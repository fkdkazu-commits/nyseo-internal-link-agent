"""
テスト用Gutenbergコンテンツ変換スクリプト

指定行範囲のH/J/L列に対応するローカルWP記事を
Classic HTML → Gutenbergブロック形式に変換する。

使い方:
    py test_convert_gutenberg.py <SpreadsheetURL> [--from N] [--limit N] [--dry-run]

例:
    py test_convert_gutenberg.py <URL> --from 11 --limit 20
"""

import html as html_module
import sys
import time

import requests
from bs4 import BeautifulSoup

from utils.logger import get_logger
from utils.sheets_client import SheetsClient
from prepare_test_rows import _load_wp_credentials, _wp_headers

logger = get_logger()

COL_NO       = 0
COL_OUT_URL1 = 7
COL_OUT_URL2 = 9
COL_OUT_URL3 = 11
URL_COLS = [COL_OUT_URL1, COL_OUT_URL2, COL_OUT_URL3]

LOCAL_DOMAIN = "http://nyseo-test.local"


def _to_gutenberg(raw_html: str) -> str:
    """Classic HTML → Gutenbergブロック形式に変換する。"""
    soup = BeautifulSoup(raw_html, "html.parser")
    parts = []
    for el in soup.find_all(["h2", "h3", "h4", "h5", "h6", "p"], recursive=True):
        text = el.get_text(strip=True)
        if not text or len(text) < 2:
            continue
        escaped = html_module.escape(text)
        if el.name.startswith("h"):
            level = int(el.name[1])
            level_attr = f' {{"level":{level}}}' if level != 2 else ""
            parts.append(
                f'<!-- wp:heading{level_attr} -->\n'
                f'<{el.name} class="wp-block-heading">{escaped}</{el.name}>\n'
                f'<!-- /wp:heading -->'
            )
        else:
            parts.append(
                f'<!-- wp:paragraph -->\n'
                f'<p>{escaped}</p>\n'
                f'<!-- /wp:paragraph -->'
            )
    return "\n\n".join(parts)


def _is_gutenberg(content: str) -> bool:
    return "<!-- wp:heading" in content or "<!-- wp:paragraph" in content


def _get_post_by_url(wp_api: str, headers: dict, url: str) -> dict | None:
    slug = url.rstrip("/").split("/")[-1]
    for post_type in ("posts", "pages"):
        try:
            r = requests.get(
                f"{wp_api}/{post_type}",
                headers=headers,
                params={"slug": slug, "context": "edit",
                        "_fields": "id,title,content,link"},
                timeout=30,
            )
            if r.status_code == 200 and r.json():
                return r.json()[0]
        except Exception:
            pass
    return None


def main(
    spreadsheet_url: str,
    from_row: int = 1,
    limit: "int | None" = None,
    dry_run: bool = False,
    force: bool = False,
):
    logger.info("=" * 55)
    logger.info(f"Gutenberg変換スクリプト No{from_row}〜{limit or '最後'} dry_run={dry_run} force={force}")
    logger.info("=" * 55)

    wp_url, wp_user, wp_pwd = _load_wp_credentials()
    wp_api = f"{wp_url}/wp-json/wp/v2"
    headers = _wp_headers(wp_user, wp_pwd)

    sheets = SheetsClient(spreadsheet_url)
    _, data = sheets.load_data()

    # 対象行のH/J/L列からローカルURLを収集
    target_urls: set[str] = set()
    for row in data:
        no_val = row[COL_NO].strip() if row else ""
        try:
            no = int(no_val)
        except ValueError:
            continue
        if no < from_row:
            continue
        if limit is not None and no > limit:
            continue
        for col in URL_COLS:
            val = row[col].strip() if len(row) > col else ""
            if val and LOCAL_DOMAIN in val:
                target_urls.add(val)

    logger.info(f"対象URL: {len(target_urls)} 件")

    updated = skipped = errors = 0

    for url in sorted(target_urls):
        post = _get_post_by_url(wp_api, headers, url)
        if not post:
            logger.warning(f"  記事取得失敗: {url}")
            errors += 1
            continue

        title = post.get("title", {}).get("rendered", "")[:40]
        raw   = post.get("content", {}).get("raw", "")

        if _is_gutenberg(raw) and not force:
            logger.debug(f"  スキップ（Gutenberg済み）: {title}")
            skipped += 1
            continue

        new_content = _to_gutenberg(raw)
        if not new_content:
            logger.warning(f"  変換結果が空のためスキップ: {title}")
            skipped += 1
            continue

        logger.info(f"  変換: [{post['id']}] {title}")

        if not dry_run:
            try:
                r = requests.post(
                    f"{wp_api}/posts/{post['id']}",
                    headers=headers,
                    json={"content": new_content},
                    timeout=60,
                )
                if r.status_code == 200:
                    updated += 1
                else:
                    logger.warning(f"  更新失敗: {r.status_code}")
                    errors += 1
            except Exception as e:
                logger.warning(f"  更新エラー: {e}")
                errors += 1
            time.sleep(2)
        else:
            updated += 1

    logger.info("=" * 55)
    logger.info(f"完了: 変換={updated} / スキップ={skipped} / エラー={errors}")
    logger.info("=" * 55)


# ------------------------------------------------------------------ #
# エントリポイント
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    _url      = args[0]
    _from     = 1
    _limit    = None
    _dry_run  = False
    _force    = False

    i = 1
    while i < len(args):
        if args[i] == "--from" and i + 1 < len(args):
            _from = int(args[i + 1]); i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            _limit = int(args[i + 1]); i += 2
        elif args[i] == "--dry-run":
            _dry_run = True; i += 1
        elif args[i] == "--force":
            _force = True; i += 1
        else:
            i += 1

    main(_url, from_row=_from, limit=_limit, dry_run=_dry_run, force=_force)
