"""
NYSEO 内部リンク構築エージェント — ダッシュボード
・setup_startup.bat を初回実行するとPC起動時に自動スタート
・ブラウザで http://localhost:8501 をブックマーク登録すれば1クリックで開ける
"""

import csv
import hashlib
import io
import re
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from config import COL_KW, COL_URL, MIN_CANDIDATES
from steps.step1_extract import extract_targets
from steps.step2_search import search_candidates
from steps.step3_fetch import fetch_and_parse, fetch_article
from steps.step4_judge import judge_candidates
from steps.step5_output import write_output
from utils.ai_client import expand_keywords, judge_relevance


@st.cache_data(show_spinner=False)
def _fetch_all_html_cached(csv_hash: str, rows: tuple) -> list[dict]:
    """HTMLを一括取得してキャッシュする（同じCSVなら再取得しない）。"""
    results = []
    for row in rows:
        url = row[COL_URL].strip() if len(row) > COL_URL else ""
        kw  = row[COL_KW].strip()  if len(row) > COL_KW  else ""
        if url:
            parsed = fetch_and_parse(url)
            if parsed:
                parsed["kw"] = kw
                results.append(parsed)
    return results


def _shorten_kw(title: str) -> str:
    """タイトルから検索に使える短いキーワードを抽出する。
    例: '品川区の風俗街の特徴は？料金相場・歴史' → '品川区の風俗街'
    """
    # 大きな区切りで分割し最初のまとまりを取る
    parts = re.split(r"[？！、。｜【】「」『』\s]", title)
    first = next((p.strip() for p in parts if len(p.strip()) >= 2), title)
    # さらに「の」で区切り、先頭2セグメントを返す（例: 品川区 + 風俗街）
    no_parts = first.split("の")
    if len(no_parts) >= 2:
        return "の".join(no_parts[:2])
    return first[:20]


# ------------------------------------------------------------------ ページ設定
st.set_page_config(
    page_title="NYSEO 内部リンク構築エージェント",
    page_icon="🔗",
    layout="wide",
)

# ------------------------------------------------------------------ サイドバー（将来の機能拡張エリア）
with st.sidebar:
    st.title("🔗 NYSEO Agent")
    st.markdown("---")
    page = st.radio(
        "メニュー",
        ["内部リンク提案"],   # 将来: "レポート", "設定" などを追加
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("© NYSEO 内部リンク構築エージェント")

# ------------------------------------------------------------------ メインコンテンツ
if page == "内部リンク提案":

    st.header("内部リンク提案")
    st.caption("NYSEOデータCSVを読み込み、被リンク不足記事への内部リンク候補を自動提案します。")
    st.markdown("---")

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded = st.file_uploader(
            "NYSEOデータCSVを選択してください",
            type=["csv"],
            help="A〜G列を含むNYSEO出力CSVをアップロードしてください。",
        )

    with col2:
        st.markdown("##### 処理の流れ")
        st.markdown("""
1. CSVを選択
2. 実行ボタンを押す
3. 処理完了を待つ
4. 出力CSVをダウンロード
        """)

    if uploaded is None:
        st.info("CSVファイルを選択すると実行ボタンが表示されます。")
        st.stop()

    st.success(f"✅ **{uploaded.name}** を読み込みました")

    if not st.button("▶ 実行する", type="primary", use_container_width=False):
        st.stop()

    # ------------------------------------------------------------------ 処理開始
    content = uploaded.read().decode("utf-8-sig")
    reader  = csv.reader(io.StringIO(content))
    rows    = list(reader)

    if len(rows) < 2:
        st.error("CSVにデータ行がありません。ファイルを確認してください。")
        st.stop()

    header   = rows[0]
    data     = rows[1:]
    max_cols = max(13, len(header))

    st.markdown("---")
    progress_placeholder = st.empty()
    st.markdown("##### 処理ログ")
    log_box  = st.empty()
    logs: list[str] = []

    def log(msg: str, level: str = "INFO") -> None:
        icon = {"INFO": "✅", "WARNING": "⚠️", "ERROR": "❌"}.get(level, "ℹ️")
        logs.append(f"{icon} {msg}")
        log_box.text_area(
            "log", "\n".join(logs), height=300, label_visibility="collapsed"
        )

    # STEP1
    log(f"CSV読み込み完了: {len(data)} 行")
    targets = extract_targets(data)
    log(f"STEP1完了: 対象記事 {len(targets)} 件を抽出")

    if not targets:
        st.warning("対象記事が0件です。CSVのE列を確認してください。")
        st.stop()

    # STEP3（全記事HTML一括取得 — 同じCSVなら2回目以降はキャッシュから読む）
    csv_hash = hashlib.md5(content.encode()).hexdigest()
    cached = st.session_state.get("articles_hash") == csv_hash

    if cached:
        log("HTML取得: キャッシュ済みのデータを使用します（再取得スキップ）")
        all_articles = st.session_state["all_articles"]
    else:
        log(f"全記事 {len(data)} 件のHTML取得を開始します…")
        progress_placeholder.progress(0, text="記事を取得しています…")
        all_articles = _fetch_all_html_cached(csv_hash, tuple(tuple(r) for r in data))
        st.session_state["all_articles"] = all_articles
        st.session_state["articles_hash"] = csv_hash
        progress_placeholder.empty()

    log(f"HTML取得完了: {len(all_articles)}/{len(data)} 件成功")

    # STEP2・4・5（対象記事ごと）
    for i, target in enumerate(targets, start=1):
        progress_placeholder.progress(
            i / len(targets),
            text=f"AI判定中… {i}/{len(targets)} 件",
        )
        log(f"[{i}/{len(targets)}] 処理中: {target['url']}")

        if target["kw_source"] == "auto_detect":
            article = fetch_article(target["url"])
            if article:
                raw = (article.get("title") or article.get("h1") or "").strip()
                target["kw"] = _shorten_kw(raw)
            if not target["kw"]:
                log("KW検出できず → スキップ", "WARNING")
                continue

        candidates = search_candidates(target, all_articles)
        for ekw in expand_keywords(target["kw"]):
            for c in search_candidates({**target, "kw": ekw}, all_articles):
                if not any(x["url"] == c["url"] for x in candidates):
                    candidates.append(c)

        if not candidates:
            log("候補記事なし → スキップ", "WARNING")
            continue

        adopted = judge_candidates(target, candidates, judge_relevance)
        if len(adopted) < MIN_CANDIDATES:
            log(f"採用 {len(adopted)} 件（閾値未満）→ 空欄出力", "WARNING")

        data[target["row_idx"]] = write_output(data[target["row_idx"]], adopted, max_cols)
        log(f"→ 採用 {len(adopted)} 件を出力")
        time.sleep(0.3)

    progress_placeholder.empty()
    # 出力CSV生成
    buf    = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header + [""] * (max_cols - len(header)))
    for row in data:
        writer.writerow(row + [""] * (max_cols - len(row)))

    log("全処理完了！出力CSVを生成しました。")

    # 完了 & ダウンロード
    st.markdown("---")
    st.success("✅ 処理が完了しました！")
    st.download_button(
        label="⬇ 出力CSVをダウンロード",
        data=buf.getvalue().encode("utf-8-sig"),
        file_name=f"{Path(uploaded.name).stem}_output.csv",
        mime="text/csv",
        use_container_width=True,
    )
