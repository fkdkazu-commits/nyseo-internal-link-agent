"""
WP挿入全パターンテスト用スクリプト

Classic/Gutenberg × URL/aタグ の4パターンを行ごとにランダムで選択して挿入する。
テスト用途のみ。本番では使用しないこと。

使い方:
    py test_wp_random.py <SpreadsheetURL> [--row N] [--limit N]
"""

import random
import re
import sys
from datetime import datetime

from config import (
    COL_URL, COL_OUT_URL1, COL_OUT_H1,
    COL_OUT_URL2, COL_OUT_H2,
    COL_OUT_URL3, COL_OUT_H3,
    COL_WP_STATUS, COL_WP_DATE, COL_WP_COUNT,
)
from utils.logger import get_logger
from utils.sheets_client import SheetsClient
from utils.wp_client import WPClient
from steps.step_wp_insert import insert_links, already_has_link, detect_editor
from main_wp import _build_title_cache, _write_wp_status

logger = get_logger()

_LINK_PAIRS = [
    (COL_OUT_URL1, COL_OUT_H1),
    (COL_OUT_URL2, COL_OUT_H2),
    (COL_OUT_URL3, COL_OUT_H3),
]


def main(
    spreadsheet_url: str,
    force_row: "int | None" = None,
    limit: "int | None" = None,
):
    logger.info("=" * 50)
    logger.info("WP挿入全パターンテスト（ランダム選択）開始")
    logger.info("Classic/Gutenberg × URL/aタグ を行ごとにランダム選択")
    logger.info("=" * 50)

    sheets = SheetsClient(spreadsheet_url)
    _, data = sheets.load_data()

    _ss_id_m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", spreadsheet_url)
    _ss_id   = _ss_id_m.group(1) if _ss_id_m else ""
    wp = WPClient(spreadsheet_id=_ss_id)

    title_cache = _build_title_cache(sheets)

    rows_to_process = []
    for row_idx, row in enumerate(data):
        if force_row is not None:
            no_val = row[0].strip() if row else ""
            if no_val != str(force_row):
                continue

        if limit is not None:
            no_val = row[0].strip() if row else ""
            try:
                if int(no_val) > limit:
                    continue
            except ValueError:
                continue

        target_url = row[COL_URL].strip() if len(row) > COL_URL else ""
        if not target_url:
            continue

        h_val = row[COL_OUT_URL1].strip() if len(row) > COL_OUT_URL1 else ""
        if not h_val or h_val == "該当なし":
            continue

        status = row[COL_WP_STATUS].strip() if len(row) > COL_WP_STATUS else ""
        if status == "済み":
            logger.debug(f"行{row_idx + 2}: 挿入済みのためスキップ")
            continue

        rows_to_process.append((row_idx, row))

    logger.info(f"処理対象: {len(rows_to_process)} 行")

    for row_idx, row in rows_to_process:
        target_url = row[COL_URL].strip()
        no_val = row[0].strip() if row else str(row_idx + 2)

        editor_choice = random.choice(["classic", "gutenberg"])
        link_choice   = random.choice(["url", "atag"])
        logger.info(f"\n[NO {no_val}] {target_url}")
        logger.info(f"  ランダム選択: editor={editor_choice} / link={link_choice}")

        target_title = title_cache.get(target_url, "") or wp.get_post_title(target_url)

        insertions: list[tuple[str, str, str, str]] = []
        for col_url, col_heading in _LINK_PAIRS:
            cand_url  = row[col_url].strip()    if len(row) > col_url    else ""
            cand_head = row[col_heading].strip() if len(row) > col_heading else ""
            if not cand_url or not cand_head:
                continue
            insertions.append((cand_url, cand_head, target_url, target_title))

        total_inserted = 0
        total_skipped  = 0
        errors = []

        for cand_url, cand_heading, tgt_url, tgt_title in insertions:
            post = wp.get_post_by_url(cand_url)
            if not post:
                errors.append(f"記事取得失敗: {cand_url}")
                continue

            content = post.get("content", {}).get("raw", "") or post.get("content", {}).get("rendered", "")

            if already_has_link(content, tgt_url):
                logger.info(f"  すでにリンクあり: {cand_url}")
                total_inserted += 1
                continue

            new_content, count, skipped = insert_links(
                content,
                [(cand_heading, tgt_url, tgt_title)],
                editor=editor_choice,
                link_format=link_choice,
            )

            if count > 0:
                ok = wp.update_post_content(post["id"], new_content)
                if ok:
                    total_inserted += 1
                else:
                    errors.append(f"更新失敗: {cand_url}")
            elif skipped > 0:
                total_skipped += 1
                logger.info(f"  セクション内既存リンクのためスキップ: {cand_url} 見出し「{cand_heading[:30]}」")
            else:
                errors.append(f"見出し未発見: {cand_heading[:30]}")

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        if errors:
            status_val = "エラー"
            date_val   = now + " / " + " | ".join(errors)
        elif total_skipped > 0:
            status_val = "済み（スキップあり）"
            date_val   = now
        else:
            status_val = "済み"
            date_val   = now

        _write_wp_status(sheets, row_idx, status_val, date_val, total_inserted)
        logger.info(f"  → ステータス: {status_val} / 挿入: {total_inserted}件")

    logger.info("\nWP挿入全パターンテスト 完了")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    _url   = args[0]
    _row   = None
    _limit = None

    i = 1
    while i < len(args):
        if args[i] == "--row" and i + 1 < len(args):
            _row = int(args[i + 1]); i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            _limit = int(args[i + 1]); i += 2
        else:
            i += 1

    main(_url, force_row=_row, limit=_limit)
