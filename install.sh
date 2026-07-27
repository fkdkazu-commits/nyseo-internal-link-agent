#!/bin/bash
# 内部リンク構築エージェント — Mac 完全インストーラー
# ============================================================
# ターミナルで以下を実行してください：
#   cd "フォルダのパス"
#   bash install.sh
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
STEP_TOTAL=12
ZSHRC="$HOME/.zshrc"
SECRETS_DIR="$HOME/.secrets"
PLIST_PATH="$HOME/Library/LaunchAgents/com.nyseo.runner.plist"

# ============================================================
# ヘルパー関数
# ============================================================
show_header() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$1 $2"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

show_ok()   { echo "  ✔ $1"; }
show_warn() { echo "  ⚠ $1"; }
show_info() { echo "  $1"; }
show_step() { echo "  $1"; }

wait_enter() {
    local prompt="${1:-完了したら Enter を押して次へ進みます...}"
    echo ""
    echo "  >>> $prompt"
    read -r dummy
}

copy_to_clipboard() {
    echo "$1" | pbcopy 2>/dev/null && echo "  ✔ クリップボードにコピーしました（Command+V で貼り付けできます）"
}

# ============================================================
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  NYSEO Cowork自動化エージェント インストーラー   ║"
echo "║  （macOS版）                                     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  以下の機能のインストールを開始します："
echo "    ①  内部リンクエージェント（CSV解析・候補提案）"
echo "    ②  WordPress 内部リンク自動挿入"
echo ""
echo "  自動処理できる部分は自動で行い、手動操作が必要な"
echo "  部分は画面の指示に従って操作し、完了したら Enter を"
echo "  押してください。"
echo ""
read -r -p "  準備ができたら Enter を押してください" dummy


# ============================================================
# STEP 1: Python 確認
# ============================================================
show_header "[1/$STEP_TOTAL]" "[自動] Python のインストール確認"

PY_CMD=""
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    PY_CMD="python3"
    show_ok "Python が見つかりました: $PY_VER"
fi

if [ -z "$PY_CMD" ]; then
    show_warn "Python が見つかりませんでした。インストールが必要です。"
    echo ""
    echo "  【手順】"
    show_step "1. ブラウザで Python の公式サイトを開きます"
    show_step "2. 「Download Python」ボタンをクリックしてダウンロード"
    show_step "3. ダウンロードした .pkg ファイルを実行してインストール"
    show_step "4. インストール完了後、このターミナルに戻る"
    echo ""
    open "https://www.python.org/downloads/" 2>/dev/null || echo "  ブラウザで https://www.python.org/downloads/ を開いてください"
    wait_enter "Python のインストールが完了したら Enter を押してください"

    if command -v python3 &>/dev/null; then
        PY_CMD="python3"
        show_ok "Python を確認しました: $(python3 --version 2>&1)"
    else
        show_warn "Python がまだ認識されていません。ターミナルを再起動してから再実行してください。"
        exit 1
    fi
fi


# ============================================================
# STEP 2: Chrome + Claude 拡張機能
# ============================================================
show_header "[2/$STEP_TOTAL]" "[手動] Google Chrome + Claude 拡張機能"

echo ""
echo "  【確認事項】"
show_step "Google Chrome がインストールされていますか？"
echo ""
echo "  【Chrome がない場合の手順】"
show_step "1. ブラウザで https://www.google.com/chrome/ を開く"
show_step "2. 「Chrome をダウンロード」をクリック"
show_step "3. ダウンロードした .dmg ファイルを開いてインストール"
echo ""
wait_enter "Chrome の準備ができたら Enter を押してください"

echo ""
echo "  【Claude Chrome 拡張機能のインストール】"
echo "  Cowork が動作するために必要な公式拡張機能です。"
echo ""
show_step "1. ブラウザで Chrome ウェブストアの検索ページを開きます"
show_step "2. 「Claude」（Anthropic 製）を探して「Chrome に追加」をクリック"
show_step "3. 確認ダイアログで「拡張機能を追加」をクリック"
show_step "4. Chrome の右上に Claude のアイコン（橙色）が表示されれば完了です"
echo ""
echo "  ⚠️  【重要】インストール後に以下の設定を必ず行ってください"
show_step "1. Cowork 画面の左下のユーザー名をクリック →「設定」を開く"
show_step "2. 「Claude in Chrome」の設定内容を開く"
show_step "3. 「すべてのサイト」のデフォルト項目で「拡張機能を許可」を選択する"
show_warn "この設定をしないと内部リンクエージェント実行時に接続エラーになります"
echo ""
open "https://chromewebstore.google.com/search/Claude" 2>/dev/null || echo "  ブラウザで https://chromewebstore.google.com/search/Claude を開いてください"
wait_enter "Claude 拡張機能のインストールと設定が完了したら Enter を押してください"


