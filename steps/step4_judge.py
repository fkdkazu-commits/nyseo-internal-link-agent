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
    ai_judge_func: Cowork内蔵AIを呼び出す関数（main.pyから注入）
    """
    adopted = _run_scoring(target, candidates, ai_judge_func, SCORE_THRESHOLD)

    # 採用が MIN_CANDIDATES 未満の場合、閾値を下げて再判定
    if len(adopted) < MIN_CANDIDATES:
        logger.info(f"採用 {len(adopted)} 件 < {MIN_CANDIDATES} 件 → 閾値を {SCORE_THRESHOLD_LOW} 点に下げて再判定")
        adopted = _run_scoring(target, candidates, ai_judge_func, SCORE_THRESHOLD_LOW)

    logger.info(f"STEP4完了: 採用 {len(adopted)} 件")
    return adopted


def _run_scoring(
    target: dict,
    candidates: list[dict],
    ai_judge_func,
    threshold: int,
) -> list[dict]:
    """指定閾値でスコアリングし、スコア降順の採用リストを返す。"""
    adopted = []

    for candidate in candidates:
        result = ai_judge_func(target, candidate)
        if result is None:
            continue

        score = result.get("score", 0)
        if score >= threshold:
            adopted.append({
                "url": candidate["url"],
                "score": score,
                "reason": result.get("reason", ""),
                "heading": result.get("recommended_heading", ""),
            })

    adopted.sort(key=lambda x: x["score"], reverse=True)
    return adopted
