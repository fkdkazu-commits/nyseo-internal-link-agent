"""
既存の内部リンクパターン分析スクリプト。
被リンク数が多い記事を取得し、その記事へのリンク元の文脈を分析する。

使い方:
  py analyze_links.py
"""

import csv
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))

import requests
from bs4 import BeautifulSoup

from config import COL_URL, COL_KW, COL_INBOUND, COL_OUTBOUND, USER_AGENT
from utils.csv_client import find_input_csv

HEADERS = {"User-Agent": USER_AGENT}
DOMAIN = "mensheaven.jp"

# --- CSV読み込み ---
csv_path = find_input_csv()
with open(csv_path, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f))[1:]

# URLとKWの辞書を作成
url_to_kw = {}
for row in rows:
    url = row[COL_URL].strip() if len(row) > COL_URL else ""
    kw  = row[COL_KW].strip()  if len(row) > COL_KW  else ""
    if url:
        url_to_kw[url] = kw

# 被リンク数の多い記事を抽出（E列降順 上位10件）
ranked = []
for row in rows:
    url = row[COL_URL].strip() if len(row) > COL_URL else ""
    kw  = row[COL_KW].strip()  if len(row) > COL_KW  else "(空)"
    try:
        inbound = int(row[COL_INBOUND].strip()) if len(row) > COL_INBOUND and row[COL_INBOUND].strip() else 0
        outbound = int(row[COL_OUTBOUND].strip()) if len(row) > COL_OUTBOUND and row[COL_OUTBOUND].strip() else 0
    except ValueError:
        continue
    if url and inbound > 1:
        ranked.append({"url": url, "kw": kw, "inbound": inbound, "outbound": outbound})

ranked.sort(key=lambda x: x["inbound"], reverse=True)
top = ranked[:5]

print(f"=== 被リンク数上位5記事 ===")
for i, r in enumerate(top, 1):
    print(f"{i}. 被リンク={r['inbound']}  KW={r['kw'] or '(空)'}  {r['url']}")

print()

# 各上位記事を取得して内部リンクを抽出
for target in top:
    print(f"\n{'='*60}")
    print(f"対象: {target['kw'] or '(空)'}  (被リンク {target['inbound']} 件)")
    print(f"URL:  {target['url']}")
    print()

    try:
        resp = requests.get(target["url"], headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"  取得失敗: {e}")
        continue

    soup = BeautifulSoup(resp.text, "html.parser")

    # 本文エリアを特定（article or main or body）
    body = soup.find("article") or soup.find("main") or soup.body
    if not body:
        continue

    # 内部リンクを前後のテキストと一緒に抽出
    links_found = []
    for a in body.find_all("a", href=True):
        href = a["href"]
        if DOMAIN not in href:
            continue
        # 正規化
        href = href.split("?")[0].rstrip("/")
        if href == target["url"].rstrip("/"):
            continue  # 自己参照除外

        anchor_text = a.get_text(strip=True)
        if not anchor_text:
            continue

        # 近くの見出しを探す
        heading = ""
        for parent in a.parents:
            for sib in parent.find_all_previous(["h2", "h3", "h4"]):
                heading = sib.get_text(strip=True)
                break
            if heading:
                break

        # 前後の文章コンテキスト
        context = ""
        parent_p = a.find_parent(["p", "li", "td"])
        if parent_p:
            context = parent_p.get_text(strip=True)[:80]

        dest_kw = url_to_kw.get(href, url_to_kw.get(href + "/", "(CSV外)"))

        links_found.append({
            "href": href,
            "anchor": anchor_text,
            "heading": heading,
            "context": context,
            "dest_kw": dest_kw,
        })

    # 重複除去
    seen = set()
    unique_links = []
    for lk in links_found:
        key = lk["href"]
        if key not in seen:
            seen.add(key)
            unique_links.append(lk)

    print(f"  内部リンク数: {len(unique_links)} 件")
    print()

    for lk in unique_links[:8]:
        print(f"  ▶ アンカー : {lk['anchor']}")
        print(f"    見出し   : {lk['heading'] or '(見出しなし)'}")
        print(f"    文脈     : {lk['context'][:60]}…" if lk['context'] else "    文脈     : (なし)")
        print(f"    リンク先KW: {lk['dest_kw'] or '(空)'}")
        print(f"    URL      : {lk['href']}")
        print()
