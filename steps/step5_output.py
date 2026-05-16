from config import MAX_CANDIDATES
from utils.csv_client import write_result_to_row
from utils.logger import get_logger

logger = get_logger()


def write_output(
    row: list[str],
    adopted: list[dict],
    max_cols: int,
) -> list[str]:
    """
    STEP5: 採用候補をスコア降順で上位MAX_CANDIDATES件に絞り、
    CSV行のH列以降に書き込んで返す。
    """
    top = adopted[:MAX_CANDIDATES]

    results = [{"url": c["url"], "heading": c["heading"]} for c in top]
    updated_row = write_result_to_row(row, results, max_cols)

    logger.info(f"STEP5完了: {len(top)} 件を出力")
    return updated_row
