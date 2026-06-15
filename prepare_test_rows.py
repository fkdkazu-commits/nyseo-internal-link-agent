"""
テスト用ローカルWordPress準備スクリプト

指定行範囲（デフォルト: No21以降）のB/H/J/L列にある mensheaven.jp 記事を
ローカルWordPressに作成し、スプレッドシートのURLをローカルに置き換える。

使い方:
    py prepare_test_rows.py <SpreadsheetURL> [--start N] [--end N] [--dry-run]

オプション:
    --start N   : 処理開始No（デフォルト: 21）
    --end N     : 処理終了No（デフォルト: 最後まで）
    --dry-run   : スプレッドシートを更新せずに確認のみ
"""

import sys
import time
import re
import json
import base64
import os
import requests
from bs4 import BeautifulSoup
from pathlib import Path

# プロジェクトのimport
from utils.logger import get_logger
from utils.sheets_client import SheetsClient

logger = get_logger()

MENSHEAVEN_DOMAIN = "https://mensheaven.jp"
LOCAL_DOMAIN = "http://nyseo-test.local"

# スプレッドシートの列インデックス（0始まり）
COL_NO      = 0   # A列
COL_URL     = 1   # B列
COL_OUT_URL1 = 7  # H列
COL_OUT_URL2 = 9  # J列
COL_OUT_URL3 = 11 # L列
URL_COLS = [COL_URL, COL_OUT_URL1, COL_OUT_URL2, COL_OUT_URL3]


# ------------------------------------------------------------------ #
# WP REST API（ローカル）
# ------------------------------------------------------------------ #

def _load_wp_credentials() -> tuple[str, str, str]:
    secrets_env = Path.home() / ".secrets" / ".env"
    env = {}
    if secrets_env.exists():
        for line in secrets_env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    url  = os.environ.get("WP_URL")  or env.get("WP_URL", "")
    user = os.environ.get("WP_USER") or env.get("WP_USER", "")
    pwd  = os.environ.get("WP_APP_PASSWORD") or env.get("WP_APP_PASSWORD", "")
    if not (url and user and pwd):
        raise RuntimeError("WP_URL / WP_USER / WP_APP_PASSWORD が設定されていません")
    return url.rstrip("/"), user, pwd


def _wp_headers(user: str, pwd: str) -> dict:
    token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def _url_to_slug(url: str) -> str:
    path = url.rstrip("/").split("/")
    return path[-1] if path else ""


def get_local_post_by_slug(api_base: str, headers: dict, slug: str) -> dict | None:
    """ローカルWPからスラッグで記事を取得する。"""
    for post_type in ("posts", "pages"):
        r = requests.get(
            f"{api_base}/{post_type}",
            headers=headers,
            params={"slug": slug, "context": "edit", "_fields": "id,title,link,status"},
            timeout=15,
        )
        if r.status_code == 200 and r.json():
            return r.json()[0]
    return None


def create_local_post(api_base: str, headers: dict, title: str, content: str, slug: str) -> dict | None:
    """ローカルWPに記事を作成する。"""
    body = {
        "title":   title,
        "content": content,
        "slug":    slug,
        "status":  "publish",
    }
    r = requests.post(f"{api_base}/posts", headers=headers, json=body, timeout=60)
    if r.status_code in (200, 201):
        post = r.json()
        logger.info(f"  ✓ WP作成: [{post['id']}] {title[:40]} → {post['link']}")
        return post
    logger.warning(f"  ✗ WP作成失敗: {r.status_code} {r.text[:200]}")
    return None


# ------------------------------------------------------------------ #
# mensheaven.jp コンテンツ取得
# ------------------------------------------------------------------ #

def fetch_mensheaven_article(url: str) -> tuple[str, str] | None:
    """mensheaven.jpから (タイトル, HTMLコンテンツ) を取得する。"""
    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15,
        )
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")

        # タイトル（「– ジョブヘブンジャーナル」除去）
        raw_title = soup.title.string.strip() if soup.title and soup.title.string else ""
        title = re.split(r'\s*[–\-|]\s*', raw_title)[0].strip() or _url_to_slug(url)

        # 本文HTMLを取得（entry-content クラスを優先）
        content_div = (
            soup.find("div", class_=re.compile(r"entry-content", re.I)) or
            soup.find("div", class_=re.compile(r"post-content", re.I)) or
            soup.find("article")
        )
        if not content_div:
            logger.warning(f"  本文エリアが見つかりません: {url}")
            content_html = "<p>コンテンツを取得できませんでした</p>"
        else:
            # script/style/広告を除去
            for tag in content_div(["script", "style", "ins", "noscript"]):
                tag.decompose()
            content_html = content_div.decode_contents()

        return title, content_html

    except requests.exceptions.HTTPError as e:
        logger.warning(f"  HTTPエラー {e.response.status_code}: {url}")
        return None
    except Exception as e:
        logger.warning(f"  取得失敗: {url} — {e}")
        return None


# ------------------------------------------------------------------ #
# メイン処理
# ------------------------------------------------------------------ #

