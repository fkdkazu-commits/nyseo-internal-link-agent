"""
NYSEO 内部リンク構築エージェント — Streamlit UI
start.bat をダブルクリックするとブラウザで開きます。
"""

import csv
import io
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

# ------------------------------------------------------------------ UI設定
st.set_page_config(page_title="NYSEO 内部リンク構築エージェント", page_icon="🔗", layout="centered")

st.title("🔗 NYSEO 内部リンク構築エージェント")
st.caption("被リンク不足記事（E列≤1）に対して、関連記事から内部リンク候補を自動提案します。")

# ------------------------------------------------------------------ CSV取り込み
uploaded = st.file_uploader("NYSEOデータCSVを選択してください", type=["csv"])

if uploaded is None:
    st.info("CSVファイルを選択すると実行ボタンが表示されます。")
    st.stop()

st.success(f"✅ {uploaded.name} を読み込みました")

# ------------------------------------------------------------------ 実行ボタン
if not st.button("▶ 実行する", type="primary"):
    st.stop()

# ------------------------------------------------------------------ 処理開始
content = uploaded.read().decode("utf-8-sig")
reader = csv.reader(io.StringIO(content))
rows = list(reader)

if len(rows) < 2:
    st.error("CSVにデータ行がありません。")
    st.stop()

header = rows[0]
data = rows[1:]
max_cols = max(13, len(header))

# ログ表示用コンテナ
log_box = st.empty()
logs: list[str] = []

def log(msg: str, level: str = "INFO") -> None:
    icon = {"INFO": "✅", "WARNING": "⚠️", "ERROR": "❌"}.get(level, "ℹ️")
    logs.append(f"{icon} {msg}")
    log_box.text_area("処理ログ", "\n".join(logs), height=320, label_visibility="collapsed")


# ------------------------------------------------------------------ STEP1
log(f"CSV読み込み完了: {len(data)} 行")
targets = extract_targets(data)
log(f"STEP1完了: 対象記事 {len(targets)} 件を抽出")

if not targets:
    st.warning("対象記事が0件です。CSVを確認してください。")
    st.stop()

# ------------------------------------------------------------------ STEP3（全記事HTML一括取得）
log(f"全記事 {len(data)} 件のHTML取得を開始します…")
progress = st.progress(0, text="記事を取得しています…")
all_articles: list[dict] = []

for i, row in enumerate(data):
    url = row[COL_URL].strip() if len(row) > COL_URL else ""
    kw  = row[COL_KW].strip()  if len(row) > COL_KW  else ""
    if url:
        parsed = fetch_and_parse(url)
        if parsed:
            parsed["kw"] = kw
            all_articles.append(parsed)
    progress.progress((i + 1) / len(data), text=f"記事を取得しています… {i+1}/{len(data)}")

progress.empty()
log(f"HTML取得完了: {len(all_articles)}/{len(data)} 件成功")

# ------------------------------------------------------------------ STEP2・4・5（対象記事ごと）
for i, target in enumerate(targets, start=1):
    log(f"[{i}/{len(targets)}] 処理中: {target['url']}")

    # C列空白の場合はtitle/h1からKW自動検出
    if target["kw_source"] == "auto_detect":
        article = fetch_article(target["url"])
        if article:
            kw = (article.get("title") or article.get("h1") or "").strip()
            target["kw"] = kw[:30]
        if not target["kw"]:
            log(f"KW検出できず → スキップ", "WARNING")
            continue

    # STEP2: KW一致で候補探索 + AI KW拡張
    candidates = search_candidates(target, all_articles)
    for ekw in expand_keywords(target["kw"]):
        for c in search_candidates({**target, "kw": ekw}, all_articles):
            if not any(x["url"] == c["url"] for x in candidates):
                candidates.append(c)

    if not candidates:
        log(f"候補記事なし → スキップ", "WARNING")
        continue

    # STEP4: AI関連性判定
    adopted = judge_candidates(target, candidates, judge_relevance)
    if len(adopted) < MIN_CANDIDATES:
        log(f"採用 {len(adopted)} 件（閾値未満）→ 空欄出力", "WARNING")

    # STEP5: CSV行に書き込み
    data[target["row_idx"]] = write_output(data[target["row_idx"]], adopted, max_cols)
    log(f"→ 採用 {len(adopted)} 件を出力")

    time.sleep(0.3)

# ------------------------------------------------------------------ 出力CSV生成
buf = io.StringIO()
writer = csv.writer(buf)
padded_header = header + [""] * (max_cols - len(header))
writer.writerow(padded_header)
for row in data:
    writer.writerow(row + [""] * (max_cols - len(row)))

log("全処理完了！出力CSVを生成しました。")

# ------------------------------------------------------------------ 完了 & ダウンロード
st.success("✅ 処理が完了しました！")
st.download_button(
    label="⬇ 出力CSVをダウンロード",
    data=buf.getvalue().encode("utf-8-sig"),
    file_name=f"{Path(uploaded.name).stem}_output.csv",
    mime="text/csv",
)
