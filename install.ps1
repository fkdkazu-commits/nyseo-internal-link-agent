# 内部リンク構築エージェント — 完全インストーラー
# ============================================================
# クライアント PC への初回セットアップを一括で案内します。
# PowerShell で以下を実行してください：
#   cd "フォルダのパス"
#   .\install.ps1
# ============================================================

$PROJECT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$STEP_TOTAL  = 10

function Show-Header {
    param([string]$Step, [string]$Title, [string]$Mode = "auto")
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    $modeLabel = if ($Mode -eq "auto") { "[自動]" } else { "[手動]" }
    $modeColor = if ($Mode -eq "auto") { "Cyan" } else { "Yellow" }
    Write-Host "$Step $modeLabel $Title" -ForegroundColor $modeColor
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
}

function Wait-Enter {
    param([string]$Prompt = "完了したら Enter を押して次へ進みます...")
    Write-Host ""
    Write-Host "  >>> $Prompt" -ForegroundColor Magenta
    Read-Host | Out-Null
}

function Show-Ok   { param([string]$msg) Write-Host "  ✔ $msg" -ForegroundColor Green }
function Show-Warn { param([string]$msg) Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Show-Info { param([string]$msg) Write-Host "  $msg" -ForegroundColor Gray }
function Show-Step { param([string]$msg) Write-Host "  $msg" -ForegroundColor White }

# ============================================================
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║      内部リンク構築エージェント インストーラー   ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  このスクリプトがインストールの全工程を案内します。" -ForegroundColor Gray
Write-Host "  自動処理できる部分は自動で行い、手動操作が必要な" -ForegroundColor Gray
Write-Host "  部分は画面の指示に従って操作し、完了したら Enter を" -ForegroundColor Gray
Write-Host "  押してください。" -ForegroundColor Gray
Write-Host ""
Read-Host "  準備ができたら Enter を押してください"


# ============================================================
# STEP 1: Python 確認
# ============================================================
Show-Header "[$([string]1)/$STEP_TOTAL]" "Python のインストール確認"

$pyCmd = $null
try {
    $pyVer = (py --version 2>&1).ToString()
    if ($pyVer -match "Python (\d+\.\d+)") {
        $pyCmd = "py"
        Show-Ok "Python が見つかりました: $pyVer"
    }
} catch {}

if (-not $pyCmd) {
    try {
        $pyVer = (python --version 2>&1).ToString()
        if ($pyVer -match "Python (\d+\.\d+)") {
            $pyCmd = "python"
            Show-Ok "Python が見つかりました: $pyVer"
        }
    } catch {}
}

if (-not $pyCmd) {
    Show-Warn "Python が見つかりませんでした。インストールが必要です。"
    Write-Host ""
    Write-Host "  【手順】" -ForegroundColor Yellow
    Show-Step "1. 今からブラウザで Python の公式サイトを開きます"
    Show-Step "2. 黄色の「Download Python」ボタンをクリックしてダウンロード"
    Show-Step "3. ダウンロードしたファイル（python-3.x.x-amd64.exe）を実行"
    Show-Step "4. インストール画面で必ず"
    Write-Host "       ★ 「Add Python to PATH」にチェックを入れてから「Install Now」をクリック" -ForegroundColor Yellow
    Show-Step "5. インストール完了後、このウィンドウに戻る"
    Write-Host ""
    Start-Process "https://www.python.org/downloads/"
    Wait-Enter "Python のインストールが完了したら Enter を押してください"

    # 再確認
    try { $pyCmd = "py"; py --version 2>&1 | Out-Null } catch {}
    try { $pyCmd = "python"; python --version 2>&1 | Out-Null } catch { $pyCmd = $null }
    if ($pyCmd) {
        Show-Ok "Python を確認しました。"
    } else {
        Show-Warn "Python がまだ認識されていません。PowerShell を一度閉じて再起動してから実行し直してください。"
        Read-Host "Enter で終了"
        exit 1
    }
}


# ============================================================
# STEP 2: Chrome + Claude 拡張機能（手動）
# ============================================================
Show-Header "[$([string]2)/$STEP_TOTAL]" "Google Chrome + Claude 拡張機能" "manual"

Write-Host ""
Write-Host "  【確認事項】" -ForegroundColor Yellow
Show-Step "Google Chrome がインストールされていますか？"
Write-Host "  → インストールされていない場合は以下の手順でインストールしてください。" -ForegroundColor Gray
Write-Host ""
Write-Host "  【Chrome がない場合の手順】" -ForegroundColor Yellow
Show-Step "1. ブラウザ（Edge など）で https://www.google.com/chrome/ を開く"
Show-Step "2. 「Chrome をダウンロード」をクリック"
Show-Step "3. ダウンロードしたファイルを実行してインストール"
Show-Step "4. Chrome を起動して、Chrome をデフォルトブラウザに設定する"
Show-Step "   設定 → アプリ → 既定のアプリ → ブラウザ → Google Chrome"
Write-Host ""

Wait-Enter "Chrome の準備ができたら Enter を押してください"

Write-Host ""
Write-Host "  【Claude Chrome 拡張機能のインストール】" -ForegroundColor Yellow
Show-Step "1. 今からブラウザで Claude 拡張機能のページを開きます"
Show-Step "2. 「Chrome に追加」をクリック"
Show-Step "3. 確認ダイアログで「拡張機能を追加」をクリック"
Show-Step "4. Chrome の右上にパズルピースのアイコンが表示され、"
Show-Step "   その中に Claude のアイコンが追加されれば完了です"
Write-Host ""
Start-Process "https://chromewebstore.google.com/detail/claude/pelmddgbnokbkggeiophnkgmfbdljbfa"

Wait-Enter "Claude 拡張機能のインストールが完了したら Enter を押してください"


# ============================================================
# STEP 3: Cowork（Claude Desktop Pro）のインストール（手動）
# ============================================================
Show-Header "[$([string]3)/$STEP_TOTAL]" "Cowork（Claude Desktop Pro）のインストール" "manual"

Write-Host ""
Write-Host "  【手順】" -ForegroundColor Yellow
Show-Step "1. 今からブラウザで Claude Desktop のダウンロードページを開きます"
Show-Step "2. 「Download for Windows」をクリックしてダウンロード"
Show-Step "3. ダウンロードしたファイル（Claude-Setup-x64.exe など）を実行"
Show-Step "4. 画面の指示に従ってインストール完了"
Show-Step "5. 起動して Claude アカウントでログイン"
Write-Host ""
Show-Info "※ すでにインストール済みの場合はそのまま Enter を押してください"
Write-Host ""
Start-Process "https://claude.ai/download"

Wait-Enter "Cowork のインストールとログインが完了したら Enter を押してください"


# ============================================================
# STEP 4: プロジェクトフォルダの確認（自動）
# ============================================================
Show-Header "[$([string]4)/$STEP_TOTAL]" "プロジェクトフォルダの確認"

$requiredFiles = @("main.py", "local_runner.py", "setup_once.ps1", "requirements.txt", "config.py")
$missing = @()
foreach ($f in $requiredFiles) {
    if (-not (Test-Path (Join-Path $PROJECT_DIR $f))) {
        $missing += $f
    }
}

if ($missing.Count -eq 0) {
    Show-Ok "プロジェクトフォルダの確認完了: $PROJECT_DIR"
} else {
    Show-Warn "以下のファイルが見つかりません: $($missing -join ', ')"
    Show-Warn "プロジェクトフォルダが正しい場所にあるか確認してください。"
    Read-Host "Enter で終了"
    exit 1
}


# ============================================================
# STEP 5: Google サービスアカウント JSON の配置確認（手動）
# ============================================================
Show-Header "[$([string]5)/$STEP_TOTAL]" "Google サービスアカウント JSON の配置" "manual"

$defaultJsonName = "nyseo-agent-3a445eba0003.json"
$defaultSecretsDir = "$env:USERPROFILE\.secrets"
$defaultJsonPath = Join-Path $defaultSecretsDir $defaultJsonName

Write-Host ""
Write-Host "  管理者から受け取った JSON ファイルを配置してください。" -ForegroundColor Yellow
Write-Host ""
Write-Host "  【推奨の配置場所】" -ForegroundColor Yellow
Write-Host "  $defaultJsonPath" -ForegroundColor White
Write-Host ""
Write-Host "  【手順】" -ForegroundColor Yellow
Show-Step "1. エクスプローラーで以下のフォルダを開く（なければ新規作成）"
Write-Host "     $defaultSecretsDir" -ForegroundColor White
Show-Step "2. 管理者から受け取った JSON ファイルをそのフォルダにコピー"
Show-Step "3. ファイル名が「$defaultJsonName」であることを確認"
Write-Host ""
Show-Info "別の場所に置く場合は、次のステップで正しいパスを入力してください"

# .secrets フォルダを自動作成
if (-not (Test-Path $defaultSecretsDir)) {
    New-Item -ItemType Directory -Path $defaultSecretsDir | Out-Null
    Show-Ok ".secrets フォルダを作成しました: $defaultSecretsDir"
}

# エクスプローラーで .secrets を開く
Start-Process "explorer.exe" $defaultSecretsDir

Wait-Enter "JSON ファイルの配置が完了したら Enter を押してください"


# ============================================================
# STEP 6: 環境変数の設定（自動）
# ============================================================
Show-Header "[$([string]6)/$STEP_TOTAL]" "環境変数の設定"

# [6-1] Google サービスアカウント
Write-Host ""
Write-Host "  [6-1] Google サービスアカウント JSON のパス設定" -ForegroundColor Cyan
$currentSa = [System.Environment]::GetEnvironmentVariable("GOOGLE_SERVICE_ACCOUNT", "User")
if ($currentSa) {
    Write-Host "  現在の設定: $currentSa" -ForegroundColor Gray
}
Write-Host "  デフォルト: $defaultJsonPath" -ForegroundColor Gray
$saPath = Read-Host "  パスを入力（デフォルトのままなら Enter）"
if (-not $saPath) { $saPath = $defaultJsonPath }

if (Test-Path $saPath) {
    Show-Ok "ファイルを確認しました: $saPath"
} else {
    Show-Warn "ファイルが見つかりません: $saPath"
    Show-Warn "パスを後で修正する場合は setup_once.ps1 を再実行してください"
}
[System.Environment]::SetEnvironmentVariable("GOOGLE_SERVICE_ACCOUNT", $saPath, "User")
Show-Ok "GOOGLE_SERVICE_ACCOUNT を設定しました"

# [6-2] Anthropic API キー（任意）
Write-Host ""
Write-Host "  [6-2] Anthropic API キーの設定（APIモード使用時のみ）" -ForegroundColor Cyan
Write-Host "  CLIモードのみ使用する場合は Enter でスキップしてください。" -ForegroundColor Gray
Write-Host "  APIモード（5並列・高速）を使う場合は sk-ant-... 形式のキーを入力します。" -ForegroundColor Gray

$currentKey = [System.Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
if ($currentKey) {
    $last4 = $currentKey.Substring([Math]::Max(0, $currentKey.Length - 4))
    Write-Host "  現在設定済み（末尾: ...$last4）" -ForegroundColor Gray
    $update = Read-Host "  変更しますか？（y で変更 / Enter でスキップ）"
    if ($update -eq "y") {
        $apiKey = Read-Host "  新しい API キー (sk-ant-...)"
    }
} else {
    $apiKey = Read-Host "  API キー（sk-ant-... / CLIモードのみなら Enter でスキップ）"
}

if ($apiKey) {
    [System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $apiKey, "User")
    Show-Ok "ANTHROPIC_API_KEY を設定しました"
} else {
    if (-not $currentKey) {
        Show-Info "スキップしました（CLIモードのみで動作します）"
    } else {
        Show-Info "変更しませんでした"
    }
}


# ============================================================
# STEP 7: ライブラリのインストール（自動）
# ============================================================
Show-Header "[$([string]7)/$STEP_TOTAL]" "Python ライブラリのインストール"

Write-Host ""
Show-Info "pip install -r requirements.txt を実行しています..."
Write-Host ""

$reqFile = Join-Path $PROJECT_DIR "requirements.txt"
& $pyCmd -m pip install -r $reqFile

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Show-Ok "ライブラリのインストールが完了しました"
} else {
    Write-Host ""
    Show-Warn "インストール中にエラーが発生した可能性があります。"
    Show-Warn "上記のエラーメッセージを確認してください。"
    Wait-Enter "確認したら Enter を押して続けてください"
}


# ============================================================
# STEP 8: スタートアップ登録 + ランナーサーバー起動（自動）
# ============================================================
Show-Header "[$([string]8)/$STEP_TOTAL]" "ランナーサーバーの登録・起動"

# スタートアップ登録
$pyPath = (Get-Command $pyCmd -ErrorAction SilentlyContinue).Source
if (-not $pyPath) { $pyPath = $pyCmd }
$runnerScript = Join-Path $PROJECT_DIR "local_runner.py"
$startupDir   = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$startupBat   = Join-Path $startupDir "nyseo_runner.bat"
$batContent   = "@echo off`r`nstart `"`" /min `"$pyPath`" `"$runnerScript`"`r`n"
[System.IO.File]::WriteAllText($startupBat, $batContent, [System.Text.Encoding]::ASCII)
Show-Ok "Windows 起動時の自動起動を登録しました"

# 既存プロセスを停止
Get-Process -Name "python", "py" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*local_runner*" } |
    Stop-Process -Force -ErrorAction SilentlyContinue

# 起動
Start-Process -FilePath $pyPath -ArgumentList "`"$runnerScript`"" -WindowStyle Hidden
Write-Host ""
Show-Info "ランナーサーバーを起動しています..."
Start-Sleep -Seconds 3

# 確認
$serverOk = $false
for ($i = 1; $i -le 5; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8765/status" -UseBasicParsing -TimeoutSec 3
        if ($resp.Content -match "idle") {
            Show-Ok "ランナーサーバーが起動しました: $($resp.Content)"
            $serverOk = $true
            break
        }
    } catch {}
    Write-Host "  待機中... ($i/5)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

if (-not $serverOk) {
    Show-Warn "サーバーの起動確認ができませんでした。"
    Show-Warn "ブラウザで http://127.0.0.1:8765/status を開いて確認してください。"
}


# ============================================================
# STEP 9: Cowork プロジェクトの作成（手動）
# ============================================================
Show-Header "[$([string]9)/$STEP_TOTAL]" "Cowork プロジェクトの作成" "manual"

$safeProjectDir = $PROJECT_DIR -replace '\\', '\\'

Write-Host ""
Write-Host "  Cowork（Claude Desktop Pro）でエージェント用プロジェクトを作成します。" -ForegroundColor Yellow
Write-Host ""
Write-Host "  【手順】" -ForegroundColor Yellow
Show-Step "1. Cowork を起動する（まだ開いていない場合）"
Show-Step "2. 左サイドバーの「Projects」をクリックする"
Show-Step "3. 「+ New project」をクリックする"
Show-Step "4. プロジェクト名に「内部リンクエージェント」と入力して作成する"
Show-Step "5. 「Project instructions」の入力欄を開く"
Show-Step "6. 下に表示される指示文をコピーして貼り付ける（Ctrl+V）"
Show-Step "7. 保存する"
Write-Host ""
Write-Host "  ┌─────────────────────────────────────────────────────┐" -ForegroundColor DarkGray
Write-Host "  │ ⚠  貼り付け前に PROJECT_DIR のパスを書き換えてください │" -ForegroundColor Yellow
Write-Host "  │    現在のパス: $PROJECT_DIR" -ForegroundColor Yellow
Write-Host "  └─────────────────────────────────────────────────────┘" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  ─── ここから指示文（全文コピーして貼り付け）───────────" -ForegroundColor DarkGray
Write-Host ""

$instructionText = @"
# 内部リンク構築AIエージェント — Cowork実行手順

## プロジェクト設定（パスを変更する場合はここを編集）

```
PROJECT_DIR : $PROJECT_DIR
RUNNER_URL  : http://127.0.0.1:8765
```

## このエージェントの目的
SEOツールから出力したSpreadsheetを読み込み、被リンク不足記事（E列≤1）に対して
関連性の高い他記事から内部リンクを設置する候補を自動提案する。

## Coworkからの実行方法

ユーザーがSpreadsheetのURLを伝えたら、以下の手順を上から順番に実行する。

---

### STEP 1：精度モードの選択

> 精度モードを選択してください。
> - **高精度**（推奨）: KWをトークン単位で分割してスコアリング。候補記事を多く拾いやすい。
> - **中精度**: KW全体の文字列一致のみ。高速だが複合KWで候補が少なくなる場合がある。

---

### STEP 2：AIモードの選択

> AIモードを選択してください。
> - **CLIモード**: Cowork内蔵AIを使用。追加コストなし。処理は逐次（1件ずつ）。
> - **APIモード**: Anthropic API直接呼び出し。5並列処理で高速。ANTHROPIC_API_KEY が必要。

---

### STEP 3：ランナーサーバーの確認と実行

**① サーバーの状態確認**

Claude in Chrome を使って以下のURLを開く：
http://127.0.0.1:8765/status

- {"status": "idle"} → STEP 3② へ進む
- {"status": "running"} → 「現在別の処理が実行中です。完了後に再度お試しください。」とユーザーに伝える
- 接続できない場合 → 以下をユーザーに伝える：
  「ランナーサーバーが起動していません。PowerShellで以下を実行してください：」
  py "$PROJECT_DIR\local_runner.py"
  「起動後にもう一度URLを送ってください。」

**② 実行リクエストを送信**

パラメータの意味（変更禁止）：
- mid=false → 高精度、mid=true → 中精度
- api=false → CLIモード、api=true → APIモード
- パラメータ名は必ず mid と api を使うこと。mode や ai など別の名前に変えてはならない

選択結果に応じて Claude in Chrome で以下のURLを開く：
| 精度 | AIモード | URL |
|------|----------|-----|
| 高精度 | CLI | http://127.0.0.1:8765/run?url=<URL>&mid=false&api=false |
| 高精度 | API | http://127.0.0.1:8765/run?url=<URL>&mid=false&api=true |
| 中精度 | CLI | http://127.0.0.1:8765/run?url=<URL>&mid=true&api=false |
| 中精度 | API | http://127.0.0.1:8765/run?url=<URL>&mid=true&api=true |

<URL> はユーザーから受け取ったSpreadsheetのURLをそのまま入れる。

{"status": "started"} が返ってきたら：
「実行を開始しました。処理完了後にSpreadsheetをご確認ください。CLIモードは記事ごとに逐次処理、APIモードは5並列で一括処理します。」

---

### 処理の中断

処理中にユーザーが「止めて」「中断して」などと伝えた場合：

Claude in Chrome で以下のURLを開く：
http://127.0.0.1:8765/stop

{"status": "stop_requested"} が返ってきたら：
「中断シグナルを送信しました。現在処理中の記事が完了した後に停止します。Spreadsheetで処理済み記事（H列にデータあり）を確認できます。」

---

### 処理の再開

中断後にユーザーが再開を希望した場合：
- 通常通り STEP 1〜3 を実施してSpreadsheet URLを送信するだけでよい
- H列が空白の記事だけが対象になるため、自動的に続きから処理される

---

## ルール
- APIキー・認証情報はプロジェクトフォルダ外に保管すること
- 外部サイトへのHTTPリクエストはGET取得のみ
- エラーが発生した記事はスキップして処理を継続する
- H列にすでにデータがある記事は処理済みとしてスキップする
- ファイルやフォルダの作成・編集は絶対に行わない。コードの実行も行わない。ユーザーへの案内のみ行う
- ランナーサーバーに接続できない場合は、ユーザーに手動起動を案内するだけでよい。自分でサーバーを構築しようとしてはならない
- URLのパラメータ名は必ず mid と api を使うこと。mode や ai など別の名前に変えてはならない
"@

Write-Host $instructionText -ForegroundColor White
Write-Host ""
Write-Host "  ─── 指示文ここまで ────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

# クリップボードにコピー
try {
    $instructionText | Set-Clipboard
    Show-Ok "上記の指示文をクリップボードにコピーしました（Ctrl+V で貼り付けできます）"
} catch {
    Show-Info "クリップボードへのコピーに失敗しました。上記テキストを手動でコピーしてください。"
}

Wait-Enter "Cowork プロジェクトの作成・指示文の貼り付けが完了したら Enter を押してください"


# ============================================================
# STEP 10: Spreadsheet の準備（手動）
# ============================================================
Show-Header "[$([string]10)/$STEP_TOTAL]" "Google Spreadsheet の準備" "manual"

# サービスアカウントのメールアドレスを JSON から取得
$saEmail = ""
$saJsonPath = [System.Environment]::GetEnvironmentVariable("GOOGLE_SERVICE_ACCOUNT", "User")
if ($saJsonPath -and (Test-Path $saJsonPath)) {
    try {
        $saJson = Get-Content $saJsonPath -Raw | ConvertFrom-Json
        $saEmail = $saJson.client_email
    } catch {}
}

Write-Host ""
Write-Host "  ツールが読み込む Google Spreadsheet を準備します。" -ForegroundColor Yellow
Write-Host ""
Write-Host "  【手順 1】Spreadsheet を新規作成する" -ForegroundColor Yellow
Show-Step "1. ブラウザで Google ドライブ（drive.google.com）を開く"
Show-Step "2. 「+ 新規」→「Google スプレッドシート」をクリック"
Show-Step "3. シート名は任意でOK（例：内部リンク管理）"
Write-Host ""

Wait-Enter "Spreadsheet を作成したら Enter を押してください"

Write-Host ""
Write-Host "  【手順 2】CSV データをインポートする" -ForegroundColor Yellow
Show-Step "1. メニューの「ファイル」→「インポート」をクリック"
Show-Step "2. 「アップロード」タブで CSV ファイルを選択"
Show-Step "3. インポート設定："
Write-Host "     ・インポート場所  →「現在のシートを置換する」" -ForegroundColor White
Write-Host "     ・区切り文字     →「カンマ」" -ForegroundColor White
Write-Host "     ・テキストを数値・日付に変換する → オン" -ForegroundColor White
Show-Step "4. 「データをインポート」をクリック"
Write-Host ""
Write-Host "  【列構成の確認】インポート後、以下の列順になっているか確認してください" -ForegroundColor Yellow
Write-Host "  ┌────┬──────────────┬──────────────────────────────────┐" -ForegroundColor DarkGray
Write-Host "  │ 列 │ 内容         │ 備考                             │" -ForegroundColor DarkGray
Write-Host "  ├────┼──────────────┼──────────────────────────────────┤" -ForegroundColor DarkGray
Write-Host "  │ A  │ NO           │ 記事番号                         │" -ForegroundColor White
Write-Host "  │ B  │ 記事URL      │ 処理対象のURL                    │" -ForegroundColor White
Write-Host "  │ C  │ メインKW     │ キーワード（空欄可）             │" -ForegroundColor White
Write-Host "  │ D  │ 発リンク数   │                                  │" -ForegroundColor White
Write-Host "  │ E  │ 被リンク数   │ ★ 1以下の記事が処理対象         │" -ForegroundColor White
Write-Host "  │ F  │ クリック数   │                                  │" -ForegroundColor White
Write-Host "  │ G  │ 表示回数     │                                  │" -ForegroundColor White
Write-Host "  │H〜M│ 出力欄       │ ツールが自動入力（空欄のままでOK）│" -ForegroundColor White
Write-Host "  └────┴──────────────┴──────────────────────────────────┘" -ForegroundColor DarkGray
Write-Host ""
Show-Warn "列の順番が違う場合は列を並び替えてから次へ進んでください"
Write-Host ""

Wait-Enter "CSV のインポートと列確認が完了したら Enter を押してください"

Write-Host ""
Write-Host "  【手順 3】サービスアカウントに編集権限を付与する" -ForegroundColor Yellow
Show-Step "1. Spreadsheet 右上の「共有」ボタンをクリック"
Show-Step "2. 以下のメールアドレスを入力して追加する"
Write-Host ""
if ($saEmail) {
    Write-Host "  ┌─────────────────────────────────────────────────────┐" -ForegroundColor DarkGray
    Write-Host "  │  $saEmail" -ForegroundColor Cyan
    Write-Host "  └─────────────────────────────────────────────────────┘" -ForegroundColor DarkGray
    try {
        $saEmail | Set-Clipboard
        Show-Ok "上記のメールアドレスをクリップボードにコピーしました（Ctrl+V で貼り付けできます）"
    } catch {}
} else {
    Show-Warn "サービスアカウントのメールアドレスを取得できませんでした。"
    Show-Warn "管理者から受け取った JSON ファイルを開き「client_email」の値を入力してください。"
}
Write-Host ""
Show-Step "3. 権限を「閲覧者」→「編集者」に変更する"
Show-Step "4. 「送信」をクリック（通知メールは送らなくてOK）"
Write-Host ""

Wait-Enter "共有設定が完了したら Enter を押してください"

Write-Host ""
Write-Host "  【手順 4】Spreadsheet の URL をコピーする" -ForegroundColor Yellow
Show-Step "ブラウザのアドレスバーの URL をコピーしておいてください"
Show-Info "（例：https://docs.google.com/spreadsheets/d/XXXXXXX/edit）"
Show-Info "このURLをCoworkのチャットに貼り付けると処理が始まります"
Write-Host ""

Wait-Enter "URL のコピーが完了したら Enter を押してください"


# ============================================================
# 完了
# ============================================================
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║           セットアップ完了！                     ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  ✔ Python                    インストール済み" -ForegroundColor Green
Write-Host "  ✔ Chrome + Claude拡張機能   インストール済み" -ForegroundColor Green
Write-Host "  ✔ Cowork                    インストール済み" -ForegroundColor Green
Write-Host "  ✔ Python ライブラリ          インストール済み" -ForegroundColor Green
Write-Host "  ✔ 環境変数                  設定済み" -ForegroundColor Green
Write-Host "  ✔ 自動起動                  登録済み" -ForegroundColor Green
Write-Host "  ✔ ランナーサーバー           $(if ($serverOk) { '起動済み' } else { '要確認' })" -ForegroundColor $(if ($serverOk) { 'Green' } else { 'Yellow' })
Write-Host "  ✔ Cowork プロジェクト        作成済み" -ForegroundColor Green
Write-Host "  ✔ Spreadsheet               準備済み" -ForegroundColor Green
Write-Host ""
Write-Host "  【次回からの使い方】" -ForegroundColor Cyan
Write-Host "  1. Cowork を開いて「内部リンクエージェント」プロジェクトを選択" -ForegroundColor White
Write-Host "  2. チャット欄に Spreadsheet の URL を貼り付けて送信" -ForegroundColor White
Write-Host "  3. 精度モード・AIモードを選択すると処理が自動で始まります" -ForegroundColor White
Write-Host ""
Write-Host "  ランナーサーバーは PC 起動時に自動で立ち上がります。" -ForegroundColor Gray
Write-Host "  設定変更は setup_once.ps1 を再実行してください。" -ForegroundColor Gray
Write-Host ""
Read-Host "  Enter を押して終了"
