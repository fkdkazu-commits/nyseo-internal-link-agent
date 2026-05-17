from config import SCORE_THRESHOLD, SCORE_THRESHOLD_LOW, MIN_CANDIDATES
from utils.logger import get_logger

logger = get_logger()


def judge_candidates(
    target: dict,
    candidates: list[dict],
    ai_judge_func,
) -> list[dict]:
    """
    STEP4: Cowork内蔵AIで各候補記事をスコアリングし、採用候補リストを返す。
    全候補を一度だけスコアリングし、閾値適用のみで再判定する（再スコアリングなし）。
    """
    # 全候補を一度だけスコアリング
    scored: list[dict] = []
    for candidate in candidates:
        result = ai_judge_func(target, candidate)
        if result is None:
            continue
        scored.append({
            "url": candidate["url"],
            "score": int(result.get("score", 0)),
            "reason": result.get("reason", ""),
            "heading": result.get("recommended_heading", ""),
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
