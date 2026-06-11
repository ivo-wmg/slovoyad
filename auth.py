"""
Slovoyad — Authentication module.

Provides password hashing, session management, and FastAPI auth dependency.
"""

import secrets
from datetime import datetime, timedelta

import bcrypt
import pymysql
import pymysql.cursors
from fastapi import Request, HTTPException

from config import get_db_config
from database import get_connection


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def create_session(user_id: int) -> str:
    """Create a new session for user_id, return the 64-char hex token."""
    token = secrets.token_hex(32)
    expires_at = datetime.now() + timedelta(days=30)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)",
                (token, user_id, expires_at),
            )
            conn.commit()
    finally:
        conn.close()
    return token


def get_session_user(token: str):
    """Return {id, email, role} for a valid session, or None."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT u.id, u.email, u.role "
                "FROM sessions s "
                "JOIN users u ON s.user_id = u.id "
                "WHERE s.token = %s AND s.expires_at > NOW()",
                (token,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def delete_session(token: str):
    """Delete a single session by token."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE token = %s", (token,))
            conn.commit()
    finally:
        conn.close()


def cleanup_expired_sessions():
    """Remove all expired sessions."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE expires_at < NOW()")
            conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def create_user(email: str, password: str, role: str = "admin") -> int:
    """Create a new user and return the user id."""
    pw_hash = hash_password(password)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s)",
                (email, pw_hash, role),
            )
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def get_all_users() -> list:
    """Return all users (id, email, role, created_at)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, role, created_at FROM users ORDER BY id")
            rows = cur.fetchall()
            result = []
            for row in rows:
                r = dict(row)
                if isinstance(r.get("created_at"), datetime):
                    r["created_at"] = r["created_at"].isoformat()
                result.append(r)
            return result
    finally:
        conn.close()


def delete_user(user_id: int):
    """Delete a user by id (cascades to sessions)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# FastAPI auth dependency
# ---------------------------------------------------------------------------

async def require_auth(request: Request) -> dict:
    """FastAPI Depends function — reads session_token cookie, returns user dict."""
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = get_session_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired")
    return user
