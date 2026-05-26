from config import SCORE_THRESHOLD, MIN_CANDIDATES
from utils.logger import get_logger

logger = get_logger()


def judge_candidates(
    target: dict,
    candidates: list[dict],
    ai_judge_batch_func,
) -> list[dict]:
    """
    STEP4: Cowork内蔵AIで全候補を一括スコアリングし、採用候補リストを返す。
    1回のAI呼び出しで全候補を判定（トークン節約）。
    """
    results = ai_judge_batch_func(target, candidates)

    if not results:
        # AI呼び出し失敗（トークン切れ・タイムアウト等）→ None で返してスキップ
        logger.warning("STEP4: AI判定結果が空 → 書き込みをスキップします")
        return None

    # urlをキーにしてスコアを引けるようにする
    score_map = {r["url"]: r for r in results}

    scored: list[dict] = []
    for candidate in candidates:
        r = score_map.get(candidate["url"])
        if r is None:
            continue
        scored.append({
            "url": candidate["url"],
            "score": r["score"],
            "reason": r["reason"],
            "heading": r["recommended_heading"],
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    adopted = [c for c in scored if c["score"] >= SCORE_THRESHOLD]

    if not adopted:
        logger.info(f"STEP4完了: 採用0件（閾値{SCORE_THRESHOLD}点未満）→ 「該当なし」を出力")
    else:
        logger.info(f"STEP4完了: 採用 {len(adopted)} 件")
    return adopted
