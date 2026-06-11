"""
Slovoyad — Admin Panel API Router
Provides authentication, evaluation management, group operations,
user management, and stats endpoints for the admin panel.
"""

from fastapi import APIRouter, Request, HTTPException, Depends, Response
from fastapi.responses import FileResponse, JSONResponse
import os
from auth import (
    require_auth, hash_password, verify_password,
    create_session, delete_session, create_user,
    get_all_users, delete_user, get_session_user,
)
from database import (
    get_evaluations_paginated, get_evaluation_by_id, delete_evaluation,
    get_all_domains, create_group, get_groups, get_group_detail,
    delete_group, get_connection,
)
from utils import logger

router = APIRouter()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MANAGE_DIR = os.path.join(BASE_DIR, 'static', 'manage')


# ---------------------------------------------------------------------------
# Auth endpoints (NO auth required)
# ---------------------------------------------------------------------------

@router.post('/manage/api/login')
async def api_login(request: Request):
    """Authenticate user and create a session."""
    body = await request.json()
    email = body.get('email', '').strip().lower()
    password = body.get('password', '')
    if not email or not password:
        raise HTTPException(400, 'Email and password required')

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM users WHERE email = %s', (email,))
            user = cur.fetchone()
    finally:
        conn.close()

    if not user or not verify_password(password, user['password_hash']):
        raise HTTPException(401, 'Invalid credentials')

    token = create_session(user['id'])
    response = JSONResponse({
        'success': True,
        'user': {'email': user['email'], 'role': user['role']},
    })
    response.set_cookie(
        'session_token', token,
        httponly=True, max_age=30 * 86400, samesite='lax', path='/',
    )
    return response


@router.post('/manage/api/logout')
async def api_logout(request: Request):
    """Delete the current session and clear the cookie."""
    token = request.cookies.get('session_token')
    if token:
        delete_session(token)
    response = JSONResponse({'success': True})
    response.delete_cookie('session_token', path='/')
    return response


# ---------------------------------------------------------------------------
# Protected endpoints (require auth)
# ---------------------------------------------------------------------------

# --- Evaluations ---

@router.get('/manage/api/evaluations')
async def api_evaluations(
    page: int = 1,
    per_page: int = 20,
    search: str = '',
    domain: str = '',
    user=Depends(require_auth),
):
    """List evaluations with pagination, search, and domain filter."""
    result = get_evaluations_paginated(
        page=page, per_page=per_page, search=search, domain=domain,
    )
    return result


@router.get('/manage/api/evaluations/{eval_id}')
async def api_evaluation_detail(eval_id: int, user=Depends(require_auth)):
    """Get a single evaluation by ID."""
    evaluation = get_evaluation_by_id(eval_id)
    if not evaluation:
        raise HTTPException(404, 'Evaluation not found')
    return evaluation


@router.delete('/manage/api/evaluations/{eval_id}')
async def api_delete_evaluation(eval_id: int, user=Depends(require_auth)):
    """Delete an evaluation by ID."""
    delete_evaluation(eval_id)
    return {'success': True}


# --- Domains ---

@router.get('/manage/api/domains')
async def api_domains(user=Depends(require_auth)):
    """Return all domains that have evaluations."""
    return {'domains': get_all_domains()}


# --- Groups ---

@router.get('/manage/api/groups')
async def api_groups(
    page: int = 1,
    per_page: int = 20,
    user=Depends(require_auth),
):
    """List evaluation groups with pagination."""
    result = get_groups(page=page, per_page=per_page)
    return result


@router.post('/manage/api/groups')
async def api_create_group(request: Request, user=Depends(require_auth)):
    """Create a new evaluation group with a list of URLs."""
    body = await request.json()
    name = body.get('name', '').strip()
    urls_text = body.get('urls', '')

    if not name:
        raise HTTPException(400, 'Group name is required')

    # Parse URLs from newline-separated text
    urls = [u.strip() for u in urls_text.split('\n') if u.strip()]
    if not urls:
        raise HTTPException(400, 'At least one URL is required')
    if len(urls) > 100:
        raise HTTPException(400, 'Maximum 100 URLs per group')

    group_id = create_group(name, urls)

    # Start bulk worker
    from bulk_worker import start_worker
    start_worker()

    return {'success': True, 'group_id': group_id}


@router.get('/manage/api/groups/{group_id}')
async def api_group_detail(group_id: int, user=Depends(require_auth)):
    """Get full group detail including URLs."""
    detail = get_group_detail(group_id)
    if not detail:
        raise HTTPException(404, 'Group not found')
    return detail


