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

import asyncio
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from config import COL_KW, COL_URL, MIN_CANDIDATES, MAX_SEARCH_CANDIDATES, LEAN_BODY_TEXT_CHARS, STRICT_MIN_MATCH_SCORE, API_CONCURRENCY
from steps.step1_extract import extract_targets
from steps.step2_search import search_candidates
from steps.step3_fetch import fetch_and_parse
from steps.step4_judge import judge_candidates
from steps.step5_output import write_output
from utils.ai_client import (
    expand_keywords, expand_keywords_sync_api,
    extract_main_kw, extract_main_kw_api_async,
    judge_relevance_batch, judge_relevance_batch_api_async,
    TokenExhaustedError, NotLoggedInError,
)
from utils.logger import get_logger
from utils.sheets_client import SheetsClient

logger = get_logger()

STOP_FLAG = Path(__file__).parent / "stop.flag"
TOKEN_RESET_WAIT = 5 * 3600 + 5 * 60  # フォールバック: 5時間5分（秒）
RESET_BUFFER    = 5 * 60              # リセット時刻の5分後に再開


def _parse_reset_seconds(error_msg: str) -> int:
    """
    エラーメッセージから復帰時刻を解析して待機秒数を返す。
    例: "resets 6pm" / "resets 1:40am" / "resets 12:40pm"
    解析失敗時は TOKEN_RESET_WAIT を返す。
    """
    match = re.search(r'resets\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)', error_msg, re.IGNORECASE)
    if not match:
        return TOKEN_RESET_WAIT

    hour   = int(match.group(1))
    minute = int(match.group(2) or 0)
    ampm   = match.group(3).lower()

    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0

    # Asia/Tokyo = UTC+9 としてローカル時刻と比較
    now = datetime.now()
    reset_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    reset = reset_today if reset_today > now else reset_today + timedelta(days=1)

    wait = int((reset - now).total_seconds()) + RESET_BUFFER
    return max(wait, 60)


def _wait_for_token_reset(error_msg: str = "") -> None:
    """トークンリセットまで待機する。1分ごとに残り時間を表示する。"""
    wait_sec  = _parse_reset_seconds(error_msg) if error_msg else TOKEN_RESET_WAIT
    resume_at = datetime.now() + timedelta(seconds=wait_sec)
    logger.info(f"⏳ 約{wait_sec // 3600}時間{(wait_sec % 3600) // 60}分後"
                f"（{resume_at.strftime('%H:%M')}）に自動再開します…")
    remaining = wait_sec
    while remaining > 0:
        interval = min(1800, remaining)
        time.sleep(interval)
        remaining -= interval
        if remaining > 0:
            print(f"  再開まで残り {remaining // 60} 分…", flush=True)
    logger.info("✅ 待機完了。処理を再開します。\n")


def _shorten_kw(title: str) -> str:
    parts = re.split(r"[？！、。｜【】「」『』\s]", title)
    first = next((p.strip() for p in parts if len(p.strip()) >= 2), title)
    no_parts = first.split("の")
    return "の".join(no_parts[:2]) if len(no_parts) >= 2 else first[:20]


def _build_candidates(target: dict, all_articles: list, min_score: int, max_candidates: int, use_token_scoring: bool = True) -> list:
    """STEP2: 候補リストを構築して返す（API/CLI共通）。"""
    search_kws = [target["kw"]] if target["kw"] else []
    candidates: list[dict] = []
    for kw in search_kws:
        for c in search_candidates({**target, "kw": kw}, all_articles, min_score=min_score, use_token_scoring=use_token_scoring):
            if not any(x["url"] == c["url"] for x in candidates):
                candidates.append(c)
    if len(candidates) < MIN_CANDIDATES and target["kw"]:
        for ekw in expand_keywords_sync_api(target["kw"]):
            for c in search_candidates({**target, "kw": ekw}, all_articles, use_token_scoring=use_token_scoring):
                if not any(x["url"] == c["url"] for x in candidates):
                    candidates.append(c)
    candidates = sorted(candidates, key=lambda c: c.get("match_score", 0), reverse=True)[:max_candidates]
    return candidates


