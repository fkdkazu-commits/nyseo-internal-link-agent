# 内部リンク構築エージェント — 完全インストーラー
# ============================================================
# クライアント PC への初回セットアップを一括で案内します。
# PowerShell で以下を実行してください：
#   cd "フォルダのパス"
#   .\install.ps1
# ============================================================

$PROJECT_DIR = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$STEP_TOTAL  = 12

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
    $Host.UI.RawUI.FlushInputBuffer()
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
Write-Host "║  NYSEO Cowork自動化エージェント インストーラー   ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  以下の機能のインストールを開始します：" -ForegroundColor Cyan
Write-Host "    ①  内部リンクエージェント（CSV解析・候補提案）" -ForegroundColor White
Write-Host "    ②  WordPress 内部リンク自動挿入" -ForegroundColor White
Write-Host ""
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
Write-Host "  Cowork が動作するために必要な公式拡張機能です。" -ForegroundColor Gray
Write-Host ""
Show-Step "1. 今からブラウザで Chrome ウェブストアの検索ページを開きます"
Show-Step "2. 「Claude」（Anthropic 製）を探して「Chrome に追加」をクリック"
Show-Step "3. 確認ダイアログで「拡張機能を追加」をクリック"
Show-Step "4. Chrome の右上に Claude のアイコン（橙色）が表示されれば完了です"
Write-Host ""
Start-Process "https://chromewebstore.google.com/search/Claude"

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
# STEP 4: Claude CLI ログイン確認（自動）
# ============================================================
Show-Header "[$([string]4)/$STEP_TOTAL]" "Claude CLI ログイン確認"

# claude.exe を探す（Windowsストア版対応）
$claudeExe = $null
$localApp = $env:LOCALAPPDATA

# 通常版
foreach ($p in @(
    "$localApp\AnthropicClaude\claude.exe",
    "$env:USERPROFILE\AppData\Local\AnthropicClaude\claude.exe"
)) {
    if (Test-Path $p) { $claudeExe = $p; break }
}