# ============================================================
# STEP 3: Cowork（Claude Desktop Pro）のインストール
# ============================================================
show_header "[3/$STEP_TOTAL]" "[手動] Cowork（Claude Desktop Pro）のインストール"

echo ""
echo "  【手順】"
show_step "1. ブラウザで Claude Desktop のダウンロードページを開きます"
show_step "2. 「Download for Mac」をクリックしてダウンロード"
show_step "3. ダウンロードした .dmg ファイルを開き、Claude をアプリケーションフォルダへドラッグ"
show_step "4. 起動して Claude アカウントでログイン"
echo ""
show_info "※ すでにインストール済みの場合はそのまま Enter を押してください"
echo ""
open "https://claude.ai/download" 2>/dev/null || echo "  ブラウザで https://claude.ai/download を開いてください"
wait_enter "Cowork のインストールとログインが完了したら Enter を押してください"


# ============================================================
# STEP 4: Claude CLI ログイン確認
# ============================================================
show_header "[4/$STEP_TOTAL]" "[自動] Claude CLI ログイン確認"

CLAUDE_CMD=""

# 一般的なパスを検索
for p in \
    "$HOME/.claude/local/claude" \
    "/usr/local/bin/claude" \
    "/opt/homebrew/bin/claude" \
    "$HOME/.local/bin/claude"; do
    if [ -x "$p" ]; then
        CLAUDE_CMD="$p"
        break
    fi
done

# Cowork（Claude Desktop）のインストール先を検索
if [ -z "$CLAUDE_CMD" ]; then
    COWORK_DIR="$HOME/Library/Application Support/Claude/claude-code"
    if [ -d "$COWORK_DIR" ]; then
        FOUND=$(find "$COWORK_DIR" -name "claude" -type f 2>/dev/null | sort -V | tail -1)
        if [ -n "$FOUND" ] && [ -x "$FOUND" ]; then
            CLAUDE_CMD="$FOUND"
        fi
    fi
fi

# PATH上のclaudeをフォールバック
if [ -z "$CLAUDE_CMD" ] && command -v claude &>/dev/null; then
    CLAUDE_CMD=$(command -v claude)
fi

# ~/.zshrc を読み込んで再検索
if [ -z "$CLAUDE_CMD" ] && [ -f "$HOME/.zshrc" ]; then
    source "$HOME/.zshrc" 2>/dev/null
    if command -v claude &>/dev/null; then
        CLAUDE_CMD=$(command -v claude)
    fi
fi

# それでも見つからない場合は手動入力
if [ -z "$CLAUDE_CMD" ]; then
    show_warn "claude コマンドが自動検出できませんでした。"
    echo ""
    echo "  別のターミナルで以下を実行してパスを確認してください："
    echo "  which claude"
    echo ""
    read -r -p "  表示されたパスを入力（スキップする場合は Enter）: " MANUAL_PATH
    if [ -n "$MANUAL_PATH" ] && [ -x "$MANUAL_PATH" ]; then
        CLAUDE_CMD="$MANUAL_PATH"
        show_ok "claude を設定しました: $CLAUDE_CMD"
    else
        show_warn "claude コマンドが設定されていません。インストール完了後に手動で確認してください。"
        wait_enter "Enter を押して続けてください"
    fi
fi

if [ -n "$CLAUDE_CMD" ]; then
    show_ok "claude を発見: $CLAUDE_CMD"
    echo ""
    echo "  ログイン状態を確認中..."

    LOGGED_IN=false
    while [ "$LOGGED_IN" = false ]; do
        TEST_RESULT=$("$CLAUDE_CMD" -p "ping" --model "claude-haiku-4-5-20251001" 2>&1)

        if echo "$TEST_RESULT" | grep -qi "not logged in\|please run /login\|not logged"; then
            echo ""
            show_warn "Claude にログインしていません。ログインが必要です。"
            echo ""
            echo "  【手順】"
            show_step "1. 別のターミナルウィンドウを開いて以下を実行："
            echo "     \"$CLAUDE_CMD\""
            show_step "2. 起動後に /login と入力して Enter"
            show_step "3. ブラウザで Claude アカウントにログイン"
            show_step "4. ログイン完了後このウィンドウに戻ってください"
            echo ""
            wait_enter "ログインが完了したら Enter を押してください（再確認します）"
            echo "  再確認中..."
        else
            LOGGED_IN=true
            show_ok "Claude CLI のログインを確認しました"
        fi
    done
