"""
STEP WP: WordPress記事への内部リンク挿入処理。
候補記事（H/J/L列URL）のI/K/M列見出しセクション末尾に
対象記事（B列URL）へのリンクを挿入する。
"""

import re
from utils.logger import get_logger

logger = get_logger()

# 挿入結果ステータス
_INSERTED         = "inserted"
_NOT_FOUND        = "not_found"
_SECTION_HAS_LINK = "section_has_link"


# ------------------------------------------------------------------ #
# 公開API
# ------------------------------------------------------------------ #

def detect_editor(content: str) -> str:
    """コンテンツのブロックコメント・wp-blockクラスの有無でエディタ形式を判定する。"""
    if "<!-- wp:" in content or "wp-block-" in content:
        return "gutenberg"
    return "classic"


def insert_links(
    content: str,
    headings_and_targets: list[tuple[str, str, str]],
    editor: str,
    link_format: str,
    rendered_content: str = "",
) -> tuple[str, int, int]:
    """
    記事コンテンツに内部リンクを挿入する。

    Args:
        content: 記事の raw コンテンツ
        headings_and_targets: [(見出しテキスト, リンク先URL, リンクテキスト), ...]
        editor: "classic" または "gutenberg"
        link_format: "url" または "atag"
        rendered_content: レンダリング済みHTML（投稿IDで埋め込まれたリンクの重複検知に使用）

    Returns:
        (更新後コンテンツ, 挿入件数, セクション既存リンクによるスキップ件数)
    """
    inserted = 0
    skipped  = 0
    for heading_text, target_url, link_text in headings_and_targets:
        if editor == "gutenberg":
            new_content, status = _insert_gutenberg(content, heading_text, target_url, link_text, link_format, rendered_content)
        else:
            new_content, status = _insert_classic(content, heading_text, target_url, link_text, link_format, rendered_content)

        if status == _INSERTED:
            content = new_content
            inserted += 1
            logger.info(f"リンク挿入成功: 見出し「{heading_text[:30]}」→ {target_url}")
        elif status == _SECTION_HAS_LINK:
            skipped += 1
            logger.info(f"セクション内に既存リンクあり、挿入スキップ: 「{heading_text[:30]}」")
        else:
            logger.warning(f"見出しが見つからず挿入スキップ: 「{heading_text[:30]}」")
            _log_available_headings(content, editor)

    return content, inserted, skipped


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
    rendered_content: str = "",
) -> tuple[str, str]:
    """クラシックエディタ用: 指定見出しと同レベルの次の見出し手前にリンクを挿入する。"""
    pattern = re.compile(
        r'(<h[2-5][^>]*>)(.*?)(</h[2-5]>)',
        re.IGNORECASE | re.DOTALL,
    )

    match = _find_heading_match(pattern, content, heading_text)
    if not match:
        return content, _NOT_FOUND

    # 見出しレベルを取得
    level_m = re.search(r'<h([2-5])', match.group(1), re.IGNORECASE)
    level = int(level_m.group(1)) if level_m else 2

    # 同レベル以上の次の見出し手前に挿入
    # 例: H3指定なら <h2> or <h3> が境界（H2が先に来た場合もそこで止める）
    heading_end = match.end()
    after = content[heading_end:]
    levels_str = ''.join(str(l) for l in range(2, level + 1))  # H3なら"23"
    next_boundary = re.search(rf'<h[{levels_str}][^>]*>', after, re.IGNORECASE)

    if next_boundary:
        insert_pos = heading_end + next_boundary.start()
    else:
        # 最後の見出し: セクション内の最後の </p> の後に挿入
        after_heading = content[heading_end:]
        last_p = None
        for m in re.finditer(r'</p>', after_heading, re.IGNORECASE):
            last_p = m
        insert_pos = heading_end + last_p.end() if last_p else len(content)

    # 挿入位置直前エリア（最後の子見出し以降）のみチェック
    # 子見出しセクションへの別行挿入は別箇所とみなし、ブロックしない
    section_content = content[heading_end:insert_pos]
    child_levels = ''.join(str(l) for l in range(level + 1, 6))
    if child_levels:
        last_child = None
        for m in re.finditer(rf'<h[{child_levels}][^>]*>', section_content, re.IGNORECASE):
            last_child = m
        if last_child:
            section_content = section_content[last_child.start():]
    if _section_has_url(section_content, target_url):
        return content, _SECTION_HAS_LINK
    if _section_has_url_in_rendered(rendered_content, heading_text, level, target_url):
        return content, _SECTION_HAS_LINK

    link_html = _build_link_html(target_url, link_text, link_format)
    new_content = content[:insert_pos] + link_html + "\n" + content[insert_pos:]
    return new_content, _INSERTED


# ------------------------------------------------------------------ #
# Gutenbergエディタ（ブロック）
# ------------------------------------------------------------------ #

