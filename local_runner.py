"""
NYSEO ローカルランナーサーバー
Cowork (Claude in Chrome) から main.py / main_wp.py を起動するための橋渡し。
ポート 8765 で待機し、Chrome からの GET リクエストを受け取る。

エンドポイント:
  GET /status                          現在の実行状態を返す
  GET /sites                           登録済みWordPressサイト一覧を返す
  GET /run?url=...                     main.py を実行開始する
       &mid=true/false                  中精度モード（省略時=false=高精度）
       &api=true/false                  APIモード（省略時=false=CLIモード）
  GET /run-wp?url=...                  main_wp.py を実行開始する（v1.3〜）
       &editor=classic|gutenberg        エディタ形式
       &link=blogcard|url|atag           リンク形式
       &site=<domain>                    対象WordPressサイト（複数登録時に指定）
  GET /stop                            実行中の処理を停止する
  GET /reset                           実行中フラグを強制リセットする（スタック時の回復用）
"""

import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_SITES_JSON = Path.home() / ".secrets" / "nyseo_sites.json"


def _load_sites() -> dict:
    """~/.secrets/nyseo_sites.json から登録済みサイト一覧を読み込む。"""
    if _SITES_JSON.exists():
        try:
            return json.loads(_SITES_JSON.read_text(encoding="utf-8-sig"))
        except Exception:
            pass
    return {}

PROJECT_DIR = Path(__file__).parent
LOG_FILE    = PROJECT_DIR / "logs" / "latest.log"
STOP_FLAG   = PROJECT_DIR / "stop.flag"
_SENTINEL   = Path.home() / ".nyseo_runner_done"   # スペースを含むパスを避けるためホームディレクトリに配置
PORT = 8765

IS_MAC = platform.system() == "Darwin"
PYTHON_CMD = "python3" if IS_MAC else "py"


