"""
No.11〜20の候補記事（H/J/L列）のエディタ種別を確認するスクリプト。

使い方:
    py check_editor_types.py <SpreadsheetURL> [--from N] [--to N]
"""

import sys
from config import COL_OUT_URL1, COL_OUT_URL2, COL_OUT_URL3
from utils.logger import get_logger
from utils.sheets_client import SheetsClient
from utils.wp_client import WPClient
from steps.step_wp_insert import detect_editor

logger = get_logger()

COL_NO = 0
URL_COLS = [COL_OUT_URL1, COL_OUT_URL2, COL_OUT_URL3]


def main(spreadsheet_url: str, from_no: int = 11, to_no: int = 20):
    sheets = SheetsClient(spreadsheet_url)
    _, data = sheets.load_data()
    wp = WPClient()

    target_range = range(from_no, to_no + 1)

    print(f"\n{'No':<5} {'候補記事URL':<60} {'エディタ'}")
    print("-" * 90)

    for row in data:
        no_val = row[COL_NO].strip() if row else ""
        try:
            no = int(no_val)
        except ValueError:
            continue
        if no not in target_range:
            continue

        for col in URL_COLS:
            cand_url = row[col].strip() if len(row) > col else ""
            if not cand_url or cand_url == "該当なし":
                continue

            post = wp.get_post_by_url(cand_url)
            if not post:
                print(f"{no:<5} {cand_url:<60} 取得失敗")
                continue

            content = post.get("content", {}).get("raw", "") or post.get("content", {}).get("rendered", "")
            editor = detect_editor(content)
            print(f"{no:<5} {cand_url:<60} {editor}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    _url = args[0]
    _from = 11
    _to = 20
    if "--from" in args:
        _from = int(args[args.index("--from") + 1])
    if "--to" in args:
        _to = int(args[args.index("--to") + 1])

    main(_url, from_no=_from, to_no=_to)
