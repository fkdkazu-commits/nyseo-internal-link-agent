"""
NYSEO 内部リンク構築AIエージェント
=====================================
Coworkのチャット欄で「内部リンクエージェントを実行してください」と入力すると
CLAUDE.md の手順に従ってこのスクリプトが呼び出される。

処理フロー:
  STEP1: 対象記事抽出（E列≤1 かつ H列が空白）
  STEP2: 関連記事候補探索（KW一致・Cowork内蔵AIによるKW拡張）
  STEP3: 全記事HTML一括取得・解析（B案）
  STEP4: Cowork内蔵AIによる関連性スコアリング（100点・5観点）
  STEP5: 採用候補をCSV出力（H列以降）
"""

import json
import time

from config import MIN_CANDIDATES
from steps.step1_extract import extract_targets
from steps.step2_search import search_candidates
from steps.step3_fetch import fetch_all_articles, fetch_article
from steps.step4_judge import judge_candidates
from steps.step5_output import write_output
from utils.csv_client import find_input_csv, load_csv, save_output_csv, is_already_processed
from utils.logger import get_logger

logger = get_logger()


# ---------------------------------------------------------------------------
# Cowork内蔵AI呼び出し関数（CLAUDE.md経由でCoworkが注入する）
# ---------------------------------------------------------------------------

def ai_expand_keywords(target_kw: str) -> list[str]:
    """
    Cowork内蔵AIにKW拡張を依頼する。
    実装はCoworkのツール呼び出しまたはプロンプト経由で行う。
    ここではプロンプトテキストを標準出力に出力し、
    Coworkが応答を解析して返す方式を想定する。
    """
    # TODO: Phase 2でCowork内蔵AI呼び出しに置き換える
    logger.info(f"KW拡張（スキップ中）: {target_kw}")
    return []


def ai_judge(target: dict, candidate: dict) -> "dict | None":
    """
    Cowork内蔵AIに関連性判定を依頼する。
    score / reason / recommended_heading を含むdictを返す。
    """
    # TODO: Phase 2でCowork内蔵AI呼び出しに置き換える
    logger.info(f"AI判定（スキップ中）: {candidate['url']}")
    return None


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 50)
    logger.info("NYSEO 内部リンク構築AIエージェント 開始")
    logger.info("=" * 50)

    # --- CSVロード ---
    csv_path = find_input_csv()
    header, data = load_csv(csv_path)
    max_cols = max(13, len(header))  # H〜M列（インデックス12）まで確保

    # --- STEP1: 対象記事抽出 ---
    targets = extract_targets(data)
    if not targets:
        logger.info("対象記事が0件です。処理を終了します。")
        return

    # --- STEP3（B案）: 全記事HTML一括取得 ---
    logger.info("全記事のHTML一括取得を開始します（B案）...")
    all_articles = fetch_all_articles(data)

    # --- 対象記事ごとに処理 ---
    for target in targets:
        logger.info(f"\n--- 処理中: {target['url']} ---")

        # C列KWが空の場合、記事を取得してKW自動検出
        if target["kw_source"] == "auto_detect":
            article = fetch_article(target["url"])
            if article:
                target["kw"] = article.get("title", "") or article.get("h1", "")
                logger.info(f"KW自動検出: {target['kw']}")

        # --- STEP2: 候補探索 ---
        candidates = search_candidates(target, all_articles)

        # KW拡張でさらに候補を補完
        expanded_kws = ai_expand_keywords(target["kw"])
        for ekw in expanded_kws:
            extra = search_candidates({**target, "kw": ekw}, all_articles)
            for c in extra:
                if not any(x["url"] == c["url"] for x in candidates):
                    candidates.append(c)

        if not candidates:
            logger.warning(f"候補記事が見つかりませんでした: {target['url']}")
            continue

        # --- STEP4: AI関連性判定 ---
        adopted = judge_candidates(target, candidates, ai_judge)

        if len(adopted) < MIN_CANDIDATES:
            logger.warning(f"採用件数が{MIN_CANDIDATES}件未満のため空欄出力: {target['url']}")

        # --- STEP5: CSV行に書き込み ---
        row = data[target["row_idx"]]
        data[target["row_idx"]] = write_output(row, adopted, max_cols)

        time.sleep(0.5)  # レート制限対応

    # --- 出力CSV保存 ---
    save_output_csv(csv_path, header, data)

    logger.info("=" * 50)
    logger.info("全処理完了")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
