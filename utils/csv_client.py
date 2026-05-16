import csv
import shutil
from pathlib import Path
from typing import Optional
from config import INPUT_DIR, OUTPUT_DIR, COL_URL, COL_INBOUND, COL_OUT_URL1
from utils.logger import get_logger

logger = get_logger()


def find_input_csv() -> Path:
    """input/ フォルダ内のCSVファイルを1つ返す。複数ある場合は最新のものを返す。"""
    files = sorted(INPUT_DIR.glob("*.csv"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"input/ フォルダにCSVファイルが見つかりません: {INPUT_DIR}")
    if len(files) > 1:
        logger.warning(f"CSVが複数あります。最新のファイルを使用します: {files[0].name}")
    logger.info(f"入力CSV: {files[0].name}")
    return files[0]


def load_csv(csv_path: Path) -> tuple[list[str], list[list[str]]]:
    """CSVを読み込み (ヘッダー行, データ行リスト) を返す。"""
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise ValueError("CSVが空です。")

    header = rows[0]
    data = rows[1:]
    logger.info(f"CSV読み込み完了: {len(data)} 行（ヘッダー除く）")
    return header, data


def is_already_processed(row: list[str]) -> bool:
    """H列にデータがある行は処理済みと判定する。"""
    if len(row) <= COL_OUT_URL1:
        return False
    return bool(row[COL_OUT_URL1].strip())


def save_output_csv(
    csv_path: Path,
    header: list[str],
    data: list[list[str]],
    output_filename: Optional[str] = None,
) -> Path:
    """
    処理済みデータをoutput/フォルダにCSVとして保存する。
    出力ファイル名はデフォルトで入力ファイル名に "_output" を付加する。
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    if output_filename is None:
        stem = csv_path.stem
        output_filename = f"{stem}_output.csv"

    output_path = OUTPUT_DIR / output_filename

    # 全行のカラム数を最大値に揃える（出力列まで空文字で埋める）
    max_cols = max(len(row) for row in [header] + data)
    padded_header = header + [""] * (max_cols - len(header))
    padded_data = [row + [""] * (max_cols - len(row)) for row in data]

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(padded_header)
        writer.writerows(padded_data)

    logger.info(f"出力CSV保存完了: {output_path}")
    return output_path


def write_result_to_row(
    row: list[str],
    results: list[dict],
    max_cols: int,
) -> list[str]:
    """
    採用候補リストをCSV行のH列以降に書き込んで返す。
    results: [{"url": ..., "heading": ...}, ...]
    """
    # 行を最大カラム数まで拡張
    while len(row) < max_cols:
        row.append("")

    col_pairs = [
        (7, 8),   # H・I列（1件目）
        (9, 10),  # J・K列（2件目）
        (11, 12), # L・M列（3件目）
    ]
    for i, (col_url, col_heading) in enumerate(col_pairs):
        if i < len(results):
            row[col_url] = results[i].get("url", "")
            row[col_heading] = results[i].get("heading", "")
        else:
            row[col_url] = ""
            row[col_heading] = ""

    return row
