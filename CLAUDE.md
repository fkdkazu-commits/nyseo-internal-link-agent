# NYSEO 内部リンク構築AIエージェント — Cowork実行手順

## このエージェントの目的
NYSEOから出力したSpreadsheetを読み込み、被リンク不足記事（E列≤1）に対して
関連性の高い他記事から内部リンクを設置する候補を自動提案する。

## Coworkからの実行方法

ユーザーがSpreadsheetのURLを伝えたら、以下のコマンドを実行する。

```
py main.py <SpreadsheetURL>
```

実行例:
```
py main.py https://docs.google.com/spreadsheets/d/xxxxxxxxx/edit
```

実行中はログを読みながら進捗を報告すること。
完了後は「Spreadsheetに結果を書き込みました」と伝える。

## 初回セットアップ（初回のみ）

### 1. パッケージインストール
```
pip install -r requirements.txt
```

### 2. Google Sheetsサービスアカウント設定
環境変数 `GOOGLE_SERVICE_ACCOUNT` にJSONファイルのパスを設定する。

PowerShellの場合:
```
$env:GOOGLE_SERVICE_ACCOUNT = "C:\path\to\service_account.json"
```

永続化する場合はシステム環境変数に追加する。

### 3. SpreadsheetへのアクセスをGoogleで許可
サービスアカウントのメールアドレスをSpreadsheetの共有設定に追加する（編集者権限）。

## Spreadsheet構成

### データタブ（1枚目・既存）
| 列 | 内容 |
|---|---|
| A | NO |
| B | 記事URL |
| C | メインKW |
| D | 発リンク数 |
| E | 被リンク数（≤1が処理対象） |
| F | クリック数 |
| G | 表示回数 |
| H〜M | 出力（自動入力） |

### article_cacheタブ（自動作成）
初回実行時に自動作成される。取得済み記事のHTMLデータを保存し、
2回目以降の実行時に再取得をスキップする。

## 出力内容（H〜M列）
| 列 | 内容 |
|---|---|
| H | 候補記事URL①（この記事から対象記事へリンクを設置する） |
| I | リンク設置箇所の見出し① |
| J | 候補記事URL② |
| K | リンク設置箇所の見出し② |
| L | 候補記事URL③（任意） |
| M | リンク設置箇所の見出し③（任意） |

## ルール
- APIキー・認証情報はプロジェクトフォルダ外に保管すること
- 外部サイトへのHTTPリクエストはGET取得のみ
- エラーが発生した記事はスキップして処理を継続する
- H列にすでにデータがある記事は処理済みとしてスキップする
