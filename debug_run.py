"""
開発用デバッグスクリプト。
Streamlit不要・UIなしで特定の行だけ全ステップをテスト実行する。

使い方:
  py debug_run.py            # CSVの最初の対象記事1件だけテスト
  py debug_run.py 5          # 5行目（データ行・0始まり）だけテスト
  py debug_run.py --ai-mock  # AI呼び出しをモック（高速テスト）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import csv
from config import COL_URL, COL_KW, MIN_CANDIDATES
from steps.step1_extract import extract_targets
from steps.step2_search import search_candidates
from steps.step3_fetch import fetch_and_parse, fetch_article
from steps.step4_judge import judge_candidates
from steps.step5_output import write_output
from utils.csv_client import find_input_csv

# --- 引数解析 ---
args = sys.argv[1:]
use_mock = "--ai-mock" in args
row_idx = int([a for a in args if a.isdigit()][0]) if any(a.isdigit() for a in args) else None

# --- AIモック（--ai-mock 時はclaudeを呼ばない） ---
def mock_judge(target, candidate):
    return {"score": 75, "reason": "[MOCK] テスト用ダミー", "recommended_heading": "[MOCK] 見出し"}

def mock_expand(kw):
    return []

if use_mock:
    judge_fn   = mock_judge
    expand_fn  = mock_expand
    print("[MOCK MODE] AI呼び出しをスキップします")
else:
    from utils.ai_client import expand_keywords as expand_fn, judge_relevance as judge_fn

# --- CSV読み込み ---
csv_path = find_input_csv()
with open(csv_path, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f))

header = rows[0]
data   = rows[1:]
print(f"CSV読み込み: {len(data)} 行  ({csv_path.name})")

# --- STEP1 ---
targets = extract_targets(data)
print(f"STEP1: 対象記事 {len(targets)} 件")

if not targets:
    print("対象記事が0件です。終了します。")
    sys.exit(0)

# テスト対象を1件に絞る
target = targets[row_idx] if row_idx is not None and row_idx < len(targets) else targets[0]
print(f"\nテスト対象: 行{target['row_num']}  {target['url']}")
print(f"  KW: {target['kw'] or '(空・自動検出)'}")

# --- STEP3（対象記事のみ + 全記事HTML取得） ---
print("\n[STEP3] HTML取得中…")
if target["kw_source"] == "auto_detect":
    article = fetch_article(target["url"])
    if article:
        target["kw"] = (article.get("title") or article.get("h1") or "")[:30]
    print(f"  KW自動検出: {target['kw'] or '(検出失敗)'}")

all_articles = []
for i, row in enumerate(data[:20]):  # 高速化のため先頭20行のみ取得
    url = row[COL_URL].strip() if len(row) > COL_URL else ""
    kw  = row[COL_KW].strip()  if len(row) > COL_KW  else ""
    if url:
        parsed = fetch_and_parse(url)
        if parsed:
            parsed["kw"] = kw
            all_articles.append(parsed)
    print(f"  {i+1}/20 完了", end="\r")

print(f"\n  取得成功: {len(all_articles)} 件")

# --- STEP2 ---
candidates = search_candidates(target, all_articles)
for ekw in expand_fn(target["kw"]):
    for c in search_candidates({**target, "kw": ekw}, all_articles):
        if not any(x["url"] == c["url"] for x in candidates):
            candidates.append(c)

print(f"\n[STEP2] 候補記事: {len(candidates)} 件")
for c in candidates[:5]:
    print(f"  score={c['match_score']}  {c['url']}")

# --- STEP4 ---
print("\n[STEP4] AI判定中…")
adopted = judge_candidates(target, candidates, judge_fn)
print(f"  採用: {len(adopted)} 件")
for a in adopted:
    print(f"  score={a['score']}  {a['url']}")
    print(f"    見出し: {a['heading']}")

# --- STEP5 ---
max_cols = max(13, len(header))
result_row = write_output(data[target["row_idx"]], adopted, max_cols)
print(f"\n[STEP5] 出力行（H〜M列）:")
print(f"  H: {result_row[7] if len(result_row) > 7 else ''}")
print(f"  I: {result_row[8] if len(result_row) > 8 else ''}")
print(f"  J: {result_row[9] if len(result_row) > 9 else ''}")
print(f"  K: {result_row[10] if len(result_row) > 10 else ''}")

print("\n✅ デバッグ完了")