def _open_terminal_mac(bash_script: str) -> None:
    """macOS: 一時bashスクリプトをTerminal.appで実行する"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False, encoding="utf-8") as f:
        f.write(bash_script)
        tmp_path = f.name
    os.chmod(tmp_path, 0o755)
    subprocess.Popen([
        "osascript", "-e",
        f'tell application "Terminal" to activate\ntell application "Terminal" to do script "bash {tmp_path}"'
    ])


def _sentinel_cleanup() -> None:
    """sentinel ファイルが残留していれば削除する。"""
    try:
        _SENTINEL.unlink()
    except FileNotFoundError:
        pass


def _wait_for_sentinel(interval: float = 2.0, timeout: float = 10800.0) -> None:
    """sentinel ファイルが作成されるまでポーリングし、作成後に削除する。
    timeout 秒（デフォルト3時間）経過しても検知できない場合は諦めて返る。
    """
    elapsed = 0.0
    while not _SENTINEL.exists():
        time.sleep(interval)
        elapsed += interval
        if elapsed >= timeout:
            break
    try:
        _SENTINEL.unlink()
    except Exception:
        pass


_running = False
_lock = threading.Lock()

LOG_FILE.parent.mkdir(exist_ok=True)


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/status":
            with _lock:
                status = "running" if _running else "idle"
            self._respond(200, f'{{"status": "{status}"}}')
            return

        if parsed.path == "/sites":
            self._handle_sites()
            return

        if parsed.path == "/run":
            self._handle_run(parsed)
            return

        if parsed.path == "/run-wp":
            self._handle_run_wp(parsed)
            return

        if parsed.path == "/stop":
            self._handle_stop()
            return

        if parsed.path == "/reset":
            self._handle_reset()
            return

        if parsed.path == "/log":
            self._handle_log(parsed)
            return

        self._respond(404, '{"error": "not found"}')

    def _handle_sites(self):
        sites = _load_sites()
        keys = list(sites.keys())
        self._respond(200, json.dumps({"sites": keys}, ensure_ascii=False))

    def _handle_run(self, parsed):
        global _running
        with _lock:
            if _running:
                self._respond(409, '{"status": "busy", "message": "Already running. Check /status."}')
                return
            _running = True

        params = parse_qs(parsed.query)
        url = params.get("url", [""])[0]
        mid = params.get("mid", ["false"])[0].lower() == "true"
        api = params.get("api", ["false"])[0].lower() == "true"

        if not url:
            with _lock:
                _running = False
            self._respond(400, '{"error": "url parameter is required"}')
            return

        precision = "mid" if mid else "high"
        ai_mode   = "api" if api else "cli"
        self._respond(200, f'{{"status": "started", "precision": "{precision}", "ai_mode": "{ai_mode}"}}')

        threading.Thread(target=self._execute, args=(url, mid, api), daemon=True).start()

    def _handle_run_wp(self, parsed):
        global _running
        with _lock:
            if _running:
                self._respond(409, '{"status": "busy", "message": "Already running. Check /status."}')
                return
            _running = True

        params = parse_qs(parsed.query)
        url    = params.get("url",    [""])[0]
        editor = params.get("editor", ["auto"])[0]
        link   = params.get("link",   [""])[0]
        site   = params.get("site",   [""])[0]
        count  = params.get("count",  [""])[0]

        if not url:
            with _lock:
                _running = False
            self._respond(400, '{"error": "url parameter is required"}')
            return

        # 複数サイト登録済みでsite未指定の場合はサイト一覧を返す
        if not site:
            sites = _load_sites()
            if len(sites) > 1:
                with _lock:
                    _running = False
                keys = list(sites.keys())
                self._respond(200, json.dumps({"status": "site_required", "sites": keys}, ensure_ascii=False))
                return

        self._respond(200, json.dumps({"status": "started", "editor": editor, "link": link, "site": site, "count": count}, ensure_ascii=False))
        threading.Thread(target=self._execute_wp, args=(url, editor, link, site, count), daemon=True).start()

    def _execute_wp(self, url: str, editor: str, link: str, site: str = "", count: str = ""):
        global _running
        try:
            site_arg  = f' --site "{site}"' if site else ""
            count_arg = f' --count {count}' if count else ""
            is_test   = count == "1"
            _sentinel_cleanup()
            if IS_MAC:
                _sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT", "")
                if link:
                    link_select = f'linkMode="{link}"\n'
                else:
                    link_select = (
                        f'echo ""\n'
                        f'echo "リンク形式を選択してください："\n'
                        f'echo "  1. URL挿入（Gutenberg/クラシック自動判定）"\n'
                        f'echo "  2. aタグ形式（テキストリンク）"\n'
                        f'echo ""\n'
                        f'read -p "番号を入力 [1/2]: " linkAns\n'
                        f'if [ "$linkAns" = "2" ]; then linkMode="atag"; else linkMode="url"; fi\n'
                    )
                if is_test:
                    done_msg = (
                        f'echo ""\n'
                        f'echo "1件の処理が完了しました。Spreadsheetで結果を確認し、問題なければCoworkで「一括実行」と送ってください。"\n'
                    )
                else:
                    done_msg = f'echo ""\necho "WP挿入完了。このウィンドウを閉じてください。"\n'
                bash_script = (
                    f'#!/bin/bash\n'
                    f'export GOOGLE_SERVICE_ACCOUNT="{_sa_path}"\n'
                    f'cd "{PROJECT_DIR}"\n'
                    f'{link_select}'
                    f'{PYTHON_CMD} main_wp.py "{url}" --editor {editor} --link $linkMode{site_arg}{count_arg}\n'
                    f'{done_msg}'
                    f'touch "{_SENTINEL}"\n'
                    f'read -p "Enterキーを押して終了..." dummy\n'
                )
                _open_terminal_mac(bash_script)
            else:
                if link:
                    link_select = f'$linkMode = "{link}"; '
                else:
                    link_select = (
                        f'Write-Host ""; '
                        f'Write-Host "リンク形式を選択してください：" -ForegroundColor Cyan; '
                        f'Write-Host "  1. URL挿入（Gutenberg/クラシック自動判定）"; '
                        f'Write-Host "  2. aタグ形式（テキストリンク）"; '
                        f'Write-Host ""; '
                        f'$linkAns = Read-Host "番号を入力 [1/2]"; '
                        f'if ($linkAns -eq "2") {{ $linkMode = "atag" }} else {{ $linkMode = "url" }}; '
                    )
                if is_test:
                    done_msg = (
                        f'Write-Host ""; '
                        f'Write-Host "1件の処理が完了しました。Spreadsheetで結果を確認し、問題なければCoworkで「一括実行」と送ってください。" -ForegroundColor Cyan; '
                    )
                else:
                    done_msg = f'Write-Host ""; Write-Host "WP挿入完了。このウィンドウを閉じてください。" -ForegroundColor Green; '
                ps_cmd = (
                    f'cd "{PROJECT_DIR}"; '
                    f'{link_select}'
                    f'{PYTHON_CMD} main_wp.py "{url}" --editor {editor} --link $linkMode{site_arg}{count_arg}; '
                    f'{done_msg}'
                    f'New-Item -ItemType File -Path "{_SENTINEL}" -Force | Out-Null; '
                    f'Read-Host "Enterキーを押して終了..."'
                )
                subprocess.Popen(
                    ["cmd", "/c", "start", "powershell", "-NoExit", "-Command", ps_cmd],
                )
            _wait_for_sentinel()
        finally:
            with _lock:
                _running = False

    def _handle_reset(self):
        global _running
        _sentinel_cleanup()
        with _lock:
            _running = False
        self._respond(200, '{"status": "reset", "message": "Running flag cleared."}')

    def _handle_stop(self):
        with _lock:
            if not _running:
                self._respond(409, '{"status": "not_running", "message": "No process is currently running."}')
                return
        STOP_FLAG.touch()
        self._respond(200, '{"status": "stop_requested", "message": "Stop signal sent. The process will stop after the current article."}')

    def _execute(self, url: str, mid: bool, api: bool):
        global _running
        try:
            args = [url]
            if mid:
                args.append("--mid")
            if api:
                args.append("--api")
            args_str = " ".join(f'"{a}"' for a in args)
            _sentinel_cleanup()
            if IS_MAC:
                _sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT", "")
                bash_script = (
                    f'#!/bin/bash\n'
                    f'export GOOGLE_SERVICE_ACCOUNT="{_sa_path}"\n'
                    f'cd "{PROJECT_DIR}"\n'
                    f'{PYTHON_CMD} main.py {args_str}\n'
                    f'echo ""\n'
                    f'echo "内部リンクエージェントの処理は完了しました。"\n'
                    f'echo "WordPressへの挿入はCoworkの画面から操作してください。"\n'
                    f'echo ""\n'
                    f'touch "{_SENTINEL}"\n'
                    f'read -p "Enterキーを押して終了..." dummy\n'
                )
                _open_terminal_mac(bash_script)
            else:
                ps_cmd = (
                    f'cd "{PROJECT_DIR}"; '
                    f'{PYTHON_CMD} main.py {args_str}; '
                    f'Write-Host ""; '
                    f'Write-Host "内部リンクエージェントの処理は完了しました。" -ForegroundColor Green; '
                    f'Write-Host "WordPressへの挿入はCoworkの画面から操作してください。" -ForegroundColor Cyan; '
                    f'Write-Host ""; '
                    f'New-Item -ItemType File -Path "{_SENTINEL}" -Force | Out-Null; '
                    f'Read-Host "Enterキーを押して終了..."'
                )
                subprocess.Popen(
                    ["cmd", "/c", "start", "powershell", "-NoExit", "-Command", ps_cmd],
                )
            _wait_for_sentinel()
        finally:
            with _lock:
                _running = False

    def _respond(self, code: int, body: str):
        encoded = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass  # コンソール出力を抑制


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"NYSEO Runner: http://127.0.0.1:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("停止しました。")
