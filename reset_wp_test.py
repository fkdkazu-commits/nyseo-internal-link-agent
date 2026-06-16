"""
WPテストリセットスクリプト（No1〜20）

No1〜20の候補記事（H/J/L列）から挿入済み内部リンクを除去し、
スプレッドシートのN/O/P列をクリアする。

使い方:
    py reset_wp_test.py <SpreadsheetURL> [--dry-run]
"""

import re
import sys
import time

from utils.logger import get_logger
from utils.sheets_client import SheetsClient
from utils.wp_client import WPClient

logger = get_logger()

COL_NO      = 0
COL_URL     = 1   # B列: 対象記事URL（挿入されたリンクのURL）
COL_OUT_URL1 = 7  # H列
COL_OUT_URL2 = 9  # J列
COL_OUT_URL3 = 11 # L列
COL_WP_STATUS = 13  # N列
URL_COLS = [COL_OUT_URL1, COL_OUT_URL2, COL_OUT_URL3]

TARGET_RANGE = range(1, 21)  # No1〜20


def remove_inserted_links(content: str, target_url: str) -> tuple[str, int]:
    """挿入済みリンクをコンテンツから除去する。除去件数を返す。"""
    original = content
    url = re.escape(target_url)

    # 1. Classic — URL形式: <p>URL</p> または <p style="...">URL</p>
    content = re.sub(rf'<p(?:[^>]*)>{url}</p>\n{{1,2}}', '', content)

    # 2. Classic — atag形式: <p ...><a href="URL" ...>任意テキスト</a></p>\n
    content = re.sub(rf'<p[^>]*><a href="{url}"[^>]*>[^<]*</a></p>\n{{1,2}}', '', content)

    # 3. Gutenberg — URL形式 (wp:embed)
    content = re.sub(
        rf'\n<!-- wp:embed \{{[^}}]*"url":"{url}"[^}}]*\}} -->\n'
        rf'<figure[^>]*><div[^>]*>\n{url}\n</div></figure>\n'
        rf'<!-- /wp:embed -->',
        '', content,
    )

    # 4. Gutenberg — atag形式 (wp:paragraph)
    content = re.sub(
        rf'\n<!-- wp:paragraph[^>]*-->\n'
        rf'<p[^>]*><a href="{url}"[^>]*>[^<]*</a></p>\n'
        rf'<!-- /wp:paragraph -->',
        '', content,
    )

    count = 0 if content == original else 1
    return content, count


def clear_wp_status(ws, sheet_row: int) -> None:
    """N/O/P列をクリアする。"""
    ws.update(values=[["", "", ""]], range_name=f"N{sheet_row}:P{sheet_row}")


def main(spreadsheet_url: str, dry_run: bool = False) -> None:
    logger.info("=" * 55)
    logger.info(f"WPリセットスクリプト 開始（No1〜20）dry_run={dry_run}")
    logger.info("=" * 55)

    sheets = SheetsClient(spreadsheet_url)
    _, data = sheets.load_data()
    wp = WPClient()
    ws = sheets._ss.worksheets()[0]

    for row_idx, row in enumerate(data):
        no_val = row[COL_NO].strip() if row else ""
        try:
            no = int(no_val)
        except ValueError:
            continue
        if no not in TARGET_RANGE:
            continue

        target_url = row[COL_URL].strip() if len(row) > COL_URL else ""
        if not target_url:
            continue

        sheet_row = row_idx + 2
        logger.info(f"\n[No{no}] 対象URL: {target_url}")

        total_removed = 0

        for col in URL_COLS:
            cand_url = row[col].strip() if len(row) > col else ""
            if not cand_url or cand_url == "該当なし":
                continue

            post = wp.get_post_by_url(cand_url)
            if not post:
                logger.warning(f"  記事取得失敗（スキップ）: {cand_url}")
                continue

            content = post.get("content", {}).get("raw", "") or post.get("content", {}).get("rendered", "")
            new_content, removed = remove_inserted_links(content, target_url)

            if removed == 0:
                logger.info(f"  リンクなし（スキップ）: {cand_url}")
                continue

            logger.info(f"  リンク除去: {cand_url}")
            if not dry_run:
                ok = wp.update_post_content(post["id"], new_content)
                if ok:
                    total_removed += 1
                else:
                    logger.warning(f"  WP更新失敗: {cand_url}")
            else:
                logger.info(f"  [dry-run] WP更新スキップ")
                total_removed += 1

        # N/O/P列クリア
        status = row[COL_WP_STATUS].strip() if len(row) > COL_WP_STATUS else ""
        if status:
            if not dry_run:
                clear_wp_status(ws, sheet_row)
                logger.info(f"  N/O/P列クリア完了")
                time.sleep(1.5)
            else:
                logger.info(f"  [dry-run] N/O/P列クリアスキップ（現在: {status}）")
        else:
            logger.info(f"  N/O/P列は空のためスキップ")

        logger.info(f"  → 除去: {total_removed}件")

    logger.info("\n" + "=" * 55)
    logger.info("リセット完了")
    logger.info("=" * 55)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    _url = args[0]
    _dry_run = "--dry-run" in args

    main(_url, dry_run=_dry_run)