def _insert_gutenberg(
    content: str,
    heading_text: str,
    target_url: str,
    link_text: str,
    link_format: str,
    rendered_content: str = "",
) -> tuple[str, str]:
    """Gutenberg用: 指定見出し以降のセクション末尾にリンクブロックを挿入する。"""
    pattern = re.compile(
        r'(<h[2-4][^>]*>)(.*?)(</h[2-4]>)',
        re.IGNORECASE | re.DOTALL,
    )

    match = _find_heading_match(pattern, content, heading_text)
    if not match:
        return content, _NOT_FOUND

    level_m = re.search(r'<h([2-4])', match.group(1), re.IGNORECASE)
    level = int(level_m.group(1)) if level_m else 2

    heading_end = match.end()
    after = content[heading_end:]
    levels_str = ''.join(str(l) for l in range(2, level + 1))
    next_boundary = re.search(rf'<h[{levels_str}][^>]*>', after, re.IGNORECASE)

    if next_boundary:
        section = after[:next_boundary.start()]
        insert_pos = heading_end + next_boundary.start()
    else:
        section = after
        last_p = None
        for m in re.finditer(r'</p>', after, re.IGNORECASE):
            last_p = m
        insert_pos = heading_end + last_p.end() if last_p else len(content)

    if _section_has_url(section, target_url):
        return content, _SECTION_HAS_LINK
    if _section_has_url_in_rendered(rendered_content, heading_text, level, target_url):
        return content, _SECTION_HAS_LINK

    block = _build_gutenberg_block(target_url, link_text, link_format)
    new_content = content[:insert_pos] + "\n" + block + content[insert_pos:]
    return new_content, _INSERTED


# ------------------------------------------------------------------ #
# 共通ユーティリティ
# ------------------------------------------------------------------ #

def _log_available_headings(content: str, editor: str) -> None:
    """見出し未発見時に記事内の見出し一覧をログ出力する（デバッグ用）。"""
    if editor == "gutenberg":
        headings = re.findall(r'<h[2-6][^>]*>(.*?)</h[2-6]>', content, re.IGNORECASE | re.DOTALL)
    else:
        headings = re.findall(r'<h[2-6][^>]*>(.*?)</h[2-6]>', content, re.IGNORECASE | re.DOTALL)
    clean = [_normalize(h) for h in headings]
    logger.warning(f"  記事内の見出し一覧（{len(clean)}件）: {clean[:10]}")


def _section_has_url(section_content: str, target_url: str) -> bool:
    """セクション内に対象URLが既に存在するか確認する。"""
    return target_url in section_content


def _section_has_url_in_rendered(
    rendered: str,
    heading_text: str,
    level: int,
    target_url: str,
) -> bool:
    """rendered コンテンツのセクション内に target_url が href として存在するか確認する。
    SWELL ブログカードなど投稿IDで埋め込まれたリンクの重複検知に使用する。
    rendered が空の場合は False を返す（raw のみのチェックに委ねる）。
    """
    if not rendered:
        return False
    pattern = re.compile(r'(<h[2-5][^>]*>)(.*?)(</h[2-5]>)', re.IGNORECASE | re.DOTALL)
    match = _find_heading_match(pattern, rendered, heading_text)
    if not match:
        return False
    level_m = re.search(r'<h([2-5])', match.group(1), re.IGNORECASE)
    actual_level = int(level_m.group(1)) if level_m else level
    heading_end = match.end()
    after = rendered[heading_end:]
    levels_str = ''.join(str(l) for l in range(2, actual_level + 1))
    next_boundary = re.search(rf'<h[{levels_str}][^>]*>', after, re.IGNORECASE)
    section = after[:next_boundary.start()] if next_boundary else after
    hrefs = re.findall(r'href=["\']([^"\']*)["\']', section, re.IGNORECASE)
    return any(target_url in href for href in hrefs)


def _find_heading_match(pattern: re.Pattern, content: str, heading_text: str):
    """見出しテキストに一致するregexマッチを返す。完全一致を優先し、なければ検索語が実テキストに含まれるものを返す。"""
    heading_clean = _normalize(heading_text)
    exact = None
    partial = None
    for m in pattern.finditer(content):
        tag_text = _normalize(m.group(2))
        if tag_text == heading_clean:
            exact = m
            break
        if partial is None and heading_clean in tag_text:
            partial = m
    return exact or partial


def _normalize(text: str) -> str:
    """比較用に空白・タグを除去して正規化する。"""
    text = re.sub(r'<[^>]+>', '', text)   # タグ除去
    text = re.sub(r'\s+', '', text)        # 空白除去
    return text.strip()


def _build_gutenberg_block(url: str, link_text: str, link_format: str) -> str:
    """Gutenberg用ブロックを生成する。"""
    if link_format == "atag":
        safe_text = link_text or url
        return (
            f'<!-- wp:paragraph -->\n'
            f'<p><a href="{url}" target="_blank" rel="noopener noreferrer">{safe_text}</a></p>\n'
            f'<!-- /wp:paragraph -->'
        )
    elif link_format == "shortcode":
        # link_text にはテンプレート解決済みのショートコード文字列が入る
        return (
            f'<!-- wp:shortcode -->\n'
            f'{link_text}\n'
            f'<!-- /wp:shortcode -->'
        )
    else:  # url: wp:embedブロックとして挿入（テーマ側でブログカード表示）
        return (
            f'<!-- wp:embed {{"url":"{url}"}} -->\n'
            f'<figure class="wp-block-embed">\n'
            f'<div class="wp-block-embed__wrapper">\n'
            f'{url}\n'
            f'</div>\n'
            f'</figure>\n'
            f'<!-- /wp:embed -->'
        )


def _build_link_html(url: str, link_text: str, link_format: str) -> str:
    """クラシックエディタ用HTMLを生成する。"""
    if link_format == "atag":
        safe_text = link_text or url
        return f'<p><a href="{url}" target="_blank" rel="noopener noreferrer">{safe_text}</a></p>\n'
    elif link_format == "shortcode":
        # link_text にはテンプレート解決済みのショートコード文字列が入る
        return f'{link_text}\n'
    else:  # url: URLをそのまま挿入（WordPressのoEmbed処理に委ねる）
        return f'<p>{url}</p>\n'