def main(
    spreadsheet_url: str,
    start_no: int = 21,
    end_no: int | None = None,
    dry_run: bool = False,
):
    logger.info("=" * 60)
    logger.info(f"テスト準備スクリプト 開始（No{start_no}〜{end_no or '最後'}）")
    logger.info(f"dry_run={dry_run}")
    logger.info("=" * 60)

    # WP認証情報ロード
    wp_url, wp_user, wp_pwd = _load_wp_credentials()
    wp_api = f"{wp_url}/wp-json/wp/v2"
    wp_headers = _wp_headers(wp_user, wp_pwd)
    logger.info(f"ローカルWP: {wp_url}")

    # スプレッドシート読み込み
    sheets = SheetsClient(spreadsheet_url)
    _, data = sheets.load_data()

    # 処理対象行の絞り込み
    rows_to_process = []
    for row_idx, row in enumerate(data):
        no_val = row[COL_NO].strip() if row else ""
        try:
            no = int(no_val)
        except ValueError:
            continue
        if no < start_no:
            continue
        if end_no is not None and no > end_no:
            continue
        rows_to_process.append((row_idx, row, no))

    logger.info(f"対象行: {len(rows_to_process)} 行")

    # 全ユニーク mensheaven.jp URL を収集
    url_set: set[str] = set()
    for _, row, _ in rows_to_process:
        for col in URL_COLS:
            val = row[col].strip() if len(row) > col else ""
            if val and MENSHEAVEN_DOMAIN in val and val not in ("該当なし",):
                url_set.add(val)

    logger.info(f"ユニーク mensheaven.jp URL: {len(url_set)} 件")

    # ローカルWPに記事を確認・作成
    url_map: dict[str, str] = {}  # mensheaven_url → local_url

    for mensheaven_url in sorted(url_set):
        slug = _url_to_slug(mensheaven_url)
        target_local_url = mensheaven_url.replace(MENSHEAVEN_DOMAIN, LOCAL_DOMAIN)

        logger.info(f"\n[{slug}]")

        # ローカルに存在するか確認
        existing = get_local_post_by_slug(wp_api, wp_headers, slug)
        if existing:
            logger.info(f"  既存: {existing['link']}")
            url_map[mensheaven_url] = target_local_url
            continue

        # mensheaven.jpから取得
        logger.info(f"  mensheaven.jpから取得中: {mensheaven_url}")
        result = fetch_mensheaven_article(mensheaven_url)
        if not result:
            logger.warning(f"  スキップ（取得失敗）")
            continue

        title, content_html = result
        logger.info(f"  タイトル: {title[:60]}")

        if dry_run:
            logger.info(f"  [dry-run] WP作成スキップ")
            url_map[mensheaven_url] = target_local_url
        else:
            post = create_local_post(wp_api, wp_headers, title, content_html, slug)
            if post:
                url_map[mensheaven_url] = target_local_url
            time.sleep(1)  # WP負荷対策

    logger.info(f"\n\nURL変換マップ: {len(url_map)} 件確定")

    # スプレッドシートのURLをローカルに書き換え
    if not url_map:
        logger.info("変換するURLがありません。終了します。")
        return

    ws = sheets._ss.worksheets()[0]
    update_count = 0

    for row_idx, row, no in rows_to_process:
        sheet_row = row_idx + 2  # ヘッダー行 + 1-indexed

        cell_updates = {}
        for col in URL_COLS:
            val = row[col].strip() if len(row) > col else ""
            if val in url_map:
                # gspread の列番号（1-indexed）
                cell_updates[col + 1] = url_map[val]

        if not cell_updates:
            continue

        if dry_run:
            for col_1indexed, new_url in cell_updates.items():
                col_letter = chr(64 + col_1indexed)
                logger.info(f"  [dry-run] No{no} {col_letter}{sheet_row}: {new_url}")
            continue

        # 実際に更新（列ごとに1セルずつ更新）
        for col_1indexed, new_url in cell_updates.items():
            col_letter = chr(64 + col_1indexed)
            try:
                ws.update(f"{col_letter}{sheet_row}", [[new_url]])
                logger.info(f"  No{no} {col_letter}{sheet_row} → {new_url}")
                update_count += 1
                time.sleep(1.5)  # Sheets APIレート制限対策
            except Exception as e:
                logger.warning(f"  書き込み失敗 {col_letter}{sheet_row}: {e}")
                time.sleep(5)

    logger.info(f"\n完了: {update_count} セルを更新しました")


# ------------------------------------------------------------------ #
# エントリポイント
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    _url     = args[0]
    _start   = 21
    _end     = None
    _dry_run = False

    i = 1
    while i < len(args):
        if args[i] == "--start" and i + 1 < len(args):
            _start = int(args[i + 1]); i += 2
        elif args[i] == "--end" and i + 1 < len(args):
            _end = int(args[i + 1]); i += 2
        elif args[i] == "--dry-run":
            _dry_run = True; i += 1
        else:
            i += 1

    main(_url, start_no=_start, end_no=_end, dry_run=_dry_run)
