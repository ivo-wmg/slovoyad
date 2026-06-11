"""
Slovoyad – MariaDB persistence layer.

Stores article evaluations with versioning: the same URL can be evaluated
multiple times, each receiving an auto-incrementing version number.
"""

import hashlib
import json
from datetime import datetime

import pymysql
import pymysql.cursors

from config import get_db_config


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection():
    """Return a new PyMySQL connection using settings from config."""
    cfg = get_db_config()
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset=cfg.get("charset", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _url_hash(url: str) -> str:
    """Return the SHA-256 hex digest of *url*."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _serialize_json(value):
    """Serialize a Python object to a JSON string for storage."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _deserialize_json(value):
    """Deserialize a JSON string from the database back to a Python object."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def _row_to_dict(row: dict) -> dict:
    """Convert a raw DB row into a friendlier Python dict."""
    if row is None:
        return None
    row = dict(row)
    for field in ("justifications", "strengths", "weaknesses", "raw_response"):
        if field in row:
            row[field] = _deserialize_json(row[field])
    # Convert datetime objects to ISO strings for JSON-safety
    if isinstance(row.get("evaluated_at"), datetime):
        row["evaluated_at"] = row["evaluated_at"].isoformat()
    return row


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_evaluation(url: str, evaluation: dict) -> int:
    """
    Persist an evaluation result for *url*.

    Automatically calculates the next version number for this URL.
    Returns the new version number.
    """
    url_h = _url_hash(url)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Determine next version inside a transaction
            conn.begin()
            cur.execute(
                "SELECT COALESCE(MAX(version), 0) AS max_ver "
                "FROM evaluations WHERE url_hash = %s",
                (url_h,),
            )
            next_version = cur.fetchone()["max_ver"] + 1

            cur.execute(
                """
                INSERT INTO evaluations (
                    url, url_hash, domain, version,
                    title_scraped, classification,
                    originality, significance_locality,
                    quality_and_depth, trust_and_sources,
                    domain_specific_score, final_overall_score,
                    justifications, strengths, weaknesses,
                    raw_response
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s
                )
                """,
                (
                    url,
                    url_h,
                    evaluation.get("domain"),
                    next_version,
                    evaluation.get("title_scraped"),
                    evaluation.get("classification"),
                    evaluation.get("originality"),
                    evaluation.get("significance_locality"),
                    evaluation.get("quality_and_depth"),
                    evaluation.get("trust_and_sources"),
                    evaluation.get("domain_specific_score"),
                    evaluation.get("final_overall_score"),
                    _serialize_json(evaluation.get("justifications")),
                    _serialize_json(evaluation.get("strengths")),
                    _serialize_json(evaluation.get("weaknesses")),
                    _serialize_json(evaluation.get("raw_response")),
                ),
            )
            conn.commit()
        return next_version
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_latest_evaluation(url: str) -> dict | None:
    """Return the most recent evaluation for *url*, or ``None``."""
    url_h = _url_hash(url)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM evaluations "
                "WHERE url_hash = %s "
                "ORDER BY version DESC LIMIT 1",
                (url_h,),
            )
            row = cur.fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_all_versions(url: str) -> list[dict]:
    """Return every evaluation for *url*, newest version first."""
    url_h = _url_hash(url)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM evaluations "
                "WHERE url_hash = %s "
                "ORDER BY version DESC",
                (url_h,),
            )
            rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_version_count(url: str) -> int:
    """Return how many times *url* has been evaluated."""
    url_h = _url_hash(url)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM evaluations "
                "WHERE url_hash = %s",
                (url_h,),
            )
            return cur.fetchone()["cnt"]
    finally:
        conn.close()
