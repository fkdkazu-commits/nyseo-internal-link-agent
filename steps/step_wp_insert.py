"""
STEP WP: WordPress記事への内部リンク挿入処理。
候補記事（H/J/L列URL）のI/K/M列見出しセクション末尾に
対象記事（B列URL）へのリンクを挿入する。
"""

import re
from utils.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------------ #
# 公開API
# ------------------------------------------------------------------ #

def insert_links(
    content: str,
    headings_and_targets: list[tuple[str, str, str]],
    editor: str,
    link_format: str,
) -> tuple[str, int]:
    """
    記事コンテンツに内部リンクを挿入する。

    Args:
        content: 記事のHTMLコンテンツ
        headings_and_targets: [(見出しテキスト, リンク先URL, リンクテキスト), ...]
        editor: "classic" または "gutenberg"
        link_format: "url" または "atag"

    Returns:
        (更新後コンテンツ, 挿入件数)
    """
    inserted = 0
    for heading_text, target_url, link_text in headings_and_targets:
        if editor == "gutenberg":
            new_content, ok = _insert_gutenberg(content, heading_text, target_url, link_text, link_format)
        else:
            new_content, ok = _insert_classic(content, heading_text, target_url, link_text, link_format)

        if ok:
            content = new_content
            inserted += 1
            logger.info(f"リンク挿入成功: 見出し「{heading_text[:30]}」→ {target_url}")
        else:
            logger.warning(f"見出しが見つからず挿入スキップ: 「{heading_text[:30]}」")

    return content, inserted


def already_has_link(content: str, target_url: str) -> bool:
    """コンテンツにすでに対象URLへのリンクが含まれているか確認する。"""
    return target_url in content


# ------------------------------------------------------------------ #
# クラシックエディタ（HTML）
# ------------------------------------------------------------------ #

def _insert_classic(
    content: str,
    heading_text: str,
    target_url: str,
    link_text: str,
    link_format: str,
) -> tuple[str, bool]:
    """クラシックエディタ用: 見出しタグの直後の段落末尾にリンクを挿入する。"""
    # h2〜h4タグを検索（テキストが一致するもの）
    pattern = re.compile(
        r'(<h[2-4][^>]*>)(.*?)(</h[2-4]>)',
        re.IGNORECASE | re.DOTALL,
    )

    match = _find_heading_match(pattern, content, heading_text)
    if not match:
        return content, False

    link_html = _build_link_html(target_url, link_text, link_format)

    # 見出しタグの終了位置を取得
    insert_pos = match.end()

    # 見出し直後の段落（</p>）の末尾に挿入するか、見出し直後に挿入
    after = content[insert_pos:]
    p_match = re.search(r'</p>', after, re.IGNORECASE)
    if p_match:
        abs_pos = insert_pos + p_match.end()
        new_content = content[:abs_pos] + "\n" + link_html + content[abs_pos:]
    else:
        new_content = content[:insert_pos] + "\n" + link_html + content[insert_pos:]

    return new_content, True


# ------------------------------------------------------------------ #
# Gutenbergエディタ（ブロック）
# ------------------------------------------------------------------ #

def _insert_gutenberg(
    content: str,
    heading_text: str,
    target_url: str,
    link_text: str,
    link_format: str,
) -> tuple[str, bool]:
    """Gutenberg用: 見出しブロックの直後に段落ブロックとしてリンクを挿入する。"""
    # wp:headingブロックを検索
    pattern = re.compile(
        r'(<!-- wp:heading[^>]*-->.*?<h[2-4][^>]*>)(.*?)(</h[2-4]>.*?<!-- /wp:heading -->)',
        re.IGNORECASE | re.DOTALL,
    )

    match = _find_heading_match(pattern, content, heading_text)
    if not match:
        return content, False

    link_html = _build_link_html(target_url, link_text, link_format)

    if link_format == "url":
        block = f'\n<!-- wp:paragraph -->\n<p>{link_html}</p>\n<!-- /wp:paragraph -->'
    else:
        block = f'\n<!-- wp:paragraph -->\n<p>{link_html}</p>\n<!-- /wp:paragraph -->'

    insert_pos = match.end()
    new_content = content[:insert_pos] + block + content[insert_pos:]
    return new_content, True


# ------------------------------------------------------------------ #
# 共通ユーティリティ
# ------------------------------------------------------------------ #

def _find_heading_match(pattern: re.Pattern, content: str, heading_text: str):
    """見出しテキストに一致するregexマッチを返す。"""
    heading_clean = _normalize(heading_text)
    for m in pattern.finditer(content):
        tag_text = _normalize(m.group(2))
        if heading_clean in tag_text or tag_text in heading_clean:
            return m
    return None


def _normalize(text: str) -> str:
    """比較用に空白・タグを除去して正規化する。"""
    text = re.sub(r'<[^>]+>', '', text)   # タグ除去
    text = re.sub(r'\s+', '', text)        # 空白除去
    return text.strip()


def _build_link_html(url: str, link_text: str, link_format: str) -> str:
    """link_formatに応じたHTMLを生成する。"""
    if link_format == "atag":
        safe_text = link_text or url
        return f'<a href="{url}">{safe_text}</a>'
    else:
        return url