def _run_api_mode(
    targets: list, all_articles: list, client, data: list,
    max_cols: int, body_chars: int, min_score: int, max_candidates: int,
    use_token_scoring: bool = True,
) -> None:
    """--api モード: 全記事取得 → 並列KW抽出 → Phase1-3。"""
    import os
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        logger.error("anthropicパッケージが未インストールです。pip install anthropic を実行してください。")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.error("環境変数 ANTHROPIC_API_KEY が設定されていません。")
        return

    # Pre-phase A: 全未キャッシュ記事のHTML取得（同期・逐次）
    uncached = [a for a in all_articles if not a.get("title")]
    if uncached:
        logger.info(f"Pre-phase A: 未キャッシュ {len(uncached)} 件をフェッチ中…")
        for i, a in enumerate(uncached, 1):
            fetched = fetch_and_parse(a["url"])
            if fetched:
                client.save_cache(fetched)
                a.update({**fetched, "kw": a.get("kw", "")})
            print(f"  フェッチ: {i}/{len(uncached)}", end="\r", flush=True)
        print()
        logger.info("Pre-phase A完了")

    # Pre-phase B: KW未設定記事のKW抽出（直列・レート制限対応）
    # Tier1 上限50RPM → 1.3秒間隔で46RPM に抑制
    kw_needed = [a for a in all_articles if a.get("title") and not a.get("kw")]
    if kw_needed:
        logger.info(f"Pre-phase B: KW抽出 {len(kw_needed)} 件（直列・1.3秒間隔）…")
        KW_INTERVAL = 1.3

        async def _extract_all_kw():
            async_ai = AsyncAnthropic(api_key=api_key)
            results = []
            for i, a in enumerate(kw_needed, 1):
                title = a.get("title", "") or a.get("h1", "")
                kw = await extract_main_kw_api_async(async_ai, title, a.get("h2_list", []))
                results.append(kw)
                print(f"  KW抽出: {i}/{len(kw_needed)}", end="\r", flush=True)
                if i < len(kw_needed):
                    await asyncio.sleep(KW_INTERVAL)
            print()
            return results

        kw_results = asyncio.run(_extract_all_kw())
        kw_updates = []
        for a, kw in zip(kw_needed, kw_results):
            if isinstance(kw, Exception) or not kw:
                continue
            a["kw"] = kw
            kw_updates.append((a["url"], kw))
        if kw_updates:
            client.batch_save_kw(kw_updates)
        logger.info(f"Pre-phase B完了: KW設定 {len(kw_updates)} 件")

    # targets の KW を Pre-phase結果で補完
    for t in targets:
        if t["kw_source"] == "auto_detect" and not t["kw"]:
            art = next((a for a in all_articles if a["url"] == t["url"]), None)
            if art and art.get("kw"):
                t["kw"] = art["kw"]
                logger.info(f"KW補完: 「{t['kw']}」← {t['url'][:50]}")

    # Phase 1: 全記事の候補リスト構築（同期）
    logger.info(f"Phase1: {len(targets)} 記事の候補構築中…")
    prepared = []
    for i, target in enumerate(targets, 1):
        if not client.get_cache(target["url"]):
            fetched = fetch_and_parse(target["url"])
            if fetched:
                fetched["kw"] = target["kw"]
                client.save_cache(fetched)

        candidates = _build_candidates(target, all_articles, min_score, max_candidates, use_token_scoring=use_token_scoring)
        for c in candidates:
            if not client.get_cache(c["url"]):
                fetched = fetch_and_parse(c["url"])
                if fetched:
                    client.save_cache(fetched)
                    c.update(fetched)
        prepared.append((target, candidates))
        print(f"  候補構築: {i}/{len(targets)}", end="\r", flush=True)
    print()
    logger.info(f"Phase1完了: {len(prepared)} 記事")

    # Phase 2+3: 並列AI判定 → 完了次第即時書き込み
    logger.info(f"Phase2: {API_CONCURRENCY}並列でAI判定・即時書き込み開始…")
    done_count = [0]

    async def _judge_and_write_all():
        async_ai = AsyncAnthropic(api_key=api_key)
        semaphore = asyncio.Semaphore(API_CONCURRENCY)

        async def _one(target, candidates):
            if not candidates:
                return target, candidates, []
            async with semaphore:
                result = await judge_relevance_batch_api_async(async_ai, target, candidates, body_chars)
                return target, candidates, result

        tasks = [asyncio.ensure_future(_one(t, c)) for t, c in prepared]
        for fut in asyncio.as_completed(tasks):
            try:
                target, candidates, result = await fut
            except Exception as e:
                logger.warning(f"AI判定例外: {e}")
                continue
            scored = judge_candidates(target, candidates, lambda t, c: result)
            if scored is None:
                # 技術的失敗（JSON破損・トークン切れ）→ H列に書き込まず再処理可能にする
                done_count[0] += 1
                logger.warning(f"[{done_count[0]}/{len(prepared)}] AI判定失敗（スキップ）: {target['url'][:50]}")
                continue
            result_row = write_output(data[target["row_idx"]], scored, max_cols)
            client.write_result(target["row_idx"], result_row)
            done_count[0] += 1
            status = f"採用{len(scored)}件" if scored else "該当なし"
            logger.info(f"[{done_count[0]}/{len(prepared)}] {status}: {target['url'][:50]}")

    asyncio.run(_judge_and_write_all())
    logger.info("Phase2完了")


