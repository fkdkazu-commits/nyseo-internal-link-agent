"""
WordPress内部リンク挿入ツール（v1.3〜）
スプレッドシートのH〜M列（承認済み内部リンク候補）を読み込み、
WordPress記事に自動挿入する。
"""

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
from steps.step_wp_insert import insert_links, detect_editor

logger = get_logger()

# H/I, J/K, L/M 列のペア定義
_LINK_PAIRS = [
    (COL_OUT_URL1, COL_OUT_H1),
    (COL_OUT_URL2, COL_OUT_H2),
    (COL_OUT_URL3, COL_OUT_H3),
]


def main(
    spreadsheet_url: str,
    editor: str = "auto",
    link_format: str = "url",
    site_key: str = "",
    force_row: "int | None" = None,
    limit: "int | None" = None,
    count_limit: "int | None" = None,
):
    logger.info("=" * 50)
    logger.info("WordPress内部リンク挿入ツール 開始")
    _link_label = {"url": "url（URL挿入・自動判定）", "atag": "atag（テキストリンク）"}.get(link_format, link_format)
    logger.info(f"エディタ: {'自動判定' if editor == 'auto' else editor} / リンク形式: {_link_label}")
    if site_key:
        logger.info(f"対象サイト: {site_key}")
    if limit:
        logger.info(f"処理上限: No{limit}まで")
    if count_limit:
        logger.info(f"処理件数上限: {count_limit}件")
    logger.info("=" * 50)

    sheets = SheetsClient(spreadsheet_url)
    _, data = sheets.load_data()

    wp = WPClient(site_key=site_key)

    # article_cacheからタイトルを取得するためのマップを構築
    title_cache = _build_title_cache(sheets)

    rows_to_process = []
    for row_idx, row in enumerate(data):
        if force_row is not None:
            # NO列（A列=index0）で照合
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

        # N列（挿入済み）チェック — 空欄以外はすべてスキップ
        status = row[COL_WP_STATUS].strip() if len(row) > COL_WP_STATUS else ""
        if status:
            logger.debug(f"行{row_idx + 2}: 処理済みのためスキップ（{status}）")
            continue

        rows_to_process.append((row_idx, row))

    if count_limit is not None:
        rows_to_process = rows_to_process[:count_limit]

    logger.info(f"処理対象: {len(rows_to_process)} 行")

    for row_idx, row in rows_to_process:
        target_url = row[COL_URL].strip()
        no_val = row[0].strip() if row else str(row_idx + 2)
        logger.info(f"\n[NO {no_val}] {target_url}")

        target_title = title_cache.get(target_url, "")
        if not target_title:
            target_title = wp.get_post_title(target_url)

        # 挿入する (見出し, リンク先URL, リンクテキスト) のリスト
        insertions: list[tuple[str, str, str]] = []
        for col_url, col_heading in _LINK_PAIRS:
            cand_url  = row[col_url].strip()     if len(row) > col_url     else ""
            cand_head = row[col_heading].strip()  if len(row) > col_heading else ""
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

            # context=edit で取得した raw（ブロックマークアップ）を使用
            raw_content      = post.get("content", {}).get("raw", "")
            rendered_content = post.get("content", {}).get("rendered", "")
            content = raw_content or rendered_content
            # raw が取得できた場合のみ rendered を重複チェックに使う
            # （raw が空で rendered を使っている場合は二重チェックしない）
            extra_rendered = rendered_content if raw_content else ""

            # エディタ形式を自動判定（autoの場合）
            actual_editor = detect_editor(content) if editor == "auto" else editor
            if editor == "auto":
                logger.debug(f"  エディタ自動判定: {actual_editor} ({cand_url})")

            new_content, count, skipped = insert_links(
                content,
                [(cand_heading, tgt_url, tgt_title)],
                editor=actual_editor,
                link_format=link_format,
                rendered_content=extra_rendered,
            )

            if count > 0:
                ok = wp.update_post_content(post["id"], new_content)
                if ok:
                    total_inserted += 1
                else:
                    errors.append(f"更新失敗: {cand_url}")
            elif skipped > 0:
                total_skipped += 1
                logger.info(f"  スキップ: {cand_url} 見出し「{cand_heading[:30]}」")
            else:
                errors.append(f"見出し未発見: {cand_heading[:30]}")

        # N/O/P列を更新
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        if errors:
            status_val = "エラー"
            date_val   = now + " / " + " | ".join(errors)
        elif total_inserted == 0 and total_skipped > 0:
            status_val = "スキップ（リンク済み）"
            date_val   = now
        elif total_inserted > 0 and total_skipped > 0:
            status_val = "済み（スキップあり）"
            date_val   = now
        else:
            status_val = "済み"
            date_val   = now

        _write_wp_status(sheets, row_idx, status_val, date_val, total_inserted)
        logger.info(f"  → ステータス: {status_val} / 挿入: {total_inserted}件")

    logger.info("\nWordPress内部リンク挿入ツール 完了")


def _build_title_cache(sheets: SheetsClient) -> dict[str, str]:
    """article_cacheタブからURL→タイトルのマップを作る。"""
    try:
        ws = sheets._ss.worksheet("article_cache")
        records = ws.get_all_values()
        cache = {}
        for row in records[1:]:
            if len(row) >= 2:
                url   = row[0].strip()
                title = row[1].strip()
                if url and title:
                    cache[url] = title
        logger.info(f"article_cacheからタイトル {len(cache)} 件を読み込み")
        return cache
    except Exception as e:
        logger.warning(f"article_cache読み込み失敗: {e}")
        return {}


def _write_wp_status(
    sheets: SheetsClient,
    row_idx: int,
    status: str,
    date_str: str,
    count: int,
):
    """N/O/P列にステータスを書き込む。"""
    try:
        ws = sheets._ss.worksheets()[0]
        sheet_row = row_idx + 2  # ヘッダー行分+1
        ws.update(
            [[status, date_str, str(count)]],
            f"N{sheet_row}:P{sheet_row}",
        )
    except Exception as e:
        logger.warning(f"ステータス書き込み失敗 行{row_idx + 2}: {e}")


# ------------------------------------------------------------------ #
# エントリポイント
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("使い方: py main_wp.py <SpreadsheetURL> [--editor auto|classic|gutenberg] [--link url|atag|blogcard] [--site <domain>] [--row N] [--limit N]")
        sys.exit(1)

    _url     = args[0]
    _editor  = "auto"
    _link    = "url"
    _site    = ""
    _row     = None
    _limit   = None
    _count   = None

    i = 1
    while i < len(args):
        if args[i] == "--editor" and i + 1 < len(args):
            _editor = args[i + 1]; i += 2
        elif args[i] == "--link" and i + 1 < len(args):
            _link = args[i + 1]; i += 2
        elif args[i] == "--site" and i + 1 < len(args):
            _site = args[i + 1]; i += 2
        elif args[i] == "--row" and i + 1 < len(args):
            _row = int(args[i + 1]); i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            _limit = int(args[i + 1]); i += 2
        elif args[i] == "--count" and i + 1 < len(args):
            _count = int(args[i + 1]); i += 2
        else:
            i += 1

    main(_url, editor=_editor, link_format=_link, site_key=_site, force_row=_row, limit=_limit, count_limit=_count)
