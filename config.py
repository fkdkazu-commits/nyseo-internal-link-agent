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

# スコアリング閾値
SCORE_THRESHOLD = 60      # 通常採用閾値
SCORE_THRESHOLD_LOW = 40  # 候補不足時の緩和閾値
MIN_CANDIDATES = 2        # 最低提案件数
MAX_CANDIDATES = 3        # 最大提案件数
MAX_SEARCH_CANDIDATES = 20  # STEP2で絞り込む最大候補数

# HTTP設定
HTTP_TIMEOUT = 10   # 秒
HTTP_RETRY = 2      # リトライ回数
USER_AGENT = "NYSEOInternalLinkAgent/1.0"

# 除外URLパターン（カテゴリ・タグ・アーカイブページ）
EXCLUDE_URL_PATTERNS = ["/category/", "/tag/", "/page/"]
