from pathlib import Path

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

# CSV列インデックス（0始まり・NYSEO出力形式）
COL_NO = 0          # A列: NO（連番）
COL_URL = 1         # B列: 記事URL
COL_KW = 2          # C列: メインKW（GSCクリック最多）
COL_OUTBOUND = 3    # D列: 発リンク数
COL_INBOUND = 4     # E列: 被リンク数（≤1が対象抽出条件）
COL_CLICK = 5       # F列: クリック数
COL_IMPRESSION = 6  # G列: 表示回数

# 出力列インデックス（H列以降）
COL_OUT_URL1 = 7    # H列: 候補記事URL①
COL_OUT_H1   = 8    # I列: リンク設置箇所見出し①
COL_OUT_URL2 = 9    # J列: 候補記事URL②
COL_OUT_H2   = 10   # K列: リンク設置箇所見出し②
COL_OUT_URL3 = 11   # L列: 候補記事URL③（任意）
COL_OUT_H3   = 12   # M列: リンク設置箇所見出し③（任意）

# AIモデル設定
MODEL_KW    = "claude-haiku-4-5-20251001"  # KW抽出・拡張（軽量・高速）
MODEL_JUDGE = "claude-sonnet-4-6"           # 関連性判定（高品質）

# スコアリング閾値
SCORE_THRESHOLD = 60      # 採用閾値（これ未満は採用しない）
MIN_CANDIDATES = 2        # 最低提案件数
MAX_CANDIDATES = 3        # 最大提案件数
MAX_SEARCH_CANDIDATES = 20  # STEP2で絞り込む最大候補数（通常モード）

# --lean フラグ時のトークン節約設定（候補数は変えず本文のみ削減）
LEAN_BODY_TEXT_CHARS = 150        # 本文抜粋を半減（通常300文字）

# --api モード時の並列数
API_CONCURRENCY = 5

# --strict フラグ時のmatch_score足切り閾値
# score=1: KWの先頭2文字が本文に含まれるだけ（ほぼ無関係）
# score=3: 本文にKWが含まれる
# score=5: h2/h3にKWが含まれる（推奨最低ライン）
STRICT_MIN_MATCH_SCORE = 5        # これ未満の候補はAIに渡さない

# WordPress挿入ステータス列（v1.3〜）
COL_WP_STATUS  = 13   # N列: 挿入ステータス（「済み」/「エラー」/「スキップ」）
COL_WP_DATE    = 14   # O列: 処理日時 / エラー内容
COL_WP_COUNT   = 15   # P列: 挿入件数（0〜3）

# HTTP設定
HTTP_TIMEOUT = 10   # 秒
HTTP_RETRY = 2      # リトライ回数
USER_AGENT = "NYSEOInternalLinkAgent/1.0"

# 除外URLパターン（カテゴリ・タグ・アーカイブページ）
EXCLUDE_URL_PATTERNS = ["/category/", "/tag/", "/page/"]
