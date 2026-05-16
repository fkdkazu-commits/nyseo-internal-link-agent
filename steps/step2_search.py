from config import COL_URL, COL_KW, MAX_SEARCH_CANDIDATES, EXCLUDE_URL_PATTERNS
from utils.logger import get_logger

logger = get_logger()


def search_candidates(
    target: dict,
    all_articles: list[dict],
) -> list[dict]:
    """
    STEP2: 全記事のtitle/h1/h2/h3（STEP3で取得済み）とKWを照合し、
    候補記事リストを返す（B案：全記事コンテンツ取得済み前提）。
    - KW完全一致・部分一致でスコアリング
    - Cowork内蔵AIによるKW拡張は main.py から呼び出す
    - 対象記事自身のURL・除外URLパターン・重複を除外
    """
    target_url = target["url"]
    target_kw = target["kw"]

    candidates = []

    for article in all_articles:
        url = article.get("url", "")

        # 自己参照・除外パターン除外
        if url == target_url:
            continue
        if any(pat in url for pat in EXCLUDE_URL_PATTERNS):
            continue

        score = _kw_match_score(target_kw, article)
        if score > 0:
            candidates.append({**article, "match_score": score})

    # マッチスコア降順でソートし上位N件に絞る
    candidates.sort(key=lambda x: x["match_score"], reverse=True)
    candidates = candidates[:MAX_SEARCH_CANDIDATES]

    logger.info(f"STEP2完了: 候補 {len(candidates)} 件（対象KW: {target_kw}）")
    return candidates


def _kw_match_score(kw: str, article: dict) -> int:
    """KWと記事コンテンツの一致度を簡易スコアリングする。"""
    if not kw:
        return 0

    score = 0
    title = article.get("title", "")
    h1 = article.get("h1", "")
    h2_list = article.get("h2_list", [])
    h3_list = article.get("h3_list", [])
    body = article.get("body_text", "")
    article_kw = article.get("kw", "")

    # KW完全一致
    if kw in article_kw:
        score += 10
    # タイトル・H1一致
    if kw in title or kw in h1:
        score += 8
    # H2・H3一致
    if any(kw in h for h in h2_list + h3_list):
        score += 5
    # 本文一致
    if kw in body:
        score += 3
    # 部分一致（KWの先頭2文字）
    if len(kw) >= 2 and kw[:2] in title + h1 + body:
        score += 1

    return score