fi


# ============================================================
# STEP 5: プロジェクトフォルダの確認
# ============================================================
show_header "[5/$STEP_TOTAL]" "[自動] プロジェクトフォルダの確認"

MISSING_FILES=()
for f in "main.py" "local_runner.py" "install.sh" "requirements.txt" "config.py"; do
    [ ! -f "$PROJECT_DIR/$f" ] && MISSING_FILES+=("$f")
done

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    show_ok "プロジェクトフォルダの確認完了: $PROJECT_DIR"
else
    show_warn "以下のファイルが見つかりません: ${MISSING_FILES[*]}"
    show_warn "プロジェクトフォルダが正しい場所にあるか確認してください。"
    exit 1
fi

# Downloads / デスクトップへの配置警告
if echo "$PROJECT_DIR" | grep -qiE "Downloads|Desktop|デスクトップ|tmp|Temp"; then
    echo ""
    echo "  ⚠  【重要】このフォルダは一時的な場所にあります"
    echo "  現在のパス: $PROJECT_DIR"
    echo ""
    echo "  【推奨】以下のような恒久的な場所にフォルダを移動してから"
    echo "  install.sh を再実行してください："
    echo "  例） $HOME/Documents/nyseo-internal-link-agent"
    echo ""
    read -r -p "  このまま続けますか？（移動してから再実行する場合は N を入力）[Y/N]: " ans
    if [ "$ans" = "N" ] || [ "$ans" = "n" ]; then
        echo "  フォルダを移動してから install.sh を再実行してください。"
        exit 0
    fi
fi


# ============================================================
# STEP 6: Google サービスアカウント JSON の配置
# ============================================================
show_header "[6/$STEP_TOTAL]" "[自動] Google サービスアカウント JSON の配置"

mkdir -p "$SECRETS_DIR"
show_ok ".secrets フォルダを確認しました: $SECRETS_DIR"

SECRETS_SRC="$PROJECT_DIR/secrets"
BUNDLED_JSON=$(find "$SECRETS_SRC" -maxdepth 1 -name "*.json" 2>/dev/null | head -1)
DEFAULT_JSON_PATH=""

if [ -n "$BUNDLED_JSON" ]; then
    JSON_NAME=$(basename "$BUNDLED_JSON")
    cp "$BUNDLED_JSON" "$SECRETS_DIR/$JSON_NAME"
    show_ok "JSON ファイルをコピーしました: $SECRETS_DIR/$JSON_NAME"
    DEFAULT_JSON_PATH="$SECRETS_DIR/$JSON_NAME"
else
    # サービスアカウントJSONかどうかを検証するヘルパー関数
    # 引数: JSONファイルのパス
    # 出力: client_email の値（空なら非該当）
    _get_sa_email() {
        python3 -c "
import json, sys
try:
    d = json.load(open('$1', encoding='utf-8'))
    print(d.get('client_email', ''))
except Exception:
    print('')
" 2>/dev/null
    }

    # ダウンロード・デスクトップ・ドキュメントを自動検索（サービスアカウントJSONのみ）
    AUTO_JSON=""
    AUTO_JSON_EMAIL=""
    for search_dir in "$HOME/Downloads" "$HOME/Desktop" "$HOME/Documents"; do
        while IFS= read -r FOUND; do
            EMAIL=$(_get_sa_email "$FOUND")
            if [ -n "$EMAIL" ]; then
                AUTO_JSON="$FOUND"
                AUTO_JSON_EMAIL="$EMAIL"
                break 2
            fi
        done < <(find "$search_dir" -maxdepth 2 -name "*.json" 2>/dev/null)
    done

    if [ -n "$AUTO_JSON" ]; then
        echo ""
        show_ok "Google サービスアカウント JSON を検出しました:"
        echo "    ファイル: $AUTO_JSON"
        echo "    アカウント: $AUTO_JSON_EMAIL"
        echo ""
        read -r -p "  このファイルを使用しますか？ [Y/N]: " USE_AUTO
        if [ "$USE_AUTO" = "Y" ] || [ "$USE_AUTO" = "y" ]; then
            JSON_NAME=$(basename "$AUTO_JSON")
            cp "$AUTO_JSON" "$SECRETS_DIR/$JSON_NAME"
            show_ok "コピーしました: $SECRETS_DIR/$JSON_NAME"
            DEFAULT_JSON_PATH="$SECRETS_DIR/$JSON_NAME"
        fi
    fi

    if [ -z "$DEFAULT_JSON_PATH" ]; then
        echo ""
        show_warn "Google サービスアカウント JSON が見つかりませんでした。"
        echo ""
        echo "  【手順】"
        show_step "1. 管理者から受け取った .json ファイルを Mac の「ダウンロード」フォルダに入れる"
        show_step "   （メール添付・AirDrop・Slack などで受け取ったファイルを保存してください）"
        show_step "2. 保存したら Enter を押してください（自動でコピーします）"
        echo ""
        wait_enter "JSON ファイルをダウンロードフォルダに入れたら Enter を押してください"

        AUTO_JSON=""
        AUTO_JSON_EMAIL=""
        while IFS= read -r FOUND; do
            EMAIL=$(_get_sa_email "$FOUND")
            if [ -n "$EMAIL" ]; then
                AUTO_JSON="$FOUND"
                AUTO_JSON_EMAIL="$EMAIL"
                break
            fi
        done < <(find "$HOME/Downloads" -maxdepth 2 -name "*.json" 2>/dev/null)

        if [ -n "$AUTO_JSON" ]; then
            JSON_NAME=$(basename "$AUTO_JSON")
            cp "$AUTO_JSON" "$SECRETS_DIR/$JSON_NAME"
            show_ok "コピーしました: $SECRETS_DIR/$JSON_NAME ($AUTO_JSON_EMAIL)"
            DEFAULT_JSON_PATH="$SECRETS_DIR/$JSON_NAME"
        else
            show_warn "まだ見つかりません。インストール完了後に手動で配置してください: $SECRETS_DIR"
            DEFAULT_JSON_PATH="$SECRETS_DIR/agent.json"
        fi
    fi
