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


def _clean_paragraph(tag) -> str:
    """Extract text from a BS4 tag, adding spaces between child elements
    to prevent word merging (e.g. <a>нещо</a>е → 'нещо е' not 'нещое').
    """
    text = tag.get_text(separator=' ')
    text = _MULTI_SPACE.sub(' ', text)
    return text.strip()


def _is_content_paragraph(p) -> bool:
    """Return True if this <p> is real article content, not a widget link.

    Filters out:
    1. <p> nested inside an <a> tag (e.g. reference-article widgets)
    2. <p> whose entire text is inside a single <a> child (e.g. leading-articles)
    """
    # Check 1: <p> inside an <a> ancestor
    for parent in p.parents:
        if parent.name == 'a':
            return False
        if parent.name in ('body', 'html', '[document]'):
            break

    # Check 2: <p> whose only meaningful content is a link
    links = p.find_all('a')
    if links:
        link_text = ' '.join(a.get_text(strip=True) for a in links)
        all_text = p.get_text(strip=True)
        if all_text and len(link_text) / len(all_text) > 0.9:
            return False

    return True


# Patterns for lines that are image captions or source credits
_JUNK_LINE_PATTERNS = [
    re.compile(r'^Снимка\s*\d+', re.IGNORECASE),
    re.compile(r'^Източник:\s', re.IGNORECASE),
    re.compile(r'^Фото:\s', re.IGNORECASE),
    re.compile(r'^Автор на снимката:', re.IGNORECASE),
    re.compile(r'^Снимка:', re.IGNORECASE),
    re.compile(r'^\(снимка\)', re.IGNORECASE),
    re.compile(r'^iStock$', re.IGNORECASE),
    re.compile(r'^Getty Images$', re.IGNORECASE),
    re.compile(r'^Shutterstock$', re.IGNORECASE),
]


def _postprocess_text(text: str) -> str:
    """Clean up extracted article text:
    - Remove duplicate consecutive paragraphs (from related-article widgets)
    - Remove image caption lines
    - Remove very short standalone lines that look like captions
    """
    paragraphs = text.split('\n\n')
    cleaned = []
    prev = None

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue

        # Skip exact duplicate of previous paragraph (widget titles)
        if p == prev:
            continue

        # Skip image caption/source lines
        if any(pat.search(p) for pat in _JUNK_LINE_PATTERNS):
            continue

        cleaned.append(p)
        prev = p

    return '\n\n'.join(cleaned)


def _strip_junk_blocks(container):
    """Remove non-content blocks from an article container.

    Uses two strategies:
    1. Known selectors (aside, nav, social, tags, etc.)
    2. Link-density heuristic: any div/section where >50% of text
       is inside <a> tags is likely a navigation/related widget.
    """
    # Strategy 1: known junk selectors
    for junk in container.select(
        'aside, nav, script, style, iframe, figure, '
        '.share, .social, .tags, .article-tags, '
        '.newsletter, .promo, .ad, .comments, '
        '.reference-article, .global-leading-articles-big, '
        '.global-leading-articles, .related-articles, .related'
    ):
        junk.decompose()

    # Strategy 2: link-density heuristic on remaining div/section blocks
    for block in container.find_all(['div', 'section']):
        total_text = block.get_text(separator=' ', strip=True)
        if len(total_text) < 20:
            continue  # too short to judge
        link_text = ' '.join(
            a.get_text(separator=' ', strip=True)
            for a in block.find_all('a')
        )
        link_ratio = len(link_text) / len(total_text) if total_text else 0
        # If >50% of text is links AND block has >1 link → widget
        link_count = len(block.find_all('a'))
        if link_ratio > 0.5 and link_count > 1:
            block.decompose()



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
        authors = list(article.authors) if article.authors else []

        publish_date: Optional[str] = None
        if article.publish_date:
            if isinstance(article.publish_date, datetime):
                publish_date = article.publish_date.isoformat()
            else:
                publish_date = str(article.publish_date)

        # Re-extract text from article HTML: strip divs, keep only <p> tags
        raw_text = (article.text or "").strip()
        article_html = getattr(article, 'article_html', '') or ''
        if article_html:
            soup = BeautifulSoup(article_html, "html.parser")
            # Remove all div/section/aside/figure/nav elements
            for tag in soup.find_all(['div', 'section', 'aside', 'figure', 'nav',
                                       'script', 'style', 'iframe']):
                tag.decompose()
            paragraphs = [p for p in soup.find_all('p') if _is_content_paragraph(p)]
            if paragraphs:
                cleaned = "\n\n".join(_clean_paragraph(p) for p in paragraphs if _clean_paragraph(p))
                if len(cleaned) >= _MIN_TEXT_LENGTH:
                    raw_text = cleaned

        return {
            "title": title,
            "text": raw_text,
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
            _strip_junk_blocks(container)

            paragraphs = [p for p in container.find_all("p") if _is_content_paragraph(p)]
            if paragraphs:
                text = "\n\n".join(_clean_paragraph(p) for p in paragraphs if _clean_paragraph(p))
            else:
                text = container.get_text(separator=" ", strip=True)
            if len(text) >= _MIN_TEXT_LENGTH:
                break

    # Last resort: grab all <p> tags from the page
    if len(text) < _MIN_TEXT_LENGTH:
        all_paragraphs = [p for p in soup.find_all("p") if _is_content_paragraph(p)]
        if all_paragraphs:
            text = "\n\n".join(_clean_paragraph(p) for p in all_paragraphs if _clean_paragraph(p))

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

    # 3. Post-process text (remove widget titles, image captions) ----------
    result["text"] = _postprocess_text(result.get("text", ""))

    # 4. Final validation -------------------------------------------------
    if len(result.get("text", "")) < _MIN_TEXT_LENGTH:
        raise ScrapingError(
            f"Не може да се извлече достатъчно текст от {url} "
            f"(получени {len(result.get('text', ''))} символа)"
        )

    # 5. Enrich with url & domain -----------------------------------------
    result["url"] = url
    result["domain"] = extract_domain(url)

    return result
