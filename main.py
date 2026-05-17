"""
NYSEO 内部リンク構築AIエージェント
=====================================
Coworkのチャット欄でSpreadsheet URLを伝えると実行される。

使い方:
  py main.py <SpreadsheetURL>

処理フロー:
  STEP1: 対象記事抽出（E列≤1 かつ H列が空白）
  INDEX: キャッシュ済み記事＋KWスタブでインデックス構築（HTTP不要）
  STEP2: 候補記事探索（インデックスと KW照合）
  STEP3: 候補記事のみオンデマンドでHTML取得・キャッシュ保存
  STEP4: Cowork内蔵AIによる関連性スコアリング
  STEP5: 採用候補をSpreadsheetのH〜M列に書き込み
"""

import re
import sys
import time

from config import COL_KW, COL_URL, MIN_CANDIDATES
from steps.step1_extract import extract_targets
from steps.step2_search import search_candidates
from steps.step3_fetch import fetch_and_parse
from steps.step4_judge import judge_candidates
from steps.step5_output import write_output
from utils.ai_client import expand_keywords, judge_relevance
from utils.logger import get_logger
from utils.sheets_client import SheetsClient

logger = get_logger()


def _shorten_kw(title: str) -> str:
    parts = re.split(r"[？！、。｜【】「」『』\s]", title)
    first = next((p.strip() for p in parts if len(p.strip()) >= 2), title)
    no_parts = first.split("の")
    return "の".join(no_parts[:2]) if len(no_parts) >= 2 else first[:20]


def main(spreadsheet_url: str) -> None:
    logger.info("=" * 50)
    logger.info("NYSEO 内部リンク構築AIエージェント 開始")
    logger.info("=" * 50)

    client = SheetsClient(spreadsheet_url)
    header, data = client.load_data()
    if not data:
        logger.info("データが0件です。終了します。")
        return

    max_cols = max(13, len(header))

    # STEP1: 対象記事抽出
    targets = extract_targets(data)
    if not targets:
        logger.info("対象記事が0件です。処理を終了します。")
        return

    # キャッシュ済み記事 + KWのみのスタブでインデックスを構築（HTTP不要）
    # キャッシュ済みの記事はフル内容、未キャッシュはURL+KWのみのスタブ
    all_articles: list[dict] = []
    for row in data:
        url = row[COL_URL].strip() if len(row) > COL_URL else ""
        kw  = row[COL_KW].strip()  if len(row) > COL_KW  else ""
        if not url:
            continue
        cached = client.get_cache(url)
        if cached:
            all_articles.append({**cached, "kw": kw})
        else:
            all_articles.append({
                "url": url, "kw": kw,
                "title": "", "h1": "", "h2_list": [], "h3_list": [], "body_text": "",
            })

    cached_count = sum(1 for a in all_articles if a.get("title"))
    logger.info(f"インデックス構築完了: {len(all_articles)} 件（キャッシュ済み {cached_count} 件）\n")

    # STEP2・4・5: 対象記事ごと
    for i, target in enumerate(targets, start=1):
        print(f"\n[{i}/{len(targets)}] {target['url']}", flush=True)

        # 対象記事がキャッシュなければ今すぐ取得して保存
        if not client.get_cache(target["url"]):
            fetched = fetch_and_parse(target["url"])
            if fetched:
                fetched["kw"] = target["kw"]
                client.save_cache(fetched)
                for a in all_articles:
                    if a["url"] == target["url"]:
                        a.update(fetched)
                        break

        # C列空の場合はh2/h3をKWとして使う
        search_kws: list[str] = []
        if target["kw_source"] == "auto_detect":
            art = next((a for a in all_articles if a["url"] == target["url"]), None)
            if art:
                h2h3 = art.get("h2_list", [])[:4] + art.get("h3_list", [])[:3]
                search_kws = [h for h in h2h3 if len(h) >= 2]
                target["kw"] = search_kws[0] if search_kws else _shorten_kw(
                    art.get("title", "") or art.get("h1", "")
                )
            if not target["kw"]:
                logger.warning("KW検出できず → スキップ")
                continue
        else:
            search_kws = [target["kw"]]

        # STEP2: 候補探索（キャッシュ済み記事は高精度マッチ、スタブはKWのみマッチ）
        candidates: list[dict] = []
        for kw in search_kws or [target["kw"]]:
            for c in search_candidates({**target, "kw": kw}, all_articles):
                if not any(x["url"] == c["url"] for x in candidates):
                    candidates.append(c)
        for ekw in expand_keywords(target["kw"]):
            for c in search_candidates({**target, "kw": ekw}, all_articles):
                if not any(x["url"] == c["url"] for x in candidates):
                    candidates.append(c)

        if not candidates:
            logger.warning("候補記事なし → スキップ")
            continue

        logger.info(f"STEP2: 候補 {len(candidates)} 件")

        # 候補記事のうちキャッシュなしのものをオンデマンド取得
        fetch_count = 0
        for c in candidates:
            if not client.get_cache(c["url"]):
                fetched = fetch_and_parse(c["url"])
                if fetched:
                    client.save_cache(fetched)
                    c.update(fetched)
                    fetch_count += 1
        if fetch_count:
            logger.info(f"候補記事のHTML取得: {fetch_count} 件")

        # STEP4: AI判定
        adopted = judge_candidates(target, candidates, judge_relevance)
        if len(adopted) < MIN_CANDIDATES:
            logger.warning(f"採用 {len(adopted)} 件（閾値未満）")

        # STEP5: Sheetsに書き込み
        result_row = write_output(data[target["row_idx"]], adopted, max_cols)
        client.write_result(target["row_idx"], result_row)
        logger.info(f"→ 採用 {len(adopted)} 件をSpreadsheetに書き込みました")

        time.sleep(0.5)

    logger.info("\n" + "=" * 50)
    logger.info("全処理完了。Spreadsheetをご確認ください。")
    logger.info("=" * 50)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: py main.py <SpreadsheetURL>")
        print("例: py main.py https://docs.google.com/spreadsheets/d/xxxxxxx")
        sys.exit(1)
    main(sys.argv[1])
