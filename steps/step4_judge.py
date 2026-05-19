from config import SCORE_THRESHOLD, SCORE_THRESHOLD_LOW, MIN_CANDIDATES
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

    # 通常閾値で絞り込み
    adopted = [c for c in scored if c["score"] >= SCORE_THRESHOLD]

    # 不足の場合は閾値を下げて再適用（AIは呼ばない）
    if len(adopted) < MIN_CANDIDATES:
        logger.info(
            f"採用 {len(adopted)} 件 < {MIN_CANDIDATES} 件 "
            f"→ 閾値を {SCORE_THRESHOLD_LOW} 点に下げて再適用"
        )
        adopted = [c for c in scored if c["score"] >= SCORE_THRESHOLD_LOW]

    logger.info(f"STEP4完了: 採用 {len(adopted)} 件")
    return adopted