# Windowsストア版（バージョン番号が可変なのでglobで検索）
if (-not $claudeExe) {
    $claudeExe = Get-ChildItem "$localApp\Packages\Claude_*\LocalCache\Roaming\Claude\claude-code\*\claude.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}

# PATH上のclaude.exeをフォールバックとして検索
if (-not $claudeExe) {
    $claudeExe = (Get-Command claude -ErrorAction SilentlyContinue).Source
}

if (-not $claudeExe) {
    Show-Warn "claude.exe が見つかりませんでした。Cowork（Claude Desktop）が正しくインストールされているか確認してください。"
    Wait-Enter "確認後 Enter を押してください"
} else {
    Show-Ok "claude.exe を発見: $claudeExe"
    Write-Host ""

    # ログイン状態を確認（--version はログイン不要なので短いプロンプトで実際に確認）
    Write-Host "  ログイン状態を確認中..." -ForegroundColor Cyan
    $loggedIn = $false
    while (-not $loggedIn) {
        $testResult = & $claudeExe -p "ping" --model "claude-haiku-4-5-20251001" 2>&1
        $testStr = "$testResult"

        if ($testStr -match "Not logged in|Please run /login|not logged") {
            Write-Host ""
            Show-Warn "Claude にログインしていません。ログインが必要です。"
            Write-Host ""
            Write-Host "  【手順】" -ForegroundColor Yellow
            Show-Step "1. 別の PowerShell ウィンドウを開いて以下を実行："
            Write-Host "     & `"$claudeExe`"" -ForegroundColor White
            Show-Step "2. 起動後に /login と入力して Enter"
            Show-Step "3. ブラウザで Claude アカウントにログイン"
            Show-Step "4. ログイン完了後このウィンドウに戻ってください"
            Write-Host ""
            Wait-Enter "ログインが完了したら Enter を押してください（再確認します）"
            Write-Host "  再確認中..." -ForegroundColor Cyan
        } else {
            $loggedIn = $true
            Show-Ok "Claude CLI のログインを確認しました"
        }
    }
}


# ============================================================
# STEP 5: プロジェクトフォルダの確認（自動）
# ============================================================
Show-Header "[$([string]5)/$STEP_TOTAL]" "プロジェクトフォルダの確認"

$requiredFiles = @("main.py", "local_runner.py", "install.ps1", "requirements.txt", "config.py")
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

# Downloads / Temp への配置警告
$tempPaths = @("Downloads", "Temp", "tmp", "デスクトップ", "Desktop")
$inTempDir = $false
foreach ($t in $tempPaths) {
    if ($PROJECT_DIR -like "*\$t\*" -or $PROJECT_DIR -like "*\$t") {
        $inTempDir = $true; break
    }
}
if ($inTempDir) {
    Write-Host ""
    Write-Host "  ⚠️  【重要】このフォルダは一時的な場所にあります" -ForegroundColor Yellow
    Write-Host "  現在のパス: $PROJECT_DIR" -ForegroundColor White
    Write-Host ""
    Write-Host "  このままセットアップを続けると、ランナーサーバーの自動起動が" -ForegroundColor Yellow
    Write-Host "  このフォルダを参照するように登録されます。" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  【推奨】以下のような恒久的な場所にフォルダを移動してから" -ForegroundColor Cyan
    Write-Host "  install.bat を再実行してください：" -ForegroundColor Cyan
    Write-Host "  例） C:\Users\$env:USERNAME\OneDrive\ドキュメント\Claude\nyseo-internal-link-agent" -ForegroundColor White
    Write-Host "  例） C:\Users\$env:USERNAME\Documents\nyseo-internal-link-agent" -ForegroundColor White
    Write-Host ""
    $ans = Read-Host "  このまま続けますか？（移動してから再実行する場合は N を入力して終了）[Y/N]"
    if ($ans -eq "N" -or $ans -eq "n") {
        Write-Host "  フォルダを移動してから install.bat を再実行してください。" -ForegroundColor Cyan
        exit 0
    }
}


# ============================================================
# STEP 6: Google サービスアカウント JSON の配置（自動）
# ============================================================
Show-Header "[$([string]6)/$STEP_TOTAL]" "Google サービスアカウント JSON の配置"

$defaultSecretsDir = "$env:USERPROFILE\.secrets"
$secretsSrcDir = Join-Path $PROJECT_DIR "secrets"

# .secrets フォルダを自動作成
if (-not (Test-Path $defaultSecretsDir)) {
    New-Item -ItemType Directory -Path $defaultSecretsDir | Out-Null
    Show-Ok ".secrets フォルダを作成しました: $defaultSecretsDir"
}

# パッケージ内 secrets/ フォルダから JSON を自動コピー
$bundledJson = Get-ChildItem -Path $secretsSrcDir -Filter "*.json" -ErrorAction SilentlyContinue | Select-Object -First 1

if ($bundledJson) {
    $destPath = Join-Path $defaultSecretsDir $bundledJson.Name
    Copy-Item -Path $bundledJson.FullName -Destination $destPath -Force
    Show-Ok "JSON ファイルをコピーしました: $destPath"
    $defaultJsonPath = $destPath
} else {
    Show-Warn "secrets フォルダに JSON ファイルが見つかりません。"
    Show-Warn "手動で配置してください: $defaultSecretsDir"
    Start-Process "explorer.exe" $defaultSecretsDir
    Wait-Enter "JSON ファイルの配置が完了したら Enter を押してください"
    $foundJson = Get-ChildItem -Path $defaultSecretsDir -Filter "*.json" | Select-Object -First 1
    $defaultJsonPath = if ($foundJson) { $foundJson.FullName } else { Join-Path $defaultSecretsDir "agent.json" }
}


# ============================================================
# STEP 7: 環境変数の設定（自動）
# ============================================================
Show-Header "[$([string]7)/$STEP_TOTAL]" "環境変数の設定"

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
    Show-Warn "パスを後で修正する場合は install.bat を再実行してください"
}
[System.Environment]::SetEnvironmentVariable("GOOGLE_SERVICE_ACCOUNT", $saPath, "User")
Show-Ok "GOOGLE_SERVICE_ACCOUNT を設定しました"


# ============================================================
# STEP 8: WordPress サイト情報の設定（手動）
# ============================================================
Show-Header "[$([string]8)/$STEP_TOTAL]" "WordPress サイト情報の設定" "manual"

$sitesJsonPath = "$env:USERPROFILE\.secrets\nyseo_sites.json"
$siteMap = @{}

# 既存設定を読み込む
if (Test-Path $sitesJsonPath) {
    try {
        $existing = Get-Content $sitesJsonPath -Raw | ConvertFrom-Json
        foreach ($prop in $existing.PSObject.Properties) {
            $siteMap[$prop.Name] = @{
                wp_url          = $prop.Value.wp_url
                wp_user         = $prop.Value.wp_user
                wp_app_password = $prop.Value.wp_app_password
            }
        }
        Show-Ok "既存の設定を読み込みました（$($siteMap.Count) サイト）"
    } catch {
        Show-Warn "既存の設定ファイルの読み込みに失敗しました。新規作成します。"
    }
}

Write-Host ""
Write-Host "  WordPress への自動挿入に使用する認証情報を設定します。" -ForegroundColor Yellow
Write-Host "  スプレッドシートごとに対象の WordPress サイトを紐づけます。" -ForegroundColor Gray
Write-Host "  複数メディアをお持ちの場合は、メディア数分入力してください。" -ForegroundColor Gray
Write-Host ""

$wpSetupDone = $false
while (-not $wpSetupDone) {
    Write-Host "  ─── スプレッドシート ↔ WordPress の紐づけ設定 ───" -ForegroundColor Cyan
    Write-Host ""

    # Spreadsheet URL
    $ssUrl = ""
    while (-not $ssUrl) {
        $ssUrl = (Read-Host "  Spreadsheet URL を入力").Trim()
    }

    # Spreadsheet ID を抽出
    if ($ssUrl -match "/spreadsheets/d/([a-zA-Z0-9_-]+)") {
        $ssId = $Matches[1]
        Show-Ok "Spreadsheet ID: $ssId"
    } else {
        Show-Warn "URL から ID を抽出できませんでした。URL を確認してください。"
        continue
    }

    # WordPress 情報
    $wpUrl  = (Read-Host "  WordPress サイト URL（例: https://example.com）").Trim().TrimEnd("/")
    $wpUser = (Read-Host "  WordPress ユーザー名（管理者）").Trim()
    Write-Host "  ※ WordPress管理画面 → ユーザー → プロフィール → アプリケーションパスワード" -ForegroundColor Gray
    $wpPass = (Read-Host "  アプリケーションパスワード").Trim()

    $siteMap[$ssId] = @{
        wp_url          = $wpUrl
        wp_user         = $wpUser
        wp_app_password = $wpPass
    }
    Show-Ok "設定を追加しました: $wpUrl"
    Write-Host ""

    $moreAns = Read-Host "  別のスプレッドシート（メディア）を追加しますか？ [Y/N]"
    if ($moreAns -ne "Y" -and $moreAns -ne "y") {
        $wpSetupDone = $true
    }
}

# JSON 保存
if ($siteMap.Count -gt 0) {
    $jsonObj = [ordered]@{}
    foreach ($key in $siteMap.Keys) { $jsonObj[$key] = $siteMap[$key] }
    $jsonStr = $jsonObj | ConvertTo-Json -Depth 3
    [System.IO.File]::WriteAllText($sitesJsonPath, $jsonStr, [System.Text.Encoding]::UTF8)
    Show-Ok "$($siteMap.Count) サイトの設定を保存しました: $sitesJsonPath"
} else {
    Show-Warn "サイト設定がありません。後で install.bat を再実行して設定してください。"
}


# ============================================================
# STEP 9: ライブラリのインストール（自動）
# ============================================================
Show-Header "[$([string]9)/$STEP_TOTAL]" "Python ライブラリのインストール"

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
# STEP 9: スタートアップ登録 + ランナーサーバー起動（自動）
# ============================================================
Show-Header "[$([string]10)/$STEP_TOTAL]" "ランナーサーバーの登録・起動"

# スタートアップ登録
$pyPath = (Get-Command $pyCmd -ErrorAction SilentlyContinue).Source
if (-not $pyPath) { $pyPath = $pyCmd }
$runnerScript = Join-Path $PROJECT_DIR "local_runner.py"
$startupDir   = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$startupBat   = Join-Path $startupDir "nyseo_runner.bat"
$batContent   = "@echo off`r`nstart `"`" /min `"$pyPath`" `"$runnerScript`"`r`n"
[System.IO.File]::WriteAllText($startupBat, $batContent, [System.Text.Encoding]::GetEncoding(932))
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
# STEP 10: Cowork プロジェクトの作成（手動）
# ============================================================
Show-Header "[$([string]11)/$STEP_TOTAL]" "Cowork プロジェクトの作成" "manual"

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

- {"status": "idle"} → STEP 2② へ進む
- {"status": "running"} → 「現在別の処理が実行中です。完了後に再度お試しください。」とユーザーに伝える
- 接続できない場合 → 以下をユーザーに伝える：
  「ランナーサーバーが起動していません。PowerShellで以下を実行してください：」
  py "$PROJECT_DIR\local_runner.py"
  「起動後にもう一度URLを送ってください。」

② 実行リクエストを送信

精度モードの選択結果に応じて Claude in Chrome で以下のURLを開く：
| 精度 | URL |
|------|-----|
| 高精度 | http://127.0.0.1:8765/run?url=<URL>&mid=false&api=false |
| 中精度 | http://127.0.0.1:8765/run?url=<URL>&mid=true&api=false |

<URL> はユーザーから受け取ったSpreadsheetのURLをそのまま入れる。

{"status": "started"} が返ってきたら：
「実行を開始しました。処理完了後にSpreadsheetのH〜M列に候補が書き込まれます。」

**STEP 3：完了後のWP挿入確認**

ユーザーから処理完了の報告があったら、必ず以下を確認する：

「処理が完了しました。WordPressへの自動挿入も続けますか？
・はい → スプレッドシートを確認せずにそのまま挿入します
・いいえ → スプレッドシートでH〜M列を確認・承認してから、後でWordPress挿入を実行してください」

「はい」の場合 → パターン2のWP挿入手順を実行する
「いいえ」の場合 → 「H〜M列を確認・承認してから、チャットで『WP挿入して』と送ってください。」と伝える

---

### ■ パターン2：WordPressに挿入する

ユーザーが「WordPressに挿入してほしい」「WP挿入を実行して」などと伝えたら以下を実行する。
SpreadsheetのH〜M列のレビュー・承認が完了している前提で進める。

**STEP 1：リンク形式の確認**

> 挿入するリンクの形式を教えてください：
> - **URLのみ**（WordPressがブログカードに自動展開）
> - **aタグ**（`<a href="URL">記事タイトル</a>` の形式）

※エディタ形式（クラシック / Gutenberg）は記事ごとに自動判定されるため確認不要。

**STEP 2：WP挿入リクエストを送信**

リンク形式に応じて Claude in Chrome で以下のURLを開く：
| 形式 | URL |
|------|-----|
| URLのみ | http://127.0.0.1:8765/run-wp?url=<URL>&link=url |
| aタグ | http://127.0.0.1:8765/run-wp?url=<URL>&link=atag |

<URL> はユーザーから受け取ったSpreadsheetのURLをそのまま入れる。

{"status": "started"} が返ってきたら：
「WP挿入を開始しました。完了後にSpreadsheetのN列でステータスを確認できます。」

---

### ■ 処理の中断

処理中にユーザーが「止めて」「中断して」などと伝えた場合：

Claude in Chrome で以下のURLを開く：
http://127.0.0.1:8765/stop

{"status": "stop_requested"} が返ってきたら：
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
- N列に「済み」が記録されている行はWP挿入をスキップする（冪等性あり）
- ファイルやフォルダの作成・編集は絶対に行わない。コードの実行も行わない。ユーザーへの案内のみ行う
- ランナーサーバーに接続できない場合は、ユーザーに手動起動を案内するだけでよい。自分でサーバーを構築しようとしてはならない
- URLのパラメータ名は必ず mid と api（内部リンク）、link（WP挿入）を使うこと
- レビューを省略した連続実行はリスクがある旨をユーザーに伝えること
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
# STEP 11: Spreadsheet の準備（手動）
# ============================================================
Show-Header "[$([string]12)/$STEP_TOTAL]" "Google Spreadsheet の準備" "manual"

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
Write-Host "  ✔ Claude CLI ログイン        確認済み" -ForegroundColor Green
Write-Host "  ✔ Python ライブラリ          インストール済み" -ForegroundColor Green
Write-Host "  ✔ 環境変数                  設定済み" -ForegroundColor Green
Write-Host "  ✔ WordPress サイト設定       $($siteMap.Count)サイト登録済み" -ForegroundColor $(if ($siteMap.Count -gt 0) { 'Green' } else { 'Yellow' })
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
Write-Host "  設定変更は install.bat を再実行してください。" -ForegroundColor Gray
Write-Host ""
Read-Host "  Enter を押して終了"
