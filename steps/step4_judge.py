import re

from config import SCORE_THRESHOLD, MIN_CANDIDATES
from utils.logger import get_logger

logger = get_logger()

# 日付のみの見出しパターン（例: 「1/1（木・元日）」「12/23（月）」「8/9（土）」）
_DATE_HEADING_RE = re.compile(r"^\d{1,2}/\d{1,2}[（(]")


def judge_candidates(
    target: dict,
    candidates: list[dict],
    ai_judge_batch_func,
    select_heading_func,
) -> list[dict]:
    """
    STEP4: AI一括スコアリング → 採用記事のみフェッチしてheading選定・検証。

    フロー:
    1. h2/h3・本文冒頭300文字で全候補を一括スコアリング
    2. スコア閾値以上の採用候補のみフェッチ → h2/h3/h4を取得
    3. AIにh2/h3/h4を渡してrecommended_headingを選定
    4. バリデーション・日付見出し除外
    """
    # STEP4-1: スコアリング（h2/h3のみ・recommended_headingなし）
    results = ai_judge_batch_func(target, candidates)

    if not results:
        logger.warning("STEP4: AI判定結果が空 → 書き込みをスキップします")
        return None

    score_map = {r["url"]: r for r in results}
    scored = []
    for candidate in candidates:
        r = score_map.get(candidate["url"])
        if r is None:
            continue
        scored.append({
            "url": candidate["url"],
            "score": r["score"],
            "reason": r["reason"],
        })
    scored.sort(key=lambda x: x["score"], reverse=True)

    for s in scored:
        logger.debug(f"  スコア {s['score']:3d}点: {s['url'][:60]} / {s.get('reason', '')[:60]}")

    high_scored = [c for c in scored if c["score"] >= SCORE_THRESHOLD]

    if not high_scored:
        top = scored[0] if scored else None
        if top:
            logger.info(f"STEP4完了: 採用0件（最高{top['score']}点・閾値{SCORE_THRESHOLD}点未満）理由: {top.get('reason', '')[:80]}")
        else:
            logger.info(f"STEP4完了: 採用0件（閾値{SCORE_THRESHOLD}点未満）→ 「該当なし」を出力")
        return []

    logger.info(f"STEP4-1完了: スコア閾値以上 {len(high_scored)} 件 → 見出し選定開始")

    # STEP4-2: 採用候補のみフェッチしてh4取得 → heading選定・検証
    from steps.step3_fetch import fetch_headings_with_context
    adopted = []

    for c in high_scored:
        parsed = fetch_headings_with_context(c["url"])
        if not parsed:
            logger.warning(f"フェッチ失敗: {c['url']}")
            continue

        h2_list = parsed["h2_list"]
        h3_list = parsed["h3_list"]
        h4_list = parsed["h4_list"]
        all_headings = h2_list + h3_list + h4_list

        # heading選定（スコアリング時のreasonを渡して地理的文脈を引き継ぐ）
        heading = select_heading_func(
            target,
            {
                "url": c["url"],
                "title": next((cand.get("title", "") for cand in candidates if cand["url"] == c["url"]), ""),
                "h2_list": h2_list,
                "h3_list": h3_list,
                "h4_list": h4_list,
            },
            c.get("reason", ""),
        )

        if not heading:
            logger.info(f"STEP4: 見出し選定なし → 除外: {c['url'][:60]}")
            continue

        # バリデーション：headingが実際の見出しに存在するか
        if all_headings and heading not in all_headings:
            logger.debug(f"見出し「{heading[:40]}」は実際の見出しリストにないため除外: {c['url'][:60]}")
            continue

        # 日付のみの見出しを除外
        if _DATE_HEADING_RE.match(heading):
            logger.debug(f"日付見出し「{heading}」を除外: {c['url'][:60]}")
            continue

        adopted.append({
            "url": c["url"],
            "score": c["score"],
            "reason": c["reason"],
            "heading": heading,
        })

    excluded_count = len(high_scored) - len(adopted)
    if excluded_count > 0:
        logger.info(f"STEP4: 見出し選定・検証で除外 {excluded_count} 件")

    if not adopted:
        logger.info(f"STEP4完了: 採用0件（見出し選定・150文字チェックで除外）→ 「該当なし」を出力")
    else:
        logger.info(f"STEP4完了: 採用 {len(adopted)} 件")
    return adopted
