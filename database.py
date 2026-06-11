"""
Slovoyad – MariaDB persistence layer.

Stores article evaluations with versioning: the same URL can be evaluated
multiple times, each receiving an auto-incrementing version number.
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional

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


def _row_to_dict(row: dict) -> Optional[dict]:
    """Convert a raw DB row into a friendlier Python dict."""
    if row is None:
        return None
    row = dict(row)
    for field in ("justifications", "strengths", "weaknesses", "spelling_errors", "raw_response"):
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
                    ai_probability, ai_reasoning, confidence,
                    spelling_errors,
                    raw_response
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s,
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
                    _serialize_json({
                        "originality_reason": evaluation.get("originality_reason", ""),
                        "significance_reason": evaluation.get("significance_reason", ""),
                        "quality_reason": evaluation.get("quality_reason", ""),
                        "trust_reason": evaluation.get("trust_reason", ""),
                        "domain_specific_reason": evaluation.get("domain_specific_reason", ""),
                    }),
                    _serialize_json(evaluation.get("strengths")),
                    _serialize_json(evaluation.get("weaknesses")),
                    evaluation.get("ai_probability", 0),
                    evaluation.get("ai_reasoning", ""),
                    evaluation.get("confidence", None),
                    _serialize_json(evaluation.get("spelling_errors", [])),
                    _serialize_json(evaluation.get("raw_response")),
                ),
            )
            conn.commit()
            eval_id = cur.lastrowid
        return next_version, eval_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_latest_evaluation(url: str) -> Optional[dict]:
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


def get_all_versions(url: str) -> List[dict]:
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


# ---------------------------------------------------------------------------
# Paginated evaluations & single-record ops
# ---------------------------------------------------------------------------

def get_evaluations_paginated(page: int = 1, per_page: int = 20,
                               search: str = None, domain: str = None) -> dict:
    """Get paginated evaluations with optional search and domain filter.
    Returns {items: list, total: int, page: int, per_page: int, total_pages: int}
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            where_clauses = []
            params = []
            if search:
                where_clauses.append('(title_scraped LIKE %s OR url LIKE %s)')
                params.extend([f'%{search}%', f'%{search}%'])
            if domain:
                where_clauses.append('domain = %s')
                params.append(domain)

            where = 'WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''

            cur.execute(f'SELECT COUNT(*) as cnt FROM evaluations {where}', params)
            total = cur.fetchone()['cnt']

            offset = (page - 1) * per_page
            cur.execute(
                f'SELECT * FROM evaluations {where} ORDER BY evaluated_at DESC LIMIT %s OFFSET %s',
                params + [per_page, offset]
            )
            items = [_row_to_dict(row) for row in cur.fetchall()]

            return {
                'items': items,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }
    finally:
        conn.close()


def get_evaluation_by_id(eval_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM evaluations WHERE id = %s', (eval_id,))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
    finally:
        conn.close()


def delete_evaluation(eval_id: int) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM evaluations WHERE id = %s', (eval_id,))
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def get_all_domains() -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT DISTINCT domain FROM evaluations ORDER BY domain')
            return [row['domain'] for row in cur.fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Group operations
# ---------------------------------------------------------------------------

def create_group(name: str, urls: list[str], created_by: int = None) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conn.begin()
            cur.execute(
                'INSERT INTO evaluation_groups (name, created_by, total_urls, status) VALUES (%s, %s, %s, %s)',
                (name, created_by, len(urls), 'pending')
            )
            group_id = cur.lastrowid
            for url in urls:
                cur.execute(
                    'INSERT INTO group_urls (group_id, url) VALUES (%s, %s)',
                    (group_id, url.strip())
                )
            conn.commit()
        return group_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_groups(page: int = 1, per_page: int = 20) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) as cnt FROM evaluation_groups')
            total = cur.fetchone()['cnt']
            offset = (page - 1) * per_page
            cur.execute(
                'SELECT g.*, u.email as created_by_email '
                'FROM evaluation_groups g '
                'LEFT JOIN users u ON g.created_by = u.id '
                'ORDER BY g.created_at DESC LIMIT %s OFFSET %s',
                (per_page, offset)
            )
            items = []
            for row in cur.fetchall():
                r = dict(row)
                if isinstance(r.get('created_at'), datetime):
                    r['created_at'] = r['created_at'].isoformat()
                items.append(r)
            return {'items': items, 'total': total, 'page': page, 'per_page': per_page}
    finally:
        conn.close()


def get_group_detail(group_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT g.*, u.email as created_by_email '
                'FROM evaluation_groups g '
                'LEFT JOIN users u ON g.created_by = u.id '
                'WHERE g.id = %s', (group_id,)
            )
            group = cur.fetchone()
            if not group:
                return None
            group = dict(group)
            if isinstance(group.get('created_at'), datetime):
                group['created_at'] = group['created_at'].isoformat()

            cur.execute(
                'SELECT gu.*, e.title_scraped, e.final_overall_score '
                'FROM group_urls gu '
                'LEFT JOIN evaluations e ON gu.evaluation_id = e.id '
                'WHERE gu.group_id = %s ORDER BY gu.id',
                (group_id,)
            )
            urls = []
            for row in cur.fetchall():
                r = dict(row)
                if isinstance(r.get('created_at'), datetime):
                    r['created_at'] = r['created_at'].isoformat()
                urls.append(r)
            group['urls'] = urls
            return group
    finally:
        conn.close()


def delete_group(group_id: int) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM evaluation_groups WHERE id = %s', (group_id,))
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def get_next_pending_url(group_id: int = None) -> Optional[dict]:
    """Get next pending URL from queue."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if group_id:
                cur.execute(
                    'SELECT * FROM group_urls WHERE group_id = %s AND status = %s ORDER BY id LIMIT 1',
                    (group_id, 'pending')
                )
            else:
                cur.execute(
                    'SELECT * FROM group_urls WHERE status = %s ORDER BY id LIMIT 1',
                    ('pending',)
                )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def update_group_url_status(url_id: int, status: str, evaluation_id: int = None, error_message: str = None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if evaluation_id:
                cur.execute(
                    'UPDATE group_urls SET status=%s, evaluation_id=%s WHERE id=%s',
                    (status, evaluation_id, url_id)
                )
            elif error_message:
                cur.execute(
                    'UPDATE group_urls SET status=%s, error_message=%s, retries=retries+1 WHERE id=%s',
                    (status, error_message, url_id)
                )
            else:
                cur.execute('UPDATE group_urls SET status=%s WHERE id=%s', (status, url_id))
            conn.commit()
    finally:
        conn.close()


def update_group_counters(group_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'UPDATE evaluation_groups SET '
                'completed_urls = (SELECT COUNT(*) FROM group_urls WHERE group_id=%s AND status="completed"), '
                'failed_urls = (SELECT COUNT(*) FROM group_urls WHERE group_id=%s AND status="failed") '
                'WHERE id = %s',
                (group_id, group_id, group_id)
            )
            # Check if all done
            cur.execute(
                'SELECT COUNT(*) as pending FROM group_urls WHERE group_id=%s AND status IN ("pending","processing")',
                (group_id,)
            )
            pending = cur.fetchone()['pending']
            if pending == 0:
                cur.execute(
                    'UPDATE evaluation_groups SET status="completed" WHERE id=%s',
                    (group_id,)
                )
            conn.commit()
    finally:
        conn.close()


def get_group_url_retry_count(url_id: int) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT retries FROM group_urls WHERE id=%s', (url_id,))
            row = cur.fetchone()
            return row['retries'] if row else 0
    finally:
        conn.close()
