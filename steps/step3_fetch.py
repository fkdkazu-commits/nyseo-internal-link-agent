import time
import requests
from bs4 import BeautifulSoup
from config import HTTP_TIMEOUT, HTTP_RETRY, USER_AGENT, COL_URL, COL_KW
from utils.logger import get_logger

logger = get_logger()

HEADERS = {"User-Agent": USER_AGENT}


def fetch_all_articles(data: list[list[str]]) -> list[dict]:
    """
    STEP2（B案）用：全記事URLのtitle/h1/h2/h3/本文を一括取得する。
    失敗した記事はスキップしてログに記録する。
    """
    results = []
    total = len(data)

    for i, row in enumerate(data, start=1):
        url = row[COL_URL].strip() if len(row) > COL_URL else ""
        kw = row[COL_KW].strip() if len(row) > COL_KW else ""

        if not url:
            continue

        logger.info(f"全記事取得中 ({i}/{total}): {url}")
        parsed = _fetch_and_parse(url)
        if parsed:
            parsed["kw"] = kw
            results.append(parsed)

    logger.info(f"STEP3（一括取得）完了: {len(results)}/{total} 件取得成功")
    return results


def fetch_article(url: str) -> "dict | None":
    """単一記事URLのコンテンツを取得・解析して返す。失敗時はNoneを返す。"""
    return _fetch_and_parse(url)


def _fetch_and_parse(url: str) -> "dict | None":
    """HTTPリクエストを送信し、BeautifulSoupで解析した結果を返す。"""
    for attempt in range(1, HTTP_RETRY + 2):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            return _parse_html(url, resp.text)
        except requests.exceptions.Timeout:
            logger.warning(f"タイムアウト（試行{attempt}）: {url}")
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTPエラー {e.response.status_code}（試行{attempt}）: {url}")
            break  # 4xxエラーはリトライしない
        except Exception as e:
            logger.warning(f"取得エラー（試行{attempt}）: {url} — {e}")

        if attempt <= HTTP_RETRY:
            time.sleep(1)

    logger.warning(f"スキップ（最大リトライ超過）: {url}")
    return None


def _parse_html(url: str, html: str) -> dict:
    """HTMLからtitle/h1/h2/h3/本文を抽出して返す。"""
    soup = BeautifulSoup(html, "lxml")

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    h1 = soup.find("h1").get_text(strip=True) if soup.find("h1") else ""
    h2_list = [tag.get_text(strip=True) for tag in soup.find_all("h2")]
    h3_list = [tag.get_text(strip=True) for tag in soup.find_all("h3")]

    # 本文テキスト（先頭800文字）
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    body_text = soup.get_text(separator=" ", strip=True)[:800]

    return {
        "url": url,
        "title": title,
        "h1": h1,
        "h2_list": h2_list,
        "h3_list": h3_list,
        "body_text": body_text,
    }
