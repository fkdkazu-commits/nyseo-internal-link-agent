"""
NYSEO 内部リンク構築AIエージェント
=====================================
Coworkのチャット欄で「内部リンクエージェントを実行してください」と入力すると
CLAUDE.md の手順に従ってこのスクリプトが呼び出される。

処理フロー:
  STEP1: 対象記事抽出（E列≤1 かつ H列が空白）
  STEP2: 関連記事候補探索（KW一致 + Cowork内蔵AIによるKW拡張）
  STEP3: 全記事HTML一括取得・解析（B案）
  STEP4: Cowork内蔵AIによる関連性スコアリング（100点・5観点）
  STEP5: 採用候補をCSV出力（H列以降）
"""

import time

from config import MIN_CANDIDATES
from steps.step1_extract import extract_targets
from steps.step2_search import search_candidates
from steps.step3_fetch import fetch_all_articles, fetch_article
from steps.step4_judge import judge_candidates
from steps.step5_output import write_output
from utils.ai_client import expand_keywords, judge_relevance
from utils.csv_client import find_input_csv, load_csv, save_output_csv
from utils.logger import get_logger

logger = get_logger()


def _detect_kw_from_article(url: str) -> str:
    """C列が空白の場合、記事を取得してtitle/h1からKWを検出する。"""
    article = fetch_article(url)
    if not article:
        return ""
    kw = article.get("title", "").strip() or article.get("h1", "").strip()
    # 長すぎる場合は先頭30文字に絞る
    return kw[:30] if kw else ""


def main():
    logger.info("=" * 50)
    logger.info("NYSEO 内部リンク構築AIエージェント 開始")
    logger.info("=" * 50)

    # --- CSVロード ---
    csv_path = find_input_csv()
    header, data = load_csv(csv_path)
    max_cols = max(13, len(header))  # H〜M列（インデックス12）まで確保

    # --- STEP1: 対象記事抽出 ---
    targets = extract_targets(data)
    if not targets:
        logger.info("対象記事が0件です。処理を終了します。")
        return

    # --- STEP3（B案）: 全記事HTML一括取得 ---
    logger.info(f"\n全記事（{len(data)}件）のHTML一括取得を開始します（B案）...")
    all_articles = fetch_all_articles(data)
    logger.info(f"一括取得完了: {len(all_articles)} 件\n")

    # --- 対象記事ごとに処理 ---
    for i, target in enumerate(targets, start=1):
        logger.info(f"\n[{i}/{len(targets)}] 処理中: {target['url']}")

        # C列KWが空の場合、記事HTMLからKW自動検出
        if target["kw_source"] == "auto_detect":
            kw = _detect_kw_from_article(target["url"])
            target["kw"] = kw
            if kw:
                logger.info(f"KW自動検出: {kw}")
            else:
                logger.warning("KW検出できず。スキップします。")
                continue

        # --- STEP2: 候補探索（KW一致） ---
        candidates = search_candidates(target, all_articles)

        # KW拡張で候補を補完
        expanded_kws = expand_keywords(target["kw"])
        for ekw in expanded_kws:
            extra = search_candidates({**target, "kw": ekw}, all_articles)
            for c in extra:
                if not any(x["url"] == c["url"] for x in candidates):
                    candidates.append(c)

        if not candidates:
            logger.warning(f"候補記事が見つかりませんでした。スキップします。")
            continue

        logger.info(f"STEP2完了: 候補 {len(candidates)} 件")

        # --- STEP4: AI関連性判定 ---
        adopted = judge_candidates(target, candidates, judge_relevance)

        if len(adopted) < MIN_CANDIDATES:
            logger.warning(
                f"採用件数が{MIN_CANDIDATES}件未満（{len(adopted)}件）のため空欄出力します。"
            )

        # --- STEP5: CSV行に書き込み ---
        row = data[target["row_idx"]]
        data[target["row_idx"]] = write_output(row, adopted, max_cols)

        time.sleep(0.5)  # レート制限対応

    # --- 出力CSV保存 ---
    save_output_csv(csv_path, header, data)

    logger.info("\n" + "=" * 50)
    logger.info("全処理完了")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
