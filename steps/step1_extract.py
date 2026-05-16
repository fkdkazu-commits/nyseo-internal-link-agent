from config import COL_URL, COL_KW, COL_INBOUND
from utils.csv_client import is_already_processed
from utils.logger import get_logger

logger = get_logger()


def extract_targets(data: list[list[str]]) -> list[dict]:
    """
    STEP1: E列（被リンク数）≤ 1 かつ H列が空白の行を対象として抽出する。
    C列（メインKW）が空白の場合はKW自動検出フラグを立てる。
    B列（記事URL）が空白の行はスキップする。
    """
    targets = []

    for row_idx, row in enumerate(data, start=2):  # 行番号はヘッダー込みで2始まり
        url = row[COL_URL].strip() if len(row) > COL_URL else ""
        if not url:
            logger.warning(f"行{row_idx}: B列（記事URL）が空白のためスキップ")
            continue

        # H列チェック（処理済み判定）
        if is_already_processed(row):
            logger.debug(f"行{row_idx}: H列にデータあり（処理済み）→ スキップ")
            continue

        # E列（被リンク数）チェック
        inbound_raw = row[COL_INBOUND].strip() if len(row) > COL_INBOUND else ""
        try:
            inbound = int(inbound_raw) if inbound_raw else 0
        except ValueError:
            inbound = 0

        if inbound > 1:
            continue

        kw = row[COL_KW].strip() if len(row) > COL_KW else ""

        targets.append({
            "row_idx": row_idx - 2,  # dataリストのインデックス
            "row_num": row_idx,
            "url": url,
            "kw": kw,
            "kw_source": "column_c" if kw else "auto_detect",
            "inbound_links": inbound,
        })

    logger.info(f"STEP1完了: 対象記事 {len(targets)} 件を抽出")
    return targets
