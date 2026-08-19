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
from urllib.parse import urlparse, unquote

import requests

from utils.logger import get_logger

logger = get_logger()

_SECRETS_DIR = Path.home() / ".secrets"
_SECRETS_ENV  = _SECRETS_DIR / ".env"
_SITES_JSON   = _SECRETS_DIR / "nyseo_sites.json"


def _load_wp_credentials(site_key: str = "") -> tuple[str, str, str]:
    """WP_URL / WP_USER / WP_APP_PASSWORD を取得する。

    優先順位:
    1. nyseo_sites.json の site_key エントリ（指定時）
    2. nyseo_sites.json に1サイトのみ登録の場合はそれを自動使用
    3. 環境変数
    4. ~/.secrets/.env
    """
    # 1. nyseo_sites.json からサイトキー（ドメイン）で検索
    if _SITES_JSON.exists():
        try:
            sites = json.loads(_SITES_JSON.read_text(encoding="utf-8-sig"))
            entry = None
            if site_key and site_key in sites:
                entry = sites[site_key]
                logger.info(f"nyseo_sites.json からWP認証情報を取得: {site_key}")
            elif not site_key and len(sites) == 1:
                entry = list(sites.values())[0]
                logger.info(f"nyseo_sites.json からWP認証情報を取得（1サイト自動選択）: {list(sites.keys())[0]}")
            if entry:
                url  = entry.get("wp_url", "")
                user = entry.get("wp_user", "")
                pwd  = entry.get("wp_app_password", "")
                if url and user and pwd:
                    # ローカル開発環境（.local / localhost / 127.0.0.1）は変換しない
                    _host = urlparse(url).hostname or ""
                    _is_local = _host in ("localhost", "127.0.0.1") or _host.endswith(".local")
                    if url.startswith("http://") and not _is_local:
                        url = "https://" + url[len("http://"):]
                        logger.warning(f"wp_url が http:// のため https:// に自動変換しました: {url}")
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

    def __init__(self, site_key: str = ""):
        self.base_url, user, pwd = _load_wp_credentials(site_key)
        token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        self._api = f"{self.base_url}/wp-json/wp/v2"

    # ------------------------------------------------------------------ #
    # 記事取得
    # ------------------------------------------------------------------ #

    def get_post_by_url(self, article_url: str) -> "dict | None":
        """記事URLからWordPress投稿を取得する。"""
        # ?p=ID 形式の URL は直接 ID で取得
        m = re.search(r"[?&]p=(\d+)", article_url)
        if m:
            post_id = int(m.group(1))
            for post_type in ("posts", "pages"):
                r = requests.get(
                    f"{self._api}/{post_type}/{post_id}",
                    headers=self.headers,
                    params={"context": "edit", "_fields": "id,title,content,link,status"},
                    timeout=60,
                )
                logger.debug(f"?p=ID検索: {self._api}/{post_type}/{post_id} → {r.status_code}")
                if r.status_code == 200:
                    post = r.json()
                    logger.info(f"記事取得成功（?p=ID）: {post.get('link')} (ID:{post.get('id')})")
                    return post

        slug = self._url_to_slug(article_url)

        # slug が取れた場合はまず slug 検索（context=edit で content.raw を取得）
        if slug:
            for post_type in ("posts", "pages"):
                r = requests.get(
                    f"{self._api}/{post_type}",
                    headers=self.headers,
                    params={"slug": slug, "context": "edit", "_fields": "id,title,content,link,status"},
                    timeout=60,
                )
                logger.debug(f"slug検索: /{post_type}?slug=... → {r.status_code}")
                if r.status_code == 200:
                    posts = r.json()
                    if posts:
                        logger.info(f"記事取得成功（slug）: {posts[0]['link']} (ID:{posts[0]['id']})")
                        return posts[0]
            logger.debug(f"slug検索で見つからず、shortlink経由で再試行: {article_url} (slug: {slug})")

        # フォールバック: 記事HTMLのshortlink（?p=ID）からIDを取得して直接引く
        post_id = self._extract_post_id_from_html(article_url)
        if post_id:
            for post_type in ("posts", "pages"):
                r = requests.get(
                    f"{self._api}/{post_type}/{post_id}",
                    headers=self.headers,
                    params={"context": "edit", "_fields": "id,title,content,link,status"},
                    timeout=60,
                )
                if r.status_code == 200:
                    post = r.json()
                    logger.info(f"記事取得成功（ID直接）: {post.get('link')} (ID:{post.get('id')})")
                    return post

        logger.warning(f"記事が見つかりません: {article_url} (slug: {slug})")
        return None

    def _extract_post_id_from_html(self, article_url: str) -> "int | None":
        """記事HTMLの shortlink タグから投稿IDを抽出する。"""
        try:
            r = requests.get(article_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30, allow_redirects=True)
            if r.status_code != 200:
                return None
            m = re.search(r"[?&]p=(\d+)", r.text)
            if m:
                return int(m.group(1))
        except Exception as e:
            logger.debug(f"shortlink取得失敗: {e}")
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
            returned = r.json().get("content", {}).get("raw", "")
            if returned:
                def _norm(s: str) -> str:
                    return s.replace("\r\n", "\n").replace("\r", "\n").strip()
                if _norm(new_content) not in _norm(returned):
                    logger.warning(f"記事更新失敗（APIは200を返したが内容が保存されていません）: ID={post_id}")
                    return False
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
        slug = path.split("/")[-1] if path else ""
        return unquote(slug)