@router.delete('/manage/api/groups/{group_id}')
async def api_delete_group(group_id: int, user=Depends(require_auth)):
    """Delete a group by ID."""
    delete_group(group_id)
    return {'success': True}


# --- Users ---

@router.get('/manage/api/users')
async def api_users(user=Depends(require_auth)):
    """List all admin users."""
    return {'users': get_all_users()}


@router.post('/manage/api/users')
async def api_create_user(request: Request, user=Depends(require_auth)):
    """Create a new admin user."""
    body = await request.json()
    email = body.get('email', '').strip().lower()
    password = body.get('password', '')

    if not email or not password:
        raise HTTPException(400, 'Email and password required')

    user_id = create_user(email, password)
    return {'success': True, 'user_id': user_id}


@router.delete('/manage/api/users/{user_id}')
async def api_delete_user(user_id: int, user=Depends(require_auth)):
    """Delete an admin user by ID."""
    delete_user(user_id)
    return {'success': True}


@router.get('/manage/api/users/{user_id}')
async def api_get_user(user_id: int, user=Depends(require_auth)):
    """Get a single user by ID."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, email, role, created_at FROM users WHERE id = %s', (user_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, 'User not found')
            result = dict(row)
            from datetime import datetime
            if isinstance(result.get('created_at'), datetime):
                result['created_at'] = result['created_at'].isoformat()
            return result
    finally:
        conn.close()


@router.put('/manage/api/users/{user_id}')
async def api_update_user(user_id: int, request: Request, user=Depends(require_auth)):
    """Update user email, role, and optionally password."""
    body = await request.json()
    email = body.get('email', '').strip().lower()
    role = body.get('role', 'admin')
    password = body.get('password', '')

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if password:
                from auth import hash_password
                pw_hash = hash_password(password)
                cur.execute(
                    'UPDATE users SET email=%s, role=%s, password_hash=%s WHERE id=%s',
                    (email, role, pw_hash, user_id)
                )
            else:
                cur.execute(
                    'UPDATE users SET email=%s, role=%s WHERE id=%s',
                    (email, role, user_id)
                )
            conn.commit()
    finally:
        conn.close()
    return {'success': True}


# --- Stats ---

@router.get('/manage/api/stats')
async def api_stats(user=Depends(require_auth)):
    """Return dashboard statistics."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) AS cnt FROM evaluations')
            total_evaluations = cur.fetchone()['cnt']

            cur.execute('SELECT COUNT(*) AS cnt FROM evaluation_groups')
            total_groups = cur.fetchone()['cnt']

            cur.execute('SELECT COUNT(*) AS cnt FROM users')
            total_users = cur.fetchone()['cnt']

            cur.execute(
                'SELECT COUNT(*) AS cnt FROM evaluations '
                'WHERE DATE(evaluated_at) = CURDATE()'
            )
            evaluations_today = cur.fetchone()['cnt']
    finally:
        conn.close()

    return {
        'total_evaluations': total_evaluations,
        'total_groups': total_groups,
        'total_users': total_users,
        'evaluations_today': evaluations_today,
    }


# ---------------------------------------------------------------------------
# HTML page routes (serve static files)
# ---------------------------------------------------------------------------

@router.get('/manage/login')
async def manage_login():
    return FileResponse(os.path.join(MANAGE_DIR, 'login.html'))


@router.get('/manage')
@router.get('/manage/')
async def manage_index():
    return FileResponse(os.path.join(MANAGE_DIR, 'index.html'))


@router.get('/manage/evaluations')
async def manage_evaluations():
    return FileResponse(os.path.join(MANAGE_DIR, 'evaluations.html'))


@router.get('/manage/evaluations/{eval_id}')
async def manage_evaluation_detail(eval_id: int):
    return FileResponse(os.path.join(MANAGE_DIR, 'evaluation-detail.html'))


@router.get('/manage/groups')
async def manage_groups():
    return FileResponse(os.path.join(MANAGE_DIR, 'groups.html'))


@router.get('/manage/groups/{group_id}')
async def manage_group_detail(group_id: int):
    return FileResponse(os.path.join(MANAGE_DIR, 'group-detail.html'))


@router.get('/manage/users')
async def manage_users():
    return FileResponse(os.path.join(MANAGE_DIR, 'users.html'))


@router.get('/manage/users/add')
async def manage_user_add():
    return FileResponse(os.path.join(MANAGE_DIR, 'user-form.html'))


@router.get('/manage/users/{user_id}/edit')
async def manage_user_edit(user_id: int):
    return FileResponse(os.path.join(MANAGE_DIR, 'user-form.html'))
