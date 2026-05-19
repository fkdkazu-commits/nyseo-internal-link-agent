"""
Cowork内蔵AI（Claude CLI）呼び出しラッパー。
Cowork環境ではAPIキー不要で claude コマンドが使用可能。
"""

import json
import subprocess
import time
from pathlib import Path

from utils.logger import get_logger

logger = get_logger()

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
CLI_TIMEOUT = 60  # 秒


class TokenExhaustedError(Exception):
    """Claude CLIのトークン上限に達した場合に raise する。"""
    pass


def _call_claude(prompt: str, retries: int = 2) -> "str | None":
    """claude CLIをサブプロセスで呼び出し、レスポンステキストを返す。"""
    for attempt in range(1, retries + 2):
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "text"],
                capture_output=True,
                timeout=CLI_TIMEOUT,
            )
            # バイナリで受け取りUTF-8でデコード（Windows cp932問題を回避）
            stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
            stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
            # トークン切れ検出（リトライせず即 raise）
            if "out of extra usage" in stdout or "out of extra usage" in stderr:
                raise TokenExhaustedError(stdout.strip() or stderr.strip())
            # stdoutに内容があればreturncode関係なく使用する
            if stdout.strip():
                return stdout.strip()
            logger.warning(f"claude CLI 失敗（試行{attempt}）stderr: {stderr[:400]}")
        except subprocess.TimeoutExpired:
            logger.warning(f"claude CLI タイムアウト（試行{attempt}）")
        except FileNotFoundError:
            logger.error("claude コマンドが見つかりません。Cowork環境で実行してください。")
            return None
        except Exception as e:
            logger.warning(f"claude CLI 例外（試行{attempt}）: {e}")

        if attempt <= retries:
            time.sleep(2)

    return None


def _extract_json(text: str, bracket: str) -> "str | None":
    """レスポンステキストからJSON部分を抽出する。"""
    close = "]" if bracket == "[" else "}"
    start = text.find(bracket)
    end = text.rfind(close)
    if start >= 0 and end > start:
        return text[start : end + 1]
    return None


def expand_keywords(target_kw: str) -> list:
    """
    KWの関連語・共起語・類義語をCowork内蔵AIで生成する。
    戻り値: キーワード文字列のリスト（失敗時は空リスト）
    """
    if not target_kw:
        return []

    template = (PROMPTS_DIR / "kw_expansion.txt").read_text(encoding="utf-8")
    prompt = template.format(target_kw=target_kw)

    response = _call_claude(prompt)
    if not response:
        logger.warning(f"KW拡張: AIレスポンスなし（KW: {target_kw}）")
        return []

    raw = _extract_json(response, "[")
    if not raw:
        logger.warning(f"KW拡張: JSON配列が見つかりません（KW: {target_kw}）")
        return []

    try:
        keywords = json.loads(raw)
        if isinstance(keywords, list):
            logger.info(f"KW拡張完了: {len(keywords)} 語生成（KW: {target_kw}）")
            return [str(k) for k in keywords]
    except json.JSONDecodeError as e:
        logger.warning(f"KW拡張: JSON解析失敗 — {e}")

    return []


def judge_relevance_batch(target: dict, candidates: list[dict]) -> list[dict]:
    """
    候補記事の関連性を一括スコアリングする（トークン節約版）。
    1回のAI呼び出しで全候補を判定する。
    戻り値: [{"url", "score", "reason", "recommended_heading"}, ...]
            失敗時は空リスト
    """
    if not candidates:
        return []

    template = (PROMPTS_DIR / "relevance_judge_batch.txt").read_text(encoding="utf-8")

    # 候補記事ブロックを組み立て（本文は300文字に絞る）
    lines = []
    for c in candidates:
        h = (c.get("h2_list", [])[:3] + c.get("h3_list", [])[:2])
        headings = " / ".join(h) if h else "（見出しなし）"
        lines.append(
            f"- URL: {c.get('url', '')}\n"
            f"  タイトル: {c.get('title', '')}\n"
            f"  見出し: {headings}\n"
            f"  本文冒頭: {c.get('body_text', '')[:300]}"
        )
    candidates_block = "\n\n".join(lines)

    prompt = template.format(
        target_kw=target.get("kw", ""),
        target_url=target.get("url", ""),
        candidates_block=candidates_block,
    )

    response = _call_claude(prompt)
    if not response:
        logger.warning("AI一括判定: AIレスポンスなし")
        return []

    raw = _extract_json(response, "[")
    if not raw:
        logger.warning(f"AI一括判定: JSON配列が見つかりません")
        logger.debug(f"レスポンス内容: {response[:300]}")
        return []

    try:
        results = json.loads(raw)
        if not isinstance(results, list):
            logger.warning("AI一括判定: レスポンスがリスト形式ではありません")
            return []
        out = []
        for r in results:
            try:
                out.append({
                    "url": r.get("url", ""),
                    "score": int(r.get("score", 0)),
                    "reason": r.get("reason", ""),
                    "recommended_heading": r.get("recommended_heading", ""),
                })
            except (ValueError, TypeError):
                continue
        logger.info(f"AI一括判定完了: {len(out)} 件")
        return out
    except json.JSONDecodeError as e:
        logger.warning(f"AI一括判定: JSON解析失敗 — {e}")

    return []


def judge_relevance(target: dict, candidate: dict) -> "dict | None":
    """
    候補記事の関連性をCowork内蔵AIで100点満点でスコアリングする。
    戻り値: {"score": int, "reason": str, "recommended_heading": str}
            失敗時は None
    """
    template = (PROMPTS_DIR / "relevance_judge.txt").read_text(encoding="utf-8")

    headings_list = candidate.get("h2_list", [])[:5] + candidate.get("h3_list", [])[:5]
    headings = " / ".join(headings_list) if headings_list else "（見出しなし）"

    prompt = template.format(
        target_kw=target.get("kw", ""),
        target_url=target.get("url", ""),
        candidate_title=candidate.get("title", ""),
        candidate_url=candidate.get("url", ""),
        candidate_headings=headings,
        candidate_body=candidate.get("body_text", "")[:800],
    )

    response = _call_claude(prompt)
    if not response:
        logger.warning(f"AI判定: AIレスポンスなし（URL: {candidate.get('url')}）")
        return None

    raw = _extract_json(response, "{")
    if not raw:
        logger.warning(f"AI判定: JSONオブジェクトが見つかりません（URL: {candidate.get('url')}）")
        logger.debug(f"AI判定レスポンス内容: {response[:300]}")
        return None

    try:
        result = json.loads(raw)
        score = int(result.get("score", 0))
        logger.info(f"AI判定完了: {score}点 — {candidate.get('url')}")
        return {
            "score": score,
            "reason": result.get("reason", ""),
            "recommended_heading": result.get("recommended_heading", ""),
        }
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"AI判定: JSON解析失敗 — {e}")

    return None
