from config import COL_URL, COL_KW, COL_INBOUND, COL_OUT_URL1
from utils.logger import get_logger

logger = get_logger()


def extract_targets(data: list[list[str]]) -> list[dict]:
    """
    STEP1: E列（被リンク数）≤ 1 かつ H列が空白の行を対象として抽出する。
    C列（メインKW）が空白の場合はKW自動検出フラグを立てる。
    B列（記事URL）が空白の行はスキップする。
    """
    targets = []

    for row_idx, row in enumerate(data):
        url = row[COL_URL].strip() if len(row) > COL_URL else ""
        if not url:
            logger.warning(f"行{row_idx + 2}: B列（記事URL）が空白のためスキップ")
            continue

        if _is_already_processed(row):
            logger.debug(f"行{row_idx + 2}: H列にデータあり（処理済み）→ スキップ")
            continue

        inbound_raw = row[COL_INBOUND].strip() if len(row) > COL_INBOUND else ""
        try:
            inbound = int(inbound_raw) if inbound_raw else 0
        except ValueError:
            inbound = 0

        if inbound > 1:
            continue

        kw = row[COL_KW].strip() if len(row) > COL_KW else ""

        targets.append({
            "row_idx": row_idx,
            "url": url,
            "kw": kw,
            "kw_source": "column_c" if kw else "auto_detect",
            "inbound_links": inbound,
        })

    logger.info(f"STEP1完了: 対象記事 {len(targets)} 件を抽出")
    return targets


def _is_already_processed(row: list[str]) -> bool:
    """H列にデータがある行は処理済みと判定する。"""
    if len(row) <= COL_OUT_URL1:
        return False
    return bool(row[COL_OUT_URL1].strip())
