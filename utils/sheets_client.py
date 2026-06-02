"""
Google Sheets 読み書きクライアント。
サービスアカウントJSONのパスは環境変数 GOOGLE_SERVICE_ACCOUNT で指定する。
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from utils.logger import get_logger

logger = get_logger()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CACHE_TAB = "article_cache"
CACHE_COLS = ["url", "title", "h1", "h2_json", "h3_json", "body_text", "fetched_at", "main_kw"]


def _get_gspread_client() -> gspread.Client:
    key_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT", "")
    if not key_path or not Path(key_path).exists():
        raise FileNotFoundError(
            "サービスアカウントJSONが見つかりません。\n"
            "環境変数 GOOGLE_SERVICE_ACCOUNT にJSONファイルのパスを設定してください。\n"
            f"現在の値: {key_path!r}"
        )
    creds = Credentials.from_service_account_file(key_path, scopes=SCOPES)
    return gspread.authorize(creds)


class SheetsClient:
    def __init__(self, spreadsheet_url: str):
        logger.info("Google Sheetsに接続中…")
        gc = _get_gspread_client()
        self._ss = gc.open_by_url(spreadsheet_url)
        self._data_ws = self._ss.sheet1
        self._cache_ws = self._get_or_create_cache_tab()
        self._cache: dict[str, dict] = {}
        self._load_cache_index()
        logger.info(f"接続完了: {self._ss.title}")

    def _get_or_create_cache_tab(self) -> gspread.Worksheet:
        try:
            ws = self._ss.worksheet(CACHE_TAB)
            headers = ws.row_values(1)
            if "main_kw" not in headers:
                # 既存タブへの migration: グリッドを拡張してから main_kw 列を追加
                self._main_kw_col = len(headers) + 1
                ws.resize(rows=ws.row_count, cols=self._main_kw_col)
                ws.update_cell(1, self._main_kw_col, "main_kw")
                logger.info("article_cache: main_kw 列を追加しました（migration）")
            else:
                self._main_kw_col = headers.index("main_kw") + 1
            logger.info(f"キャッシュタブ '{CACHE_TAB}' を確認しました")
            return ws
        except gspread.WorksheetNotFound:
            ws = self._ss.add_worksheet(title=CACHE_TAB, rows=2000, cols=len(CACHE_COLS))
            ws.append_row(CACHE_COLS)
            self._main_kw_col = CACHE_COLS.index("main_kw") + 1
            logger.info(f"キャッシュタブ '{CACHE_TAB}' を新規作成しました")
            return ws

    def _load_cache_index(self) -> None:
        rows = self._cache_ws.get_all_records()
        for sheet_row_num, row in enumerate(rows, start=2):  # 1行目はヘッダー
            url = row.get("url", "").strip()
            if not url:
                continue
            self._cache[url] = {
                "url": url,
                "title": row.get("title", ""),
                "h1": row.get("h1", ""),
                "h2_list": json.loads(row.get("h2_json") or "[]"),
                "h3_list": json.loads(row.get("h3_json") or "[]"),
                "body_text": row.get("body_text", ""),
                "main_kw": row.get("main_kw", ""),
                "_row": sheet_row_num,  # update_cache_kw で使用
            }
        self._next_cache_row = len(rows) + 2  # ヘッダー1行 + データN行 + 1
        logger.info(f"キャッシュ読み込み完了: {len(self._cache)} 件")

    def load_data(self) -> tuple[list[str], list[list[str]]]:
        """データタブ（1枚目）を読み込み (ヘッダー, データ行リスト) を返す。"""
        all_values = self._data_ws.get_all_values()
        if not all_values:
            return [], []
        header = all_values[0]
        data = all_values[1:]
        logger.info(f"データ読み込み完了: {len(data)} 行")
        return header, data

    def get_cache(self, url: str) -> "dict | None":
        """URLのキャッシュを返す。なければ None。"""
        return self._cache.get(url.strip())

    def save_cache(self, article: dict) -> None:
        """記事データをキャッシュタブに保存する。既存URLはスキップ。"""
        url = article.get("url", "").strip()
        if not url or url in self._cache:
            return
        row = [
            url,
            article.get("title", ""),
            article.get("h1", ""),
            json.dumps(article.get("h2_list", []), ensure_ascii=False),
            json.dumps(article.get("h3_list", []), ensure_ascii=False),
            article.get("body_text", "")[:1500],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            article.get("main_kw", ""),
        ]
        self._cache_ws.append_row(row)
        self._cache[url] = {**article, "_row": self._next_cache_row}
        self._next_cache_row += 1

    def batch_save_kw(self, url_kw_pairs: list) -> None:
        """複数URLのmain_kwをまとめて一括更新する（API呼び出し1回）。"""
        col_letter = chr(64 + self._main_kw_col)
        updates = []
        for url, main_kw in url_kw_pairs:
            cached = self._cache.get(url.strip())
            if not cached or cached.get("main_kw"):
                continue
            row_num = cached.get("_row")
            if not row_num:
                continue
            updates.append({"range": f"{col_letter}{row_num}", "values": [[main_kw]]})
            cached["main_kw"] = main_kw
        if updates:
            self._cache_ws.batch_update(updates)
            logger.info(f"main_kw 一括更新: {len(updates)} 件")

    def update_cache_kw(self, url: str, main_kw: str) -> None:
        """既存キャッシュ行の main_kw を更新する。"""
        url = url.strip()
        cached = self._cache.get(url)
        if not cached:
            return
        row_num = cached.get("_row")
        if not row_num:
            return
        try:
            self._cache_ws.update_cell(row_num, self._main_kw_col, main_kw)
            cached["main_kw"] = main_kw
        except Exception as e:
            logger.warning(f"キャッシュKW更新失敗({url[:40]}): {e}")

    def write_result(self, row_idx: int, result_row: list[str]) -> None:
        """H〜M列（インデックス7〜12）をSpreadsheetに書き込む。ネットワークエラー時は3回リトライ。"""
        sheet_row = row_idx + 2  # 0始まりデータ + 1始まりSheet + ヘッダー行
        values = result_row[7:13]
        while len(values) < 6:
            values.append("")
        for attempt in range(1, 4):
            try:
                self._data_ws.update(f"H{sheet_row}:M{sheet_row}", [values])
                return
            except Exception as e:
                if attempt < 3:
                    logger.warning(f"Spreadsheet書き込みエラー（試行{attempt}/3）: {e} → 10秒後リトライ")
                    time.sleep(10)
                else:
                    logger.error(f"Spreadsheet書き込み失敗（3回試行）: {e}")
                    raise
