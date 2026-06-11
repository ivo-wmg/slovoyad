"""
Slovoyad — Utility Functions
URL parsing, logging setup, and display helpers.
"""

import logging
from typing import Tuple
from urllib.parse import urlparse

# --- Logging ---

def setup_logging(level=logging.INFO):
    """Configure logging for the application."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("newspaper").setLevel(logging.WARNING)

logger = logging.getLogger("slovoyad")


# --- URL Helpers ---

SUPPORTED_DOMAINS = {
    "news.bg",
    "money.bg",
    "infostock.bg",
    "topsport.bg",
    "lifestyle.bg",
    "chr.bg",
    "webcafe.bg",
    "mamamia.bg",
}


def extract_domain(url: str) -> str:
    """
    Extract the base domain from a URL.
    'https://www.money.bg/article/123' -> 'money.bg'
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    # Remove www. prefix
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname.lower()


def validate_url(url: str) -> Tuple[bool, str]:
    """
    Validate a URL and return (is_valid, error_message).
    """
    if not url or not url.strip():
        return False, "URL не може да бъде празен."

    url = url.strip()

    # Add https:// if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    if not parsed.hostname:
        return False, "Невалиден URL формат."

    domain = extract_domain(url)
    if domain not in SUPPORTED_DOMAINS:
        return False, f"Домейнът '{domain}' не се поддържа. Поддържани домейни: {', '.join(sorted(SUPPORTED_DOMAINS))}"

    return True, url


def format_score(score: float) -> str:
    """Format a score with color indicator."""
    if score >= 8:
        return f"🟢 {score}"
    elif score >= 5:
        return f"🟡 {score}"
    else:
        return f"🔴 {score}"
