"""
Cowork内蔵AI（Claude CLI）呼び出しラッパー。
--api フラグ時は Anthropic SDK を直接使用（ANTHROPIC_API_KEY 環境変数が必要）。
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from config import MODEL_KW, MODEL_JUDGE
from utils.logger import get_logger

logger = get_logger()

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
CLI_TIMEOUT = 240  # 秒（20件一括判定プロンプトは応答に2〜3分かかる場合がある）

def _find_claude() -> str:
    """claude 実行ファイルのパスを返す。見つからなければ 'claude' を返す。"""
    # 1. PATH から検索
    found = shutil.which("claude")
    if found:
        return found

    local_app = Path(os.environ.get("LOCALAPPDATA", ""))

    # 2. 通常インストール版
    for p in [
        local_app / "AnthropicClaude" / "claude.exe",
        Path(os.environ.get("USERPROFILE", "")) / "AppData" / "Local" / "AnthropicClaude" / "claude.exe",
    ]:
        if p.exists():
            logger.info(f"claude をフォールバックパスで発見: {p}")
            return str(p)

    # 3. Windows ストア版（パッケージ名・バージョンが可変なのでglobで検索）
    packages_dir = local_app / "Packages"
    if packages_dir.exists():
        for exe in packages_dir.glob("Claude_*/LocalCache/Roaming/Claude/claude-code/*/claude.exe"):
            logger.info(f"claude をWindowsストア版パスで発見: {exe}")
            return str(exe)

    return "claude"


_CLAUDE_CMD = _find_claude()


class TokenExhaustedError(Exception):
    """Claude CLIのトークン上限に達した場合に raise する。"""
    pass


def _call_claude(prompt: str, retries: int = 2, model: str = MODEL_JUDGE) -> "str | None":
    """claude CLIをサブプロセスで呼び出し、レスポンステキストを返す。"""
    for attempt in range(1, retries + 2):
        try:
            cli_env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
            result = subprocess.run(
                [_CLAUDE_CMD, "-p", prompt, "--model", model, "--output-format", "text"],
                capture_output=True,
                timeout=CLI_TIMEOUT,
                env=cli_env,
            )
            # バイナリで受け取りUTF-8でデコード（Windows cp932問題を回避）
            stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
            stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
            combined = stdout + stderr

            # ── トークン切れ・残高不足の検出 ──────────────────────────────
            # 1次: returncode != 0 かつ stdout が JSON でない → エラー文言と判断
            # 2次: 既知のパターンマッチ（returncode=0 でも念のため）
            is_json_response = stdout.lstrip().startswith(("[", "{"))
            if result.returncode != 0 and not is_json_response:
                # エラー終了: stdout はエラーメッセージの可能性があるため使用しない
                # 既知のトークン切れパターンなら即 raise、それ以外はリトライ
                if any(p in combined for p in (
                    "out of extra usage", "out of usage credits",
                    "hit your limit", "session limit", "hit your session", "Asia/Tokyo",
                    "Credit balance", "credit balance",
                )):
                    raise TokenExhaustedError(combined.strip())
                logger.warning(f"claude CLI エラー終了（試行{attempt}）rc={result.returncode} stdout: {stdout[:200]} stderr: {stderr[:200]}")
            else:
                # returncode=0 でも既知パターンが混入していれば raise
                if any(p in combined for p in (
                    "out of extra usage", "out of usage credits",
                    "hit your limit", "session limit", "hit your session", "Asia/Tokyo",
                    "Credit balance", "credit balance",
                )):
                    raise TokenExhaustedError(combined.strip())
                if stdout.strip():
                    return stdout.strip()
                logger.warning(f"claude CLI 失敗（試行{attempt}）stderr: {stderr[:400]}")
        except subprocess.TimeoutExpired:
            logger.warning(f"claude CLI タイムアウト（試行{attempt}）")
        except FileNotFoundError:
            logger.error(f"claude コマンドが見つかりません（試行パス: {_CLAUDE_CMD}）。Claude Desktop がインストールされているか確認してください。")
            return None
        except Exception as e:
            err_msg = str(e)
            if any(p in err_msg for p in (
                "out of extra usage", "out of usage credits",
                "hit your limit", "session limit", "hit your session", "Asia/Tokyo",
                "Credit balance", "credit balance",
            )):
                raise TokenExhaustedError(err_msg)
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


def extract_main_kw(title: str, h2_list: list) -> str:
    """
    記事タイトルとH2見出しからメインKWをAIで抽出する（C列空白記事向け）。
    戻り値: メインKW文字列（失敗時は空文字列）
    """
    if not title:
        return ""

    template = (PROMPTS_DIR / "kw_extract.txt").read_text(encoding="utf-8")
    h2_text = " / ".join(h2_list[:6]) if h2_list else "（見出しなし）"
    prompt = template.format(title=title, h2_list=h2_text)

    response = _call_claude(prompt, model=MODEL_KW)
    if not response:
        logger.warning(f"KW抽出: AIレスポンスなし（タイトル: {title}）")
        return ""

    kw = response.strip().splitlines()[0].strip()

    # エラーメッセージが混入していないか検証
    if any(p in kw for p in ("out of", "hit your limit", "resets ", "usage")):
        logger.warning(f"KW抽出: エラー文字列を検出したためスキップ（{kw[:40]}）")
        return ""

    logger.info(f"KW抽出完了: 「{kw}」（タイトル: {title}）")
    return kw


def expand_keywords(target_kw: str) -> list:
    """
    KWの関連語・共起語・類義語をCowork内蔵AIで生成する。
    戻り値: キーワード文字列のリスト（失敗時は空リスト）
    """
    if not target_kw:
        return []

    template = (PROMPTS_DIR / "kw_expansion.txt").read_text(encoding="utf-8")
    prompt = template.format(target_kw=target_kw)

    response = _call_claude(prompt, model=MODEL_KW)
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


def judge_relevance_batch(target: dict, candidates: list[dict], body_chars: int = 300) -> list[dict]:
    """
    候補記事の関連性を一括スコアリングする（トークン節約版）。
    1回のAI呼び出しで全候補を判定する。
    body_chars: 候補記事の本文抜粋文字数（--lean 時は150）
    戻り値: [{"url", "score", "reason", "recommended_heading"}, ...]
            失敗時は空リスト
    """
    if not candidates:
        return []

    template = (PROMPTS_DIR / "relevance_judge_batch.txt").read_text(encoding="utf-8")

    # 候補記事ブロックを組み立て
    lines = []
    for c in candidates:
        h = (c.get("h2_list", [])[:3] + c.get("h3_list", [])[:2])
        headings = " / ".join(h) if h else "（見出しなし）"
        lines.append(
            f"- URL: {c.get('url', '')}\n"
            f"  タイトル: {c.get('title', '')}\n"
            f"  見出し: {headings}\n"
            f"  本文冒頭: {c.get('body_text', '')[:body_chars]}"
        )
    candidates_block = "\n\n".join(lines)

    t_headings = (target.get("h2_list", [])[:3] + target.get("h3_list", [])[:2])
    prompt = template.format(
        target_kw=target.get("kw", ""),
        target_url=target.get("url", ""),
        target_title=target.get("title", "") or target.get("h1", ""),
        target_headings=" / ".join(t_headings) if t_headings else "（見出しなし）",
        target_body=target.get("body_text", "")[:300],
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


# ============================================================
# Anthropic API 直接呼び出し（--api モード用）
# ============================================================

def _get_anthropic_client():
    """同期 Anthropic クライアントを返す。"""
    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError("anthropicパッケージが未インストールです。pip install anthropic を実行してください。")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("環境変数 ANTHROPIC_API_KEY が設定されていません。")
    return Anthropic(api_key=api_key)


def expand_keywords_sync_api(target_kw: str) -> list:
    """expand_keywords の Anthropic API 同期版（--api モード用）。"""
    if not target_kw:
        return []
    template = (PROMPTS_DIR / "kw_expansion.txt").read_text(encoding="utf-8")
    prompt = template.format(target_kw=target_kw)
    try:
        client = _get_anthropic_client()
        response = client.messages.create(
            model=MODEL_KW, max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else ""
    except Exception as e:
        logger.warning(f"KW拡張（API）エラー: {e}")
        return []
    raw = _extract_json(text, "[")
    if not raw:
        return []
    try:
        kws = json.loads(raw)
        return [str(k) for k in kws] if isinstance(kws, list) else []
    except json.JSONDecodeError:
        return []


async def extract_main_kw_api_async(async_client, title: str, h2_list: list) -> str:
    """extract_main_kw の Anthropic API 非同期版（--api モード用）。"""
    import asyncio as _asyncio
    if not title:
        return ""
    template = (PROMPTS_DIR / "kw_extract.txt").read_text(encoding="utf-8")
    h2_text = " / ".join(h2_list[:6]) if h2_list else "（見出しなし）"
    prompt = template.format(title=title, h2_list=h2_text)
    for attempt in range(4):
        try:
            response = await async_client.messages.create(
                model=MODEL_KW, max_tokens=64,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip() if response.content else ""
            kw = text.splitlines()[0].strip() if text else ""
            if any(p in kw for p in ("out of", "hit your limit", "resets ", "usage")):
                return ""
            return kw
        except Exception as e:
            err = str(e)
            if ("429" in err or "rate_limit" in err) and attempt < 3:
                wait = 30 * (attempt + 1)
                logger.warning(f"KW抽出レート制限: {wait}秒待機（試行{attempt + 1}/4）")
                await _asyncio.sleep(wait)
                continue
            logger.warning(f"KW抽出（API非同期）エラー: {e}")
            return ""
    return ""


async def judge_relevance_batch_api_async(
    async_client,
    target: dict,
    candidates: list[dict],
    body_chars: int = 300,
) -> list[dict]:
    """judge_relevance_batch の Anthropic API 非同期版（--api モード用）。"""
    if not candidates:
        return []

    template = (PROMPTS_DIR / "relevance_judge_batch.txt").read_text(encoding="utf-8")
    lines = []
    for c in candidates:
        h = (c.get("h2_list", [])[:3] + c.get("h3_list", [])[:2])
        headings = " / ".join(h) if h else "（見出しなし）"
        lines.append(
            f"- URL: {c.get('url', '')}\n"
            f"  タイトル: {c.get('title', '')}\n"
            f"  見出し: {headings}\n"
            f"  本文冒頭: {c.get('body_text', '')[:body_chars]}"
        )
    t_headings = (target.get("h2_list", [])[:3] + target.get("h3_list", [])[:2])
    prompt = template.format(
        target_kw=target.get("kw", ""),
        target_url=target.get("url", ""),
        target_title=target.get("title", "") or target.get("h1", ""),
        target_headings=" / ".join(t_headings) if t_headings else "（見出しなし）",
        target_body=target.get("body_text", "")[:300],
        candidates_block="\n\n".join(lines),
    )
    text = ""
    for attempt in range(4):
        try:
            response = await async_client.messages.create(
                model=MODEL_JUDGE, max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text if response.content else ""
            break
        except Exception as e:
            err = str(e)
            if ("429" in err or "rate_limit" in err) and attempt < 3:
                wait = 30 * (attempt + 1)
                logger.warning(f"API判定レート制限: {wait}秒待機（試行{attempt + 1}/4）")
                import asyncio as _asyncio
                await _asyncio.sleep(wait)
                continue
            logger.warning(f"API判定エラー: {e}")
            return []
    if not text:
        return []

    raw = _extract_json(text, "[")
    if not raw:
        logger.warning("API判定: JSON配列が見つかりません")
        return []
    try:
        results = json.loads(raw)
        if not isinstance(results, list):
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
        logger.info(f"API判定完了: {len(out)} 件（{target.get('url', '')[:40]}）")
        return out
    except json.JSONDecodeError as e:
        logger.warning(f"API判定: JSON解析失敗 — {e}")
    return []