fi


# ============================================================
# STEP 7: 環境変数の設定
# ============================================================
show_header "[7/$STEP_TOTAL]" "[自動] 環境変数の設定"

echo ""
echo "  [7-1] Google サービスアカウント JSON のパス設定"
CURRENT_SA=$(grep 'GOOGLE_SERVICE_ACCOUNT' "$ZSHRC" 2>/dev/null | tail -1 | sed 's/.*export GOOGLE_SERVICE_ACCOUNT="//' | sed 's/".*//')
[ -n "$CURRENT_SA" ] && echo "  現在の設定: $CURRENT_SA"
echo "  デフォルト: $DEFAULT_JSON_PATH"
read -r -p "  パスを入力（デフォルトのままなら Enter）: " SA_PATH
[ -z "$SA_PATH" ] && SA_PATH="$DEFAULT_JSON_PATH"

if [ -f "$SA_PATH" ]; then
    show_ok "ファイルを確認しました: $SA_PATH"
else
    show_warn "ファイルが見つかりません: $SA_PATH"
    show_warn "パスを後で修正する場合は install.sh を再実行してください"
fi

# ~/.zshrc に書き込む（重複回避）
sed -i '' '/export GOOGLE_SERVICE_ACCOUNT=/d' "$ZSHRC" 2>/dev/null
echo "export GOOGLE_SERVICE_ACCOUNT=\"$SA_PATH\"" >> "$ZSHRC"
export GOOGLE_SERVICE_ACCOUNT="$SA_PATH"
show_ok "GOOGLE_SERVICE_ACCOUNT を ~/.zshrc に設定しました"


# ============================================================
# STEP 8: WordPress サイト情報の設定
# ============================================================
show_header "[8/$STEP_TOTAL]" "[手動] WordPress サイト情報の設定"

SITES_JSON="$SECRETS_DIR/nyseo_sites.json"

echo ""
echo "  WordPress への自動挿入に使用する認証情報を設定します。"
echo "  スプレッドシートごとに対象の WordPress サイトを紐づけます。"
echo "  複数メディアをお持ちの場合は、メディア数分入力してください。"
echo ""

# 既存設定を保持しつつ新規追加
SITES_JSON_CONTENT="{}"
[ -f "$SITES_JSON" ] && SITES_JSON_CONTENT=$(cat "$SITES_JSON")

