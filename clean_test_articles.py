"""
ローカルWPテスト記事クリーンアップスクリプト

ローカルWP内の全記事コンテンツを h2〜h6・p タグのみに絞り込む。
mensheaven.jpスクレイピング時に混入したCTA・シェアボタン・関連記事等を除去する。

使い方:
    py clean_test_articles.py [--dry-run] [--limit N]
"""

import html as html_module
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

from utils.logger import get_logger
from prepare_test_rows import _load_wp_credentials, _wp_headers

logger = get_logger()


def _clean_content(raw_html: str) -> str:
    """生HTMLからh2〜h6・pタグのみ抽出してクリーンなHTMLを返す。"""
    import re as _re
    soup = BeautifulSoup(raw_html, "html.parser")
    parts = []
    for el in soup.find_all(["h2", "h3", "h4", "h5", "h6", "p"], recursive=True):
        text = el.get_text(strip=True)
        if not text or len(text) < 2:
            continue
        # URLのみの段落は除外（関連記事埋め込みの痕跡）
        if _re.match(r'^https?://\S+$', text):
            continue
        escaped = html_module.escape(text)
        parts.append(f"<{el.name}>{escaped}</{el.name}>")
    return "\n".join(parts)


def _is_already_clean(content: str) -> bool:
    """h・pタグ以外のHTML要素がなく、URLのみの段落もないかチェック。"""
    import re as _re
    soup = BeautifulSoup(content, "html.parser")
    for el in soup.find_all(True):
        if el.name not in ("h2", "h3", "h4", "h5", "h6", "p"):
            return False
    # URLのみの段落が残っていればクリーン済みとみなさない
    if _re.search(r'<p[^>]*>https?://\S+</p>', content):
        return False
    return True


def main(dry_run: bool = False, limit: int | None = None):
    logger.info("=" * 60)
    logger.info(f"テスト記事クリーンアップ 開始 dry_run={dry_run}")
    logger.info("=" * 60)

    wp_url, wp_user, wp_pwd = _load_wp_credentials()
    wp_api = f"{wp_url}/wp-json/wp/v2"
    headers = _wp_headers(wp_user, wp_pwd)

    # 全記事を取得（100件ずつページング）
    all_posts = []
    page = 1
    while True:
        try:
            r = requests.get(
                f"{wp_api}/posts",
                headers=headers,
                params={"per_page": 100, "page": page, "context": "edit",
                        "_fields": "id,title,content,link"},
                timeout=30,
            )
        except Exception as e:
            logger.warning(f"記事一覧取得失敗 page={page}: {e}")
            break
        if r.status_code != 200 or not r.json():
            break
        all_posts.extend(r.json())
        logger.info(f"  取得: page={page} / {len(r.json())}件")
        page += 1
        time.sleep(1)

    logger.info(f"合計 {len(all_posts)} 件取得")
    if limit:
        all_posts = all_posts[:limit]
        logger.info(f"--limit {limit} 件に絞り込み")

    updated = 0
    skipped = 0
    errors = 0

    for post in all_posts:
        post_id = post["id"]
        title = post.get("title", {}).get("rendered", "")[:40]
        raw = post.get("content", {}).get("raw", "")

        if not raw:
            skipped += 1
            continue

        if _is_already_clean(raw):
            logger.debug(f"  スキップ（クリーン済み）: [{post_id}] {title}")
            skipped += 1
            continue

        clean = _clean_content(raw)

        if not clean:
            logger.warning(f"  クリーン後が空のためスキップ: [{post_id}] {title}")
            skipped += 1
            continue

        logger.info(f"  クリーン: [{post_id}] {title}")

        if not dry_run:
            try:
                r = requests.post(
                    f"{wp_api}/posts/{post_id}",
                    headers=headers,
                    json={"content": clean},
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

    logger.info("=" * 60)
    logger.info(f"完了: 更新={updated} / スキップ={skipped} / エラー={errors}")
    logger.info("=" * 60)


if __name__ == "__main__":
    args = sys.argv[1:]
    _dry_run = "--dry-run" in args
    _limit = None
    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            _limit = int(args[i + 1])
    main(dry_run=_dry_run, limit=_limit)
