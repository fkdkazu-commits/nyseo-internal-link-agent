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
    """コンテンツのブロックコメント有無でエディタ形式を判定する。"""
    return "gutenberg" if "<!-- wp:" in content else "classic"


def insert_links(
    content: str,
    headings_and_targets: list[tuple[str, str, str]],
    editor: str,
    link_format: str,
) -> tuple[str, int, int]:
    """
    記事コンテンツに内部リンクを挿入する。

    Args:
        content: 記事のHTMLコンテンツ
        headings_and_targets: [(見出しテキスト, リンク先URL, リンクテキスト), ...]
        editor: "classic" または "gutenberg"
        link_format: "url" または "atag"

    Returns:
        (更新後コンテンツ, 挿入件数, セクション既存リンクによるスキップ件数)
    """
    inserted = 0
    skipped  = 0
    for heading_text, target_url, link_text in headings_and_targets:
        if editor == "gutenberg":
            new_content, status = _insert_gutenberg(content, heading_text, target_url, link_text, link_format)
        else:
            new_content, status = _insert_classic(content, heading_text, target_url, link_text, link_format)

        if status == _INSERTED:
            content = new_content
            inserted += 1
            logger.info(f"リンク挿入成功: 見出し「{heading_text[:30]}」→ {target_url}")
        elif status == _SECTION_HAS_LINK:
            skipped += 1
            logger.info(f"セクション内に既存リンクあり、挿入スキップ: 「{heading_text[:30]}」")
        else:
            logger.warning(f"見出しが見つからず挿入スキップ: 「{heading_text[:30]}」")

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
        insert_pos = len(content)

    # セクション内に既存リンクがあればスキップ
    section_content = content[heading_end:insert_pos]
    if _section_has_link(section_content):
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
) -> tuple[str, str]:
    """Gutenberg用: 見出しブロック直後の段落の後にリンクブロックを挿入する。"""
    # wp:headingブロックを検索（<!-- wp:heading ... --> の中に > が含まれる場合に対応）
    pattern = re.compile(
        r'(<!-- wp:heading.*?-->[ \t]*\r?\n?<h[2-4][^>]*>)(.*?)(</h[2-4]>[ \t]*\r?\n?<!-- /wp:heading -->)',
        re.IGNORECASE | re.DOTALL,
    )

    match = _find_heading_match(pattern, content, heading_text)
    if not match:
        return content, _NOT_FOUND

    # マッチした見出しのレベルを取得（デフォルトH2）
    level_m = re.search(r'<h([2-5])', match.group(1), re.IGNORECASE)
    level = int(level_m.group(1)) if level_m else 2

    # 同レベル以上の次の見出しブロックまでのセクションを取得
    # 例: H3指定なら <h2> or <h3> が境界（H2が先に来た場合もそこで止める）
    heading_end = match.end()
    after = content[heading_end:]
    levels_str = ''.join(str(l) for l in range(2, level + 1))  # H3なら"23"
    next_boundary = re.search(
        rf'<!-- wp:heading[^>]*>\s*<h[{levels_str}][^>]*>',
        after,
        re.IGNORECASE,
    )
    section = after[:next_boundary.start()] if next_boundary else after

    # セクション内に既存リンクがあればスキップ
    if _section_has_link(section):
        return content, _SECTION_HAS_LINK

    # そのセクション内の最後の <!-- /wp:paragraph --> の後に挿入
    last_para = None
    for m in re.finditer(r'<!-- /wp:paragraph -->', section, re.IGNORECASE):
        last_para = m
    if last_para:
        insert_pos = heading_end + last_para.end()
    else:
        insert_pos = heading_end

    block = _build_gutenberg_block(target_url, link_text, link_format)
    new_content = content[:insert_pos] + "\n" + block + content[insert_pos:]
    return new_content, _INSERTED


# ------------------------------------------------------------------ #
# 共通ユーティリティ
# ------------------------------------------------------------------ #

def _section_has_link(section_content: str) -> bool:
    """セクション内にリンク（aタグ・wp:embed）が存在するか確認する。"""
    if re.search(r'<a\s[^>]*href=', section_content, re.IGNORECASE):
        return True
    if re.search(r'<!--\s*wp:embed', section_content, re.IGNORECASE):
        return True
    return False


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
    """Gutenberg用ブロックを生成する。URLのみ→embedブロック、aタグ→paragraphブロック。"""
    if link_format == "atag":
        safe_text = link_text or url
        return f'<!-- wp:paragraph -->\n<p><a href="{url}">{safe_text}</a></p>\n<!-- /wp:paragraph -->'
    else:
        return (
            f'<!-- wp:embed {{"url":"{url}"}} -->\n'
            f'<figure class="wp-block-embed"><div class="wp-block-embed__wrapper">\n'
            f'{url}\n'
            f'</div></figure>\n'
            f'<!-- /wp:embed -->'
        )


def _build_link_html(url: str, link_text: str, link_format: str) -> str:
    """クラシックエディタ用HTMLを生成する。<p>タグで囲み記事枠内に収める。"""
    if link_format == "atag":
        safe_text = link_text or url
        return f'<p><a href="{url}">{safe_text}</a></p>\n'
    else:
        return f'<p>{url}</p>\n'
