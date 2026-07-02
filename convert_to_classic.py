"""
Gutenberg記事をClassicエディタ形式に変換するスクリプト。
ブロックコメント（<!-- wp:... -->）を除去し、内部のHTMLのみ残す。

使い方:
    py convert_to_classic.py <post_id> [<post_id> ...]
    py convert_to_classic.py --dry-run <post_id> [<post_id> ...]
"""

import re
import sys
import requests
from utils.logger import get_logger
from utils.wp_client import WPClient

logger = get_logger()


def strip_block_comments(content: str) -> str:
    """Gutenbergブロックコメントとwp-block-*クラスを除去してClassic形式のHTMLにする。"""
    # ブロックコメント除去
    content = re.sub(r'<!-- wp:[^\-].*?-->\n?', '', content)
    content = re.sub(r'<!-- /wp:[^\-].*?-->\n?', '', content)
    # wp-block-* クラスをclass属性から除去（class属性が空になれば属性ごと削除）
    def clean_class(m):
        classes = ' '.join(c for c in m.group(1).split() if not c.startswith('wp-block-'))
        return f' class="{classes}"' if classes else ''
    content = re.sub(r' class="([^"]*)"', clean_class, content)
    # 連続する空行を1行に
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()


def get_post_by_id(wp: WPClient, post_id: int) -> "dict | None":
    """IDで記事を取得する。"""
    for post_type in ("posts", "pages"):
        r = requests.get(
            f"{wp._api}/{post_type}/{post_id}",
            headers=wp.headers,
            params={"context": "edit", "_fields": "id,title,content,link"},
            timeout=60,
        )
        if r.status_code == 200:
            return r.json()
    return None


def main(post_ids: list[int], dry_run: bool = False):
    wp = WPClient()

    if "localhost" not in wp.base_url and ".local" not in wp.base_url:
        logger.error(f"このスクリプトはローカル環境専用です。本番サイトでは実行できません: {wp.base_url}")
        sys.exit(1)

    for post_id in post_ids:
        logger.info(f"\n[ID:{post_id}] 処理開始")

        post = get_post_by_id(wp, post_id)
        if not post:
            logger.warning(f"  記事取得失敗: ID={post_id}")
            continue

        title = post.get("title", {}).get("rendered", "")
        content_raw = post.get("content", {}).get("raw", "")

        if not content_raw:
            logger.warning(f"  content.raw が空: ID={post_id}")
            continue

        if "<!-- wp:" not in content_raw and "wp-block-" not in content_raw:
            logger.info(f"  すでにClassic形式: {title[:40]}")
            continue

        new_content = strip_block_comments(content_raw)
        logger.info(f"  タイトル: {title[:40]}")
        logger.info(f"  変換前: {len(content_raw)}文字 → 変換後: {len(new_content)}文字")

        if dry_run:
            logger.info(f"  [dry-run] 更新スキップ")
            continue

        ok = wp.update_post_content(post_id, new_content)
        if ok:
            logger.info(f"  ✅ Classic形式に変換完了")
        else:
            logger.warning(f"  ❌ 更新失敗")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    dry_run = "--dry-run" in args
    ids = [int(a) for a in args if a.isdigit()]

    if not ids:
        print("post_idを指定してください。例: py convert_to_classic.py 163 164 165 166")
        sys.exit(1)

    main(ids, dry_run=dry_run)
