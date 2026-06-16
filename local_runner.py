"""
NYSEO ローカルランナーサーバー
Cowork (Claude in Chrome) から main.py / main_wp.py を起動するための橋渡し。
ポート 8765 で待機し、Chrome からの GET リクエストを受け取る。

エンドポイント:
  GET /status                          現在の実行状態を返す
  GET /run?url=...                     main.py を実行開始する
       &mid=true/false                  中精度モード（省略時=false=高精度）
       &api=true/false                  APIモード（省略時=false=CLIモード）
  GET /run-wp?url=...                  main_wp.py を実行開始する（v1.3〜）
       &editor=classic|gutenberg        エディタ形式
       &link=url|atag                   リンク形式
  GET /stop                            実行中の処理を停止する
"""

import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_DIR = Path(__file__).parent
LOG_FILE    = PROJECT_DIR / "logs" / "latest.log"
STOP_FLAG   = PROJECT_DIR / "stop.flag"
PORT = 8765

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

        if parsed.path == "/run":
            self._handle_run(parsed)
            return

        if parsed.path == "/run-wp":
            self._handle_run_wp(parsed)
            return

        if parsed.path == "/stop":
            self._handle_stop()
            return

        if parsed.path == "/log":
            self._handle_log(parsed)
            return

        self._respond(404, '{"error": "not found"}')

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
        editor = params.get("editor", ["classic"])[0]
        link   = params.get("link",   ["url"])[0]

        if not url:
            with _lock:
                _running = False
            self._respond(400, '{"error": "url parameter is required"}')
            return

        self._respond(200, f'{{"status": "started", "editor": "{editor}", "link": "{link}"}}')
        threading.Thread(target=self._execute_wp, args=(url, editor, link), daemon=True).start()

    def _execute_wp(self, url: str, editor: str, link: str):
        global _running
        try:
            ps_cmd = (
                f'cd "{PROJECT_DIR}"; '
                f'py main_wp.py "{url}" --editor {editor} --link {link}; '
                f'Write-Host ""; Write-Host "WP挿入完了。このウィンドウを閉じてください。" -ForegroundColor Green; '
                f'pause'
            )
            subprocess.Popen(
                ["cmd", "/c", "start", "powershell", "-NoExit", "-Command", ps_cmd],
            )
        finally:
            with _lock:
                _running = False

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
            ps_cmd = (
                f'cd "{PROJECT_DIR}"; '
                f'py main.py {args_str}; '
                f'Write-Host ""; '
                f'Write-Host "内部リンクエージェントの処理は完了しました。" -ForegroundColor Green; '
                f'Write-Host ""; '
                f'$wpAns = Read-Host "続けてWP挿入を開始しますか？ [Y/N]"; '
                f'if ($wpAns -eq "Y" -or $wpAns -eq "y") {{ '
                f'Write-Host ""; '
                f'Write-Host "リンク形式を選択してください：" -ForegroundColor Cyan; '
                f'Write-Host "  1. URLのみ（WordPressがブログカードに自動展開）"; '
                f'Write-Host "  2. aタグ形式"; '
                f'$linkAns = Read-Host "番号を入力 [1/2]"; '
                f'if ($linkAns -eq "2") {{ $linkMode = "atag" }} else {{ $linkMode = "url" }}; '
                f'Write-Host ""; '
                f'Write-Host "WP挿入を開始します..." -ForegroundColor Cyan; '
                f'py main_wp.py "{url}" --link $linkMode; '
                f'Write-Host ""; '
                f'Write-Host "WP挿入完了。このウィンドウを閉じてください。" -ForegroundColor Green '
                f'}} else {{ '
                f'Write-Host "完了しました。このウィンドウを閉じてください。" -ForegroundColor Green '
                f'}}; '
                f'pause'
            )
            subprocess.Popen(
                ["cmd", "/c", "start", "powershell", "-NoExit", "-Command", ps_cmd],
            )
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
