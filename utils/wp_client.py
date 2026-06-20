"""
WordPress REST API クライアント。
認証情報は ~/.secrets/nyseo_sites.json（Spreadsheet IDで検索）または
~/.secrets/.env から読み込む。
"""

import base64
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from utils.logger import get_logger

logger = get_logger()

_SECRETS_DIR = Path.home() / ".secrets"
_SECRETS_ENV  = _SECRETS_DIR / ".env"
_SITES_JSON   = _SECRETS_DIR / "nyseo_sites.json"


def _load_wp_credentials(spreadsheet_id: str = "") -> tuple[str, str, str]:
    """WP_URL / WP_USER / WP_APP_PASSWORD を取得する。

    優先順位:
    1. nyseo_sites.json の spreadsheet_id エントリ
    2. 環境変数
    3. ~/.secrets/.env
    """
    # 1. nyseo_sites.json から Spreadsheet ID で検索
    if spreadsheet_id and _SITES_JSON.exists():
        try:
            sites = json.loads(_SITES_JSON.read_text(encoding="utf-8"))
            if spreadsheet_id in sites:
                entry = sites[spreadsheet_id]
                url  = entry.get("wp_url", "")
                user = entry.get("wp_user", "")
                pwd  = entry.get("wp_app_password", "")
                if url and user and pwd:
                    logger.info(f"nyseo_sites.json からWP認証情報を取得: {url}")
                    return url.rstrip("/"), user, pwd
        except Exception as e:
            logger.warning(f"nyseo_sites.json 読み込み失敗: {e}")

    # 2. 環境変数 + .env フォールバック
    env = {}
    if _SECRETS_ENV.exists():
        for line in _SECRETS_ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    url  = os.environ.get("WP_URL")  or env.get("WP_URL", "")
    user = os.environ.get("WP_USER") or env.get("WP_USER", "")
    pwd  = os.environ.get("WP_APP_PASSWORD") or env.get("WP_APP_PASSWORD", "")

    if not (url and user and pwd):
        raise RuntimeError(
            "WordPress認証情報が不足しています。"
            "install.bat を再実行してWordPress設定を完了させるか、"
            "~/.secrets/.env に WP_URL / WP_USER / WP_APP_PASSWORD を設定してください。"
        )
    return url.rstrip("/"), user, pwd


class WPClient:
    """WordPress REST API クライアント。"""

    def __init__(self, spreadsheet_id: str = ""):
        self.base_url, user, pwd = _load_wp_credentials(spreadsheet_id)
        token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }
        self._api = f"{self.base_url}/wp-json/wp/v2"

    # ------------------------------------------------------------------ #
    # 記事取得
    # ------------------------------------------------------------------ #

    def get_post_by_url(self, article_url: str) -> "dict | None":
        """記事URLからWordPress投稿を取得する。"""
        slug = self._url_to_slug(article_url)
        if not slug:
            logger.warning(f"スラッグ抽出失敗: {article_url}")
            return None

        # まずslugで検索（context=edit で content.raw を取得）
        for post_type in ("posts", "pages"):
            r = requests.get(
                f"{self._api}/{post_type}",
                headers=self.headers,
                params={"slug": slug, "context": "edit", "_fields": "id,title,content,link,status"},
                timeout=60,
            )
            if r.status_code == 200:
                posts = r.json()
                if posts:
                    logger.info(f"記事取得成功: {posts[0]['link']} (ID:{posts[0]['id']})")
                    return posts[0]

        logger.warning(f"記事が見つかりません: {article_url} (slug: {slug})")
        return None

    def get_post_title(self, article_url: str) -> str:
        """記事URLからタイトルを取得する。article_cache にない場合のフォールバック用。"""
        post = self.get_post_by_url(article_url)
        if post:
            return post.get("title", {}).get("rendered", "")
        return ""

    # ------------------------------------------------------------------ #
    # 記事更新
    # ------------------------------------------------------------------ #

    def update_post_content(self, post_id: int, new_content: str) -> bool:
        """投稿のcontentを更新する。"""
        r = requests.post(
            f"{self._api}/posts/{post_id}",
            headers=self.headers,
            json={"content": new_content},
            timeout=60,
        )
        if r.status_code == 200:
            logger.info(f"記事更新成功: ID={post_id}")
            return True
        logger.warning(f"記事更新失敗: ID={post_id} status={r.status_code} {r.text[:200]}")
        return False

    # ------------------------------------------------------------------ #
    # ユーティリティ
    # ------------------------------------------------------------------ #

    @staticmethod
    def _url_to_slug(url: str) -> str:
        """URLからスラッグ（最後のパス要素）を抽出する。"""
        path = urlparse(url).path.rstrip("/")
        return path.split("/")[-1] if path else ""