WP_SETUP_DONE=false
while [ "$WP_SETUP_DONE" = false ]; do
    echo "  ─── WordPress サイト設定 ───"
    echo ""

    read -r -p "  WordPress サイト URL（例: https://example.com）: " WP_URL
    WP_URL="${WP_URL%/}"
    SITE_KEY=$(echo "$WP_URL" | sed -E 's|https?://||' | sed -E 's|/.*||')
    show_ok "サイトキー: $SITE_KEY"

    read -r -p "  WordPress ユーザー名（管理者）: " WP_USER
    echo ""
    echo "  【アプリケーションパスワードの取得手順】"
    show_step "1. WordPress 管理画面にログイン"
    show_step "2. 左メニュー「ユーザー」→「プロフィール」をクリック"
    show_step "3. ページ下部「アプリケーションパスワード」セクションまでスクロール"
    show_step "4. 名前を入力（例：内部リンクエージェント）して「追加」をクリック"
    show_step "5. 表示されたパスワード（xxxx xxxx xxxx の形式）をコピー"
    show_warn "パスワードは作成時に一度しか表示されません"
    echo ""
    read -r -p "  アプリケーションパスワード: " WP_PASS

    # JSONにエントリを追加（pythonで処理）
    SITES_JSON_CONTENT=$($PY_CMD -c "
import json, sys
data = json.loads('''$SITES_JSON_CONTENT''')
data['$SITE_KEY'] = {
    'wp_url': '$WP_URL',
    'wp_user': '$WP_USER',
    'wp_app_password': '$WP_PASS'
}
print(json.dumps(data, ensure_ascii=False, indent=2))
")
    show_ok "設定を追加しました: $WP_URL"
    echo ""

    read -r -p "  別のWordPressサイトを追加しますか？ [Y/N]: " MORE
    if [ "$MORE" != "Y" ] && [ "$MORE" != "y" ]; then
        WP_SETUP_DONE=true
    fi
done

echo "$SITES_JSON_CONTENT" > "$SITES_JSON"
show_ok "サイト設定を保存しました: $SITES_JSON"


# ============================================================
# STEP 9: ライブラリのインストール
# ============================================================
show_header "[9/$STEP_TOTAL]" "[自動] Python ライブラリのインストール"

echo ""
show_info "ライブラリをインストールしています。完了まで数分かかる場合があります..."
show_info "画面が止まっているように見えても処理中ですので、そのままお待ちください。"
echo ""

$PY_CMD -m pip install --upgrade pip --quiet 2>/dev/null
$PY_CMD -m pip install -r "$PROJECT_DIR/requirements.txt" --no-warn-script-location -q

if [ $? -eq 0 ]; then
    echo ""
    show_ok "ライブラリのインストールが完了しました"
else
    echo ""
    show_warn "インストール中にエラーが発生しました。"
    show_warn "ログを確認するには以下を実行してください："
    echo "  $PY_CMD -m pip install -r \"$PROJECT_DIR/requirements.txt\""
    wait_enter "確認したら Enter を押して続けてください"
fi


# ============================================================
# STEP 10: ランナーサーバーの登録・起動（launchd）
# ============================================================
show_header "[10/$STEP_TOTAL]" "[自動] ランナーサーバーの登録・起動"

PY_PATH=$(command -v "$PY_CMD")

# LaunchAgent plist を作成
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nyseo.runner</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PY_PATH</string>
        <string>$PROJECT_DIR/local_runner.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>GOOGLE_SERVICE_ACCOUNT</key>
        <string>$SA_PATH</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/runner.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/runner.log</string>
</dict>
</plist>
PLIST

mkdir -p "$PROJECT_DIR/logs"
show_ok "LaunchAgent を登録しました: $PLIST_PATH"

# 既存プロセスを停止してから起動
launchctl unload "$PLIST_PATH" 2>/dev/null
launchctl load "$PLIST_PATH"
show_info "ランナーサーバーを起動しています..."
sleep 3

# 確認
SERVER_OK=false
for i in 1 2 3 4 5; do
    RESP=$(curl -s --max-time 3 "http://127.0.0.1:8765/status" 2>/dev/null)
    if echo "$RESP" | grep -q "idle"; then
        show_ok "ランナーサーバーが起動しました: $RESP"
        SERVER_OK=true
        break
    fi
    echo "  待機中... ($i/5)"
    sleep 2
done

if [ "$SERVER_OK" = false ]; then
    show_warn "サーバーの起動確認ができませんでした。"
    show_warn "ブラウザで http://127.0.0.1:8765/status を開いて確認してください。"
fi


# ============================================================
# STEP 11: Cowork プロジェクトの作成
# ============================================================
show_header "[11/$STEP_TOTAL]" "[手動] Cowork プロジェクトの作成"
echo ""
echo "  Cowork（Claude Desktop Pro）でエージェント用プロジェクトを作成します。"
echo ""
echo "  【手順】"
show_step "1. Cowork を起動する（まだ開いていない場合）"
show_step "2. 左サイドバーの「Projects」をクリックする"
show_step "3. 「+ New project」をクリックする"
show_step "4. プロジェクト名に「内部リンクエージェント」と入力して作成する"
show_step "5. 「Project instructions」の入力欄を開く"
show_step "6. 下に表示される指示文をコピーして貼り付ける（Command+V）"
show_step "7. 保存する"
echo ""
echo "  ─── ここから指示文（全文コピーして貼り付け）───────────"
echo ""
INSTRUCTION_TEXT="# 内部リンク構築AIエージェント — Cowork実行手順

## プロジェクト設定（パスを変更する場合はここを編集）

\`\`\`
PROJECT_DIR : $PROJECT_DIR
RUNNER_URL  : http://127.0.0.1:8765
\`\`\`

## このエージェントの目的
SEOツールから出力したSpreadsheetを読み込み、被リンク不足記事（E列≤1）に対して
関連性の高い他記事から内部リンクを設置する候補を自動提案する。
さらにSpreadsheetの承認済み候補をWordPress記事に自動挿入する機能も持つ。

## Coworkからの実行方法

---

### ■ パターン1：内部リンクエージェントを実行する

ユーザーが「内部リンクを作ってほしい」「エージェントを実行して」などと伝えたら以下を実行する。

**STEP 1：精度モードの選択**

> 精度モードを選択してください。
> - **高精度**（推奨）: KWをトークン単位で分割してスコアリング。候補記事を多く拾いやすい。
> - **中精度**: KW全体の文字列一致のみ。高速だが複合KWで候補が少なくなる場合がある。

**STEP 2：ランナーサーバーの確認と実行**

① サーバーの状態確認

Claude in Chrome を使って以下のURLを開く：
http://127.0.0.1:8765/status

- {\"status\": \"idle\"} → STEP 2② へ進む
- {\"status\": \"running\"} → 「現在別の処理が実行中です。完了後に再度お試しください。」とユーザーに伝える
- Chrome拡張機能に接続できない場合 → すぐに以下をユーザーに提示してブラウザで直接開いてもらう（Chromeの確認は不要）：
  「① まずサーバー確認：http://127.0.0.1:8765/status
   → {\"status\": \"idle\"} が表示されたら次のURLを開いてください。
   ② 実行（高精度モード）：http://127.0.0.1:8765/run?url=<URL>&mid=false&api=false
   → {\"status\": \"started\"} が返ってきたら処理開始です。」
  サーバー自体が起動していない場合のみ：
  「ターミナルで以下を実行してください：python3 \"$PROJECT_DIR/local_runner.py\"」

② 実行リクエストを送信（Chrome接続時）

精度モードの選択結果に応じて Claude in Chrome で以下のURLを開く：
| 精度 | URL |
|------|-----|
| 高精度 | http://127.0.0.1:8765/run?url=<URL>&mid=false&api=false |
| 中精度 | http://127.0.0.1:8765/run?url=<URL>&mid=true&api=false |

<URL> はユーザーから受け取ったSpreadsheetのURLをそのまま入れる。

{\"status\": \"started\"} が返ってきたら：
「実行を開始しました。処理完了後にSpreadsheetのH〜M列に候補が書き込まれます。
ターミナルウィンドウに『完了しました』と表示されたら教えてください。」

**STEP 3：完了待ちとWP挿入確認**

statusのポーリングは行わない。
ユーザーから「完了しました」が送られてくるまで待機する。

完了の報告を受けたら、必ず以下を確認する：

「処理が完了しました。WordPressへの自動挿入も続けますか？
・はい → スプレッドシートを確認せずにそのまま挿入します
・いいえ → スプレッドシートでH〜M列を確認・承認してから、このチャットで『WP挿入して』と送ってください」

「はい」の場合 → パターン2のWP挿入手順を実行する
「いいえ」の場合 → 「H〜M列を確認・承認したら、このチャットで『WP挿入して』と送ってください。」と伝えて終了する

---

### ■ パターン2：WordPressに挿入する

ユーザーが「WordPressに挿入してほしい」「WP挿入を実行して」などと伝えたら以下を実行する。
SpreadsheetのH〜M列のレビュー・承認が完了している前提で進める。

**STEP 1：対象サイトの確認（複数サイト登録時のみ）**

Claude in Chrome で以下のURLを開いてサイト一覧を取得する：
http://127.0.0.1:8765/sites

- サイトが1件のみ → 確認不要。そのままSTEP 2へ。
- サイトが2件以上 → 以下を確認する：
  「どのWordPressサイトに挿入しますか？
  ・site-a.com
  ・site-b.com」

**STEP 2：リンク形式の確認**

> 挿入するリンクの形式を教えてください：
> 1. URL挿入（Gutenberg/クラシック自動判定）※ブログカード表示はテーマ依存
> 2. aタグ（テキストリンク・Gutenberg/クラシック両対応）

※エディタ形式（クラシック / Gutenberg）は記事ごとに自動判定されるため確認不要。

**STEP 3：実行範囲の確認**

> まず1記事のみテスト実行しますか？それとも一括実行しますか？
> ・1記事のみ → 先頭の未処理行を1件だけ処理します。表示結果を確認してから一括実行してください。
> ・一括実行 → すべての未処理行を処理します。

**STEP 4：WP挿入リクエストを送信**

選択に応じて Claude in Chrome で以下のURLを開く：
| リンク形式 | 実行範囲 | URL |
|------|------|-----|
| 1. URL挿入 | 1記事のみ | http://127.0.0.1:8765/run-wp?url=<URL>&link=url&count=1 |
| 1. URL挿入 | 一括 | http://127.0.0.1:8765/run-wp?url=<URL>&link=url |
| 2. aタグ | 1記事のみ | http://127.0.0.1:8765/run-wp?url=<URL>&link=atag&count=1 |
| 2. aタグ | 一括 | http://127.0.0.1:8765/run-wp?url=<URL>&link=atag |

複数サイトの場合は末尾に &site=<domain> を追加する：
例）http://127.0.0.1:8765/run-wp?url=<URL>&link=url&site=example.com

run-wp が {\"status\": \"site_required\"} を返した場合は、
ユーザーにサイトを確認してから &site=<domain> を付けて再度リクエストを送る。

<URL> はユーザーから受け取ったSpreadsheetのURLをそのまま入れる。

{\"status\": \"started\"} が返ってきたら：
- 1記事のみの場合：「1件処理します。完了後にSpreadsheetとWordPressのプレビューで表示を確認してください。問題なければ「一括実行」と送ってください。※挿入内容がおかしい場合はツール販売元（NYマーケティング：seo@ny-marketing.co.jp）までお問い合わせください。」
- 一括の場合：「WP挿入を開始しました。完了後にSpreadsheetのN列でステータスを確認できます。」

1記事テスト後にユーザーが「一括実行」と送ってきたら、パターン2のSTEP 4を再度実行する（count=1を外して一括実行）。

---

### ■ 処理の中断

処理中にユーザーが「止めて」「中断して」などと伝えた場合：

Claude in Chrome で以下のURLを開く：
http://127.0.0.1:8765/stop

{\"status\": \"stop_requested\"} が返ってきたら：
「中断シグナルを送信しました。現在処理中の記事が完了した後に停止します。Spreadsheetで処理済み記事（H列にデータあり）を確認できます。」

---

### ■ 処理の再開

中断後にユーザーが再開を希望した場合：
- 通常通り STEP 1〜2 を実施してSpreadsheet URLを送信するだけでよい
- H列が空白の記事だけが対象になるため、自動的に続きから処理される

---

## ルール
- APIキー・認証情報はプロジェクトフォルダ外に保管すること
- 外部サイトへのHTTPリクエストはGET取得のみ
- エラーが発生した記事はスキップして処理を継続する
- H列にすでにデータがある記事は処理済みとしてスキップする
- N列に値が記録されている行はWP挿入をスキップする（冪等性あり）
- ファイルやフォルダの作成・編集は絶対に行わない。コードの実行も行わない。ユーザーへの案内のみ行う
- ランナーサーバーに接続できない場合は、ユーザーに手動起動を案内するだけでよい。自分でサーバーを構築しようとしてはならない
- URLのパラメータ名は必ず mid と api（内部リンク）、link（WP挿入）を使うこと
- レビューを省略した連続実行はリスクがある旨をユーザーに伝えること"
echo "$INSTRUCTION_TEXT"
echo ""
echo "  ─── 指示文ここまで ────────────────────────────────"
echo ""

copy_to_clipboard "$INSTRUCTION_TEXT"
wait_enter "Cowork プロジェクトの作成・指示文の貼り付けが完了したら Enter を押してください"


# ============================================================
# STEP 12: Spreadsheet の準備
# ============================================================
show_header "[12/$STEP_TOTAL]" "[手動] Google Spreadsheet の準備"

# サービスアカウントのメールアドレスを JSON から取得
SA_EMAIL=""
if [ -f "$SA_PATH" ]; then
    SA_EMAIL=$($PY_CMD -c "import json; d=json.load(open('$SA_PATH')); print(d.get('client_email',''))" 2>/dev/null)
fi

echo ""
echo "  ツールが読み込む Google Spreadsheet を準備します。"
echo ""
echo "  【手順 1】Spreadsheet を新規作成する"
show_step "1. ブラウザで Google ドライブ（drive.google.com）を開く"
show_step "2. 「+ 新規」→「Google スプレッドシート」をクリック"
show_step "3. シート名は任意でOK（例：内部リンク管理）"
echo ""
wait_enter "Spreadsheet を作成したら Enter を押してください"

echo ""
echo "  【手順 2】データを Spreadsheet に用意する"
show_info "記事データのインポート方法は管理者から別途案内があります。"
show_info "インポート後、以下の列構成になっているか確認してください。"
echo ""
echo "  【列構成の確認】以下の列順になっているか確認してください"
echo "  ┌────┬──────────────┬──────────────────────────────────┐"
echo "  │ 列 │ 内容         │ 備考                             │"
echo "  ├────┼──────────────┼──────────────────────────────────┤"
echo "  │ A  │ NO           │ 記事番号                         │"
echo "  │ B  │ 記事URL      │ 処理対象のURL                    │"
echo "  │ C  │ メインKW     │ キーワード（空欄可）             │"
echo "  │ D  │ 発リンク数   │                                  │"
echo "  │ E  │ 被リンク数   │ ★ 1以下の記事が処理対象         │"
echo "  │ F  │ クリック数   │                                  │"
echo "  │ G  │ 表示回数     │                                  │"
echo "  │H〜M│ 出力欄       │ ツールが自動入力（空欄のままでOK）│"
echo "  └────┴──────────────┴──────────────────────────────────┘"
echo ""
show_warn "列の順番が違う場合は列を並び替えてから次へ進んでください"
echo ""
wait_enter "列構成の確認が完了したら Enter を押してください"

echo ""
echo "  【手順 3】サービスアカウントに編集権限を付与する"
show_step "1. Spreadsheet 右上の「共有」ボタンをクリック"
show_step "2. 以下のメールアドレスを入力して追加する"
echo ""
if [ -n "$SA_EMAIL" ]; then
    echo "  ┌─────────────────────────────────────────────────────┐"
    echo "  │  $SA_EMAIL"
    echo "  └─────────────────────────────────────────────────────┘"
    copy_to_clipboard "$SA_EMAIL"
else
    show_warn "サービスアカウントのメールアドレスを取得できませんでした。"
    show_warn "管理者から受け取った JSON ファイルを開き「client_email」の値を入力してください。"
fi
echo ""
show_step "3. 権限を「閲覧者」→「編集者」に変更する"
show_step "4. 「送信」をクリック（通知メールは送らなくてOK）"
echo ""
wait_enter "共有設定が完了したら Enter を押してください"

echo ""
echo "  【手順 4】Spreadsheet の URL をコピーする"
show_step "ブラウザのアドレスバーの URL をコピーしておいてください"
show_info "（例：https://docs.google.com/spreadsheets/d/XXXXXXX/edit）"
show_info "このURLをCoworkのチャットに貼り付けると処理が始まります"
echo ""
wait_enter "URL のコピーが完了したら Enter を押してください"


# ============================================================
# 完了
# ============================================================
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║           セットアップ完了！                     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  ✔ Python                    インストール済み"
echo "  ✔ Chrome + Claude拡張機能   インストール済み"
echo "  ✔ Cowork                    インストール済み"
echo "  ✔ Claude CLI ログイン        確認済み"
echo "  ✔ Python ライブラリ          インストール済み"
echo "  ✔ 環境変数                  ~/.zshrc に設定済み"
echo "  ✔ WordPress サイト設定       登録済み"
echo "  ✔ 自動起動                  LaunchAgent 登録済み"
echo "  ✔ ランナーサーバー           $([ "$SERVER_OK" = true ] && echo '起動済み' || echo '要確認')"
echo "  ✔ Cowork プロジェクト        作成済み"
echo "  ✔ Spreadsheet               準備済み"
echo ""
echo "  【次回からの使い方】"
echo "  1. Cowork を開いて「内部リンクエージェント」プロジェクトを選択"
echo "  2. チャット欄に Spreadsheet の URL を貼り付けて送信"
echo "  3. 精度モードを選択すると処理が自動で始まります"
echo ""
echo "  ランナーサーバーは Mac 起動時に自動で立ち上がります。"
echo "  設定変更は install.sh を再実行してください。"
echo ""
echo "  ※ 環境変数を反映するには一度ターミナルを再起動してください："
echo "     source ~/.zshrc"
echo ""
read -r -p "  Enter を押して終了" dummy
