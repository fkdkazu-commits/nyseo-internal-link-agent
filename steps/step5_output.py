from config import MAX_CANDIDATES
from utils.logger import get_logger

logger = get_logger()

_COL_PAIRS = [
    (7, 8),   # H・I列（1件目）
    (9, 10),  # J・K列（2件目）
    (11, 12), # L・M列（3件目）
]


def write_output(
    row: list[str],
    adopted: list[dict],
    max_cols: int,
) -> list[str]:
    """
    STEP5: 採用候補をスコア降順で上位MAX_CANDIDATES件に絞り、
    H〜M列（インデックス7〜12）に書き込んで返す。
    """
    top = adopted[:MAX_CANDIDATES]

    while len(row) < max_cols:
        row.append("")

    if not top:
        for col_url, col_heading in _COL_PAIRS:
            row[col_url] = ""
            row[col_heading] = ""
        row[7] = "該当なし"
        logger.info("STEP5完了: 該当なし を出力")
        return row

    seen_headings: set[str] = set()
    for i, (col_url, col_heading) in enumerate(_COL_PAIRS):
        if i < len(top):
            heading = top[i].get("heading", "")
            # ② 同じ見出しが既に採用済みならスキップ
            if heading and heading in seen_headings:
                logger.debug(f"重複見出し「{heading[:40]}」をスキップ: {top[i].get('url', '')[:60]}")
                row[col_url] = ""
                row[col_heading] = ""
            else:
                if heading:
                    seen_headings.add(heading)
                row[col_url] = top[i].get("url", "")
                row[col_heading] = heading
        else:
            row[col_url] = ""
            row[col_heading] = ""

    logger.info(f"STEP5完了: {len(top)} 件を出力")
    for i, c in enumerate(top, 1):
        logger.info(f"  [{i}] {c.get('url', '')} → 見出し: 「{c.get('heading', '')}」")
    return row
