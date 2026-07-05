"""
Bug2 検証テスト: SWELL ブログカード（投稿ID保存）の重複チェック

rawコンテンツには投稿IDのみ、renderedコンテンツにhrefが含まれる状況を
手動で再現し、_section_has_url_in_rendered によるスキップが正しく動くか確認する。
"""

from steps.step_wp_insert import insert_links

TARGET_URL = "https://nyseo.co.jp/suumo-keywords/"
LINK_TEXT  = "SUUMOの流入キーワード記事"

# --------------------------------------------------------------------------
# ケース1: rawに投稿IDのみ（URLなし）、renderedに同URLのhrefあり → スキップ期待
# --------------------------------------------------------------------------
RAW_CASE1 = """\
<!-- wp:heading {"level":2} -->
<h2>SUUMOの流入キーワード</h2>
<!-- /wp:heading -->

<!-- wp:swell/blogcard {"postId":987} /-->

<!-- wp:paragraph -->
<p>本文テキストです。</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>次のセクション</h2>
<!-- /wp:heading -->
"""

RENDERED_CASE1 = """\
<h2>SUUMOの流入キーワード</h2>
<div class="swell-block-blogCard">
  <a href="https://nyseo.co.jp/suumo-keywords/" class="blogCard-wrap">
    <span class="blogCard-title">SUUMOの流入キーワード</span>
  </a>
</div>
<p>本文テキストです。</p>
<h2>次のセクション</h2>
"""

# --------------------------------------------------------------------------
# ケース2: rawにも renderedにも同URLなし → 挿入期待
# --------------------------------------------------------------------------
RAW_CASE2 = """\
<!-- wp:heading {"level":2} -->
<h2>SUUMOの流入キーワード</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>リンクのない本文テキストです。</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>次のセクション</h2>
<!-- /wp:heading -->
"""

RENDERED_CASE2 = """\
<h2>SUUMOの流入キーワード</h2>
<p>リンクのない本文テキストです。</p>
<h2>次のセクション</h2>
"""

# --------------------------------------------------------------------------
# ケース3: rawに直接URLあり → 従来ロジックでスキップ期待
# --------------------------------------------------------------------------
RAW_CASE3 = """\
<!-- wp:heading {"level":2} -->
<h2>SUUMOの流入キーワード</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p><a href="https://nyseo.co.jp/suumo-keywords/">SUUMOの流入キーワード</a></p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":2} -->
<h2>次のセクション</h2>
<!-- /wp:heading -->
"""

RENDERED_CASE3 = """\
<h2>SUUMOの流入キーワード</h2>
<p><a href="https://nyseo.co.jp/suumo-keywords/">SUUMOの流入キーワード</a></p>
<h2>次のセクション</h2>
"""


# --------------------------------------------------------------------------
# ケース4: rawに投稿IDなし、renderedで別セクションに同URLのhrefあり → 挿入期待
# --------------------------------------------------------------------------
RAW_CASE4 = """\
<!-- wp:heading {"level":2} -->
<h2>別のセクション</h2>
<!-- /wp:heading -->

<!-- wp:swell/blogcard {"postId":987} /-->

<!-- wp:heading {"level":2} -->
<h2>SUUMOの流入キーワード</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>こちらにはリンクがない。</p>
<!-- /wp:paragraph -->
"""

RENDERED_CASE4 = """\
<h2>別のセクション</h2>
<div class="swell-block-blogCard">
  <a href="https://nyseo.co.jp/suumo-keywords/" class="blogCard-wrap">
    <span class="blogCard-title">SUUMOの流入キーワード</span>
  </a>
</div>
<h2>SUUMOの流入キーワード</h2>
<p>こちらにはリンクがない。</p>
"""


def run(label, raw, rendered, expect_inserted, expect_skipped):
    _, inserted, skipped = insert_links(
        content=raw,
        headings_and_targets=[("SUUMOの流入キーワード", TARGET_URL, LINK_TEXT)],
        editor="gutenberg",
        link_format="url",
        rendered_content=rendered,
    )
    ok_i = (inserted == expect_inserted)
    ok_s = (skipped  == expect_skipped)
    result = "PASS" if (ok_i and ok_s) else "FAIL"
    print(f"[{result}] {label}")
    if not ok_i:
        print(f"       inserted: 期待={expect_inserted}, 実際={inserted}")
    if not ok_s:
        print(f"       skipped : 期待={expect_skipped},  実際={skipped}")


if __name__ == "__main__":
    print("=" * 55)
    print("Bug2 検証: renderedコンテンツによる重複チェック")
    print("=" * 55)

    run(
        "ケース1: rawに投稿IDのみ → renderedのhrefで重複検知 → スキップ",
        RAW_CASE1, RENDERED_CASE1,
        expect_inserted=0, expect_skipped=1,
    )
    run(
        "ケース2: rawもrenderedもリンクなし → 挿入される",
        RAW_CASE2, RENDERED_CASE2,
        expect_inserted=1, expect_skipped=0,
    )
    run(
        "ケース3: rawに直接URL → 従来ロジックでスキップ",
        RAW_CASE3, RENDERED_CASE3,
        expect_inserted=0, expect_skipped=1,
    )
    run(
        "ケース4: 別セクションのrenderedにhrefあり → セクション外なので挿入される",
        RAW_CASE4, RENDERED_CASE4,
        expect_inserted=1, expect_skipped=0,
    )

    print("=" * 55)
