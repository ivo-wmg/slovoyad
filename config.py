"""
Slovoyad — Configuration
Loads settings from .env and exposes them as module-level constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Gemini API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# --- Database ---
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_DATABASE = os.getenv("DB_DATABASE", "slovoyad")
DB_USERNAME = os.getenv("DB_USERNAME", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# --- Deploy ---
DEPLOY_SECRET = os.getenv("DEPLOY_SECRET", "")

# --- Scoring Weights ---
# Must sum to 1.0
SCORING_WEIGHTS = {
    "domain_specific_score": 0.35,
    "originality": 0.25,
    "trust_and_sources": 0.20,
    "quality_and_depth": 0.10,
    "significance_locality": 0.10,
}

def get_db_config():
    """Return dict suitable for PyMySQL connection."""
    return {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USERNAME,
        "password": DB_PASSWORD,
        "database": DB_DATABASE,
        "charset": "utf8mb4",
    }
