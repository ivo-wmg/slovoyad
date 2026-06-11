"""
scraper.py – Извличане на съдържание от статии по URL.

Основен метод: newspaper4k
Резервен метод: BeautifulSoup4
"""

import logging
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
from newspaper import Article

from utils import extract_domain

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_TEXT_LENGTH = 100  # chars – below this the primary extraction is considered failed

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "bg,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_REQUEST_TIMEOUT = 15  # seconds

_ARTICLE_SELECTORS = [
    "article",
    ".article-body",
    ".post-content",
    ".entry-content",
    "[itemprop='articleBody']",
]

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class ScrapingError(Exception):
    """Raised when article scraping fails irrecoverably."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

import re

_MULTI_SPACE = re.compile(r'[ \t]+')
_MULTI_NEWLINE = re.compile(r'\n{3,}')


def _clean_paragraph(tag) -> str:
    """Extract text from a BS4 tag, adding spaces between child elements
    to prevent word merging (e.g. <a>нещо</a>е → 'нещо е' not 'нещое').
    """
    text = tag.get_text(separator=' ')
    text = _MULTI_SPACE.sub(' ', text)
    return text.strip()


def _fetch_html(url: str) -> str:
    """Download raw HTML with proper headers and timeout."""
    try:
        response = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        raise ScrapingError(
            f"HTTP {status} при заявка към {url}"
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise ScrapingError(
            f"Таймаут ({_REQUEST_TIMEOUT}s) при заявка към {url}"
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise ScrapingError(
            f"Мрежова грешка при заявка към {url}: {exc}"
        ) from exc

    # Force UTF-8 to handle encoding issues
    response.encoding = "utf-8"
    return response.text


def _extract_via_newspaper(url: str) -> dict:
    """Primary extraction using newspaper4k."""
    try:
        article = Article(url, language="bg")
        article.set_html(_fetch_html(url))
        article.parse()

        title = (article.title or "").strip()
        text = (article.text or "").strip()
        authors = list(article.authors) if article.authors else []

        publish_date: Optional[str] = None
        if article.publish_date:
            if isinstance(article.publish_date, datetime):
                publish_date = article.publish_date.isoformat()
            else:
                publish_date = str(article.publish_date)

        return {
            "title": title,
            "text": text,
            "authors": authors,
            "publish_date": publish_date,
        }
    except ScrapingError:
        raise  # re-raise our own errors as-is
    except Exception as exc:
        logger.warning("newspaper4k не успя за %s: %s", url, exc)
        return {"title": "", "text": "", "authors": [], "publish_date": None}


def _extract_via_bs4(html: str) -> dict:
    """Fallback extraction using BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")

    # --- Title -----------------------------------------------------------
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()

    # --- Body text -------------------------------------------------------
    text = ""
    for selector in _ARTICLE_SELECTORS:
        container = soup.select_one(selector)
        if container:
            # Remove related-articles, widgets, sidebars, nav blocks
            for junk in container.select(
                '.related, .related-articles, .related-posts, '
                '.read-more, .see-also, .widget, .sidebar, '
                '.article-tags, .tags, .share, .social, '
                'aside, nav, .newsletter, .promo, .ad, '
                '[class*="related"], [class*="widget"], '
                '[class*="sidebar"], [class*="promo"]'
            ):
                junk.decompose()

            paragraphs = container.find_all("p")
            if paragraphs:
                text = "\n\n".join(_clean_paragraph(p) for p in paragraphs)
            else:
                text = container.get_text(separator=" ", strip=True)
            if len(text) >= _MIN_TEXT_LENGTH:
                break

    # Last resort: grab all <p> tags from the page
    if len(text) < _MIN_TEXT_LENGTH:
        all_paragraphs = soup.find_all("p")
        if all_paragraphs:
            text = "\n\n".join(_clean_paragraph(p) for p in all_paragraphs)

    return {
        "title": title,
        "text": text.strip(),
        "authors": [],
        "publish_date": None,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scrape_article(url: str) -> dict:
    """
    Scrape an article from *url* and return a dict with keys:
        title, text, authors, publish_date, url, domain

    Raises ``ScrapingError`` on irrecoverable failures.
    """
    logger.info("Извличане на статия: %s", url)

    # 1. Try newspaper4k (primary) ----------------------------------------
    result = _extract_via_newspaper(url)

    # 2. Fallback to BS4 if text is missing / too short -------------------
    if len(result.get("text", "")) < _MIN_TEXT_LENGTH:
        logger.info("newspaper4k върна кратък текст – превключване към BS4 за %s", url)
        try:
            html = _fetch_html(url)
            bs4_result = _extract_via_bs4(html)

            # Merge: prefer non-empty values from BS4
            if not result["title"] and bs4_result["title"]:
                result["title"] = bs4_result["title"]
            if len(bs4_result["text"]) > len(result.get("text", "")):
                result["text"] = bs4_result["text"]
        except ScrapingError:
            logger.warning("BS4 резервен метод също се провали за %s", url)

    # 3. Final validation -------------------------------------------------
    if len(result.get("text", "")) < _MIN_TEXT_LENGTH:
        raise ScrapingError(
            f"Не може да се извлече достатъчно текст от {url} "
            f"(получени {len(result.get('text', ''))} символа)"
        )

    # 4. Enrich with url & domain -----------------------------------------
    result["url"] = url
    result["domain"] = extract_domain(url)

    return result