def main(spreadsheet_url: str, limit: int = 0, force_row: int = 0, lean: bool = False, strict: bool = False, api: bool = False, mid: bool = False) -> None:
    use_token_scoring = not mid
    logger.info("=" * 50)
    logger.info("NYSEO 内部リンク構築AIエージェント 開始")
    logger.info(f"📊 精度モード: {'高精度（トークン分割スコアリング）' if use_token_scoring else '中精度（全体文字列スコアリング）'}")
    if lean:
        logger.info("⚡ --lean モード: 本文150文字（候補数は通常どおり20件）")
    if strict:
        logger.info(f"🔍 --strict モード: match_score < {STRICT_MIN_MATCH_SCORE} の候補を除外")
    if api:
        logger.info(f"🚀 --api モード: Anthropic API 直接呼び出し・{API_CONCURRENCY}並列")
    logger.info("=" * 50)

    max_candidates = MAX_SEARCH_CANDIDATES
    body_chars     = LEAN_BODY_TEXT_CHARS if lean else 300
    min_score      = STRICT_MIN_MATCH_SCORE if strict else 1

    client = SheetsClient(spreadsheet_url)
    header, data = client.load_data()
    if not data:
        logger.info("データが0件です。終了します。")
        return

    max_cols = max(13, len(header))

    # STEP1: 対象記事抽出
    if force_row > 0:
        # --row 指定: H列スキップ判定を無視して指定NO行を強制処理
        row_idx = force_row - 1  # NO は1始まり、data は0始まり
        if row_idx >= len(data):
            logger.info(f"--row {force_row}: データが存在しません。終了します。")
            return
        row = data[row_idx]
        url = row[COL_URL].strip() if len(row) > COL_URL else ""
        kw  = row[COL_KW].strip()  if len(row) > COL_KW  else ""
        targets = [{
            "row_idx": row_idx,
            "url": url,
            "kw": kw,
            "kw_source": "manual" if kw else "auto_detect",
        }]
        logger.info(f"--row {force_row} 指定: {url} を強制処理します")
    else:
        targets = extract_targets(data)
        if not targets:
            logger.info("対象記事が0件です。処理を終了します。")
            return
        if limit > 0:
            targets = targets[:limit]
            logger.info(f"--limit {limit} 指定: 先頭 {limit} 件のみ処理します")

    # キャッシュ済み記事 + KWのみのスタブでインデックスを構築（HTTP不要）
    # C列KWが空の記事はキャッシュの main_kw を優先して使用する
    all_articles: list[dict] = []
    col_kw_pairs: list[tuple] = []  # C列ありでmain_kw未保存の記事を収集
    for row in data:
        url = row[COL_URL].strip() if len(row) > COL_URL else ""
        kw  = row[COL_KW].strip()  if len(row) > COL_KW  else ""
        if not url:
            continue
        cached = client.get_cache(url)
        if cached:
            effective_kw = kw or cached.get("main_kw", "")
            all_articles.append({**cached, "kw": effective_kw})
            # C列に値があるがキャッシュH列が空 → 一括保存リストに追加
            if kw and not cached.get("main_kw"):
                col_kw_pairs.append((url, kw))
        else:
            all_articles.append({
                "url": url, "kw": kw,
                "title": "", "h1": "", "h2_list": [], "h3_list": [], "body_text": "",
            })

    # C列ありの記事のmain_kwをarticle_cache H列に一括保存（API1回）
    if col_kw_pairs:
        logger.info(f"C列KWをarticle_cacheに一括保存: {len(col_kw_pairs)} 件")
        client.batch_save_kw(col_kw_pairs)

    cached_count = sum(1 for a in all_articles if a.get("title"))
    logger.info(f"インデックス構築完了: {len(all_articles)} 件（キャッシュ済み {cached_count} 件）")

    # フェーズ1: 未キャッシュ記事のHTML全件フェッチ（CLIモードも全件取得して候補漏れを防ぐ）
    # KW抽出はフェーズ2（CLI）またはPre-phase B（API）で実施
    to_fetch = [a for a in all_articles if not a.get("title")]
    if to_fetch:
        logger.info(f"未キャッシュ {len(to_fetch)} 件をフェッチ中…")
        for i, a in enumerate(to_fetch, 1):
            fetched = fetch_and_parse(a["url"])
            if fetched:
                client.save_cache(fetched)
                a.update({**fetched, "kw": a.get("kw", "")})
            print(f"  フェッチ: {i}/{len(to_fetch)}", end="\r", flush=True)
        print()
        logger.info("フェッチ完了")

    # フェーズ2: A〜G取得済み・H列(main_kw)が空の記事はKWのみ抽出してH列を更新
    # --api モード: Pre-phase Bで並列実施するためスキップ
    kw_missing = [a for a in all_articles if a.get("title") and not a["kw"]]
    if kw_missing and not api:
        logger.info(f"KW未抽出 {len(kw_missing)} 件 → main_kw を抽出中…")
        for i, a in enumerate(kw_missing, 1):
            title = a.get("title", "") or a.get("h1", "")
            extracted = extract_main_kw(title, a.get("h2_list", []))
            if extracted:
                client.update_cache_kw(a["url"], extracted)
                a["kw"] = extracted
            print(f"  KW抽出: {i}/{len(kw_missing)}", end="\r", flush=True)
        print()
        logger.info("KW抽出完了")

    print()

    # targets の KW をフェーズ1・2の結果で補完
    for t in targets:
        if t["kw_source"] == "auto_detect" and not t["kw"]:
            art = next((a for a in all_articles if a["url"] == t["url"]), None)
            if art and art.get("kw"):
                t["kw"] = art["kw"]
                logger.info(f"KW補完: 「{t['kw']}」← {t['url'][:50]}")

    # --api モード: 非同期並列処理
    if api:
        _run_api_mode(targets, all_articles, client, data, max_cols, body_chars, min_score, max_candidates, use_token_scoring=use_token_scoring)
        logger.info("\n" + "=" * 50)
        logger.info("全処理完了。Spreadsheetをご確認ください。")
        logger.info("=" * 50)
        return

    # STEP2・4・5: 対象記事ごと（CLI モード）
    for i, target in enumerate(targets, start=1):
        if STOP_FLAG.exists():
            STOP_FLAG.unlink()
            logger.info("\n⏹ 中断シグナルを受信しました。処理を停止します。")
            logger.info("再開するには、Coworkで同じSpreadsheet URLを送信してください。")
            return
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

        search_kws: list[str] = []
        skip_article = False

        # トークン切れ時は待機して同じ記事を再試行するためretryループ
        while True:
            try:
                # C列空の場合のKW設定
                if target["kw_source"] == "auto_detect" and not search_kws:
                    if target["kw"]:
                        # bootstrap またはキャッシュで既に取得済み → AI呼び出し不要
                        search_kws = [target["kw"]]
                        logger.info(f"KW（キャッシュ済み）: 「{target['kw']}」")
                    else:
                        # キャッシュミス時のフォールバック: AIで抽出してキャッシュ更新
                        art = next((a for a in all_articles if a["url"] == target["url"]), None)
                        if art:
                            title = art.get("title", "") or art.get("h1", "")
                            extracted = extract_main_kw(title, art.get("h2_list", []))
                            if extracted:
                                target["kw"] = extracted
                                search_kws = [extracted]
                                client.update_cache_kw(target["url"], extracted)
                                logger.info(f"KW自動抽出（フォールバック）: 「{extracted}」")
                            else:
                                h2h3 = art.get("h2_list", [])[:4] + art.get("h3_list", [])[:3]
                                search_kws = [h for h in h2h3 if len(h) >= 2]
                                target["kw"] = search_kws[0] if search_kws else _shorten_kw(title)
                    if not target["kw"]:
                        logger.warning("KW検出できず → 「該当なし」を書き込みます")
                        result_row = write_output(data[target["row_idx"]], [], max_cols)
                        client.write_result(target["row_idx"], result_row)
                        skip_article = True
                        break
                elif not search_kws:
                    search_kws = [target["kw"]]

                # STEP2: 候補探索
                candidates: list[dict] = []
                for kw in search_kws or [target["kw"]]:
                    for c in search_candidates({**target, "kw": kw}, all_articles, min_score=min_score, use_token_scoring=use_token_scoring):
                        if not any(x["url"] == c["url"] for x in candidates):
                            candidates.append(c)
                # 候補が少ない場合のみKW拡張（トークン節約）
                if len(candidates) < MIN_CANDIDATES:
                    for ekw in expand_keywords(target["kw"]):
                        for c in search_candidates({**target, "kw": ekw}, all_articles, use_token_scoring=use_token_scoring):
                            if not any(x["url"] == c["url"] for x in candidates):
                                candidates.append(c)

                if not candidates:
                    logger.warning("候補記事なし → 「該当なし」を書き込みます")
                    result_row = write_output(data[target["row_idx"]], [], max_cols)
                    client.write_result(target["row_idx"], result_row)
                    break

                # match_score上位N件に絞る（通常20件・lean時10件）
                candidates = sorted(candidates, key=lambda c: c.get("match_score", 0), reverse=True)[:max_candidates]
                logger.info(f"STEP2: 候補 {len(candidates)} 件")
                for _c in candidates:
                    logger.debug(f"  候補: [{_c.get('match_score',0)}点] {_c.get('title','')[:40]} ({_c.get('url','')})")

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

                # STEP4: AI一括判定（全候補を1回の呼び出しで判定）
                adopted = judge_candidates(
                    target, candidates,
                    lambda t, c: judge_relevance_batch(t, c, body_chars=body_chars),
                )

                if adopted is None:
                    # AI失敗（トークン切れ以外のエラー）→ 書き込みせずスキップ
                    break

                if len(adopted) < MIN_CANDIDATES:
                    logger.warning(f"採用 {len(adopted)} 件（閾値未満）")

                # STEP5: Sheetsに書き込み
                result_row = write_output(data[target["row_idx"]], adopted, max_cols)
                client.write_result(target["row_idx"], result_row)
                logger.info(f"→ 採用 {len(adopted)} 件をSpreadsheetに書き込みました")
                break  # 成功 → 次の記事へ

            except NotLoggedInError:
                logger.error("\n⛔ Claude CLI に未ログインです。")
                logger.error("PowerShell で claude を起動し /login でログインしてから再実行してください。")
                return

            except TokenExhaustedError as e:
                logger.warning(f"\n⛔ Claudeトークン上限: {e}")
                _wait_for_token_reset(str(e))
                # retryループ継続 → 同じ記事を再試行

        if skip_article:
            continue
        time.sleep(0.5)

    logger.info("\n" + "=" * 50)
    logger.info("全処理完了。Spreadsheetをご確認ください。")
    logger.info("=" * 50)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: py main.py <SpreadsheetURL> [--limit N] [--row N] [--lean] [--mid] [--api]")
        print("  --limit N : 未処理記事の先頭N件だけ処理")
        print("  --row N   : NO列がNの行をH列の状態に関わらず強制処理")
        print("  --lean    : トークン節約モード（本文150文字・候補数は通常どおり）")
        print("  --strict  : 低スコア候補除外モード（match_score<5の候補をAI判定から除外）")
        print("  --mid     : 中精度モード（KWトークン分割スコアリングを無効化）")
        print("  --api     : Anthropic API直接呼び出し・5並列（ANTHROPIC_API_KEY 環境変数が必要）")
        sys.exit(1)
    _args = sys.argv[1:]
    _limit = 0
    _row = 0

    def _pop_int_arg(args, flag):
        if flag in args:
            idx = args.index(flag)
            val = int(args[idx + 1]) if idx + 1 < len(args) else 0
            args = [a for i, a in enumerate(args) if i != idx and i != idx + 1]
            return args, val
        return args, 0

    _args, _limit = _pop_int_arg(_args, "--limit")
    _args, _row   = _pop_int_arg(_args, "--row")
    _lean = "--lean" in _args
    if _lean:
        _args = [a for a in _args if a != "--lean"]
    _strict = "--strict" in _args
    if _strict:
        _args = [a for a in _args if a != "--strict"]
    _api = "--api" in _args
    if _api:
        _args = [a for a in _args if a != "--api"]
    _mid = "--mid" in _args
    if _mid:
        _args = [a for a in _args if a != "--mid"]
    main(_args[0], limit=_limit, force_row=_row, lean=_lean, strict=_strict, api=_api, mid=_mid)
