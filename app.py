"""
Slovoyad — Article Evaluation Web App
Minimal version for deploy testing.
"""

import os
import hmac
import hashlib
import subprocess

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Slovoyad", version="0.1.0")

DEPLOY_SECRET = os.getenv("DEPLOY_SECRET", "")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Static files ---

static_dir = os.path.join(BASE_DIR, "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "ok", "message": "Slovoyad is running", "version": "0.1.0"}


# --- Deploy Webhook ---

@app.post("/api/deploy")
async def github_deploy(request: Request):
    """GitHub webhook: auto-pull on push to main."""
    payload = await request.body()

    # Verify signature if secret is configured
    if DEPLOY_SECRET:
        signature = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(
            DEPLOY_SECRET.encode(), payload, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse payload
    try:
        import json
        data = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Only deploy on push to main
    ref = data.get("ref", "")
    if ref != "refs/heads/main":
        return {"status": "skipped", "reason": f"not main branch (got {ref})"}

    # Git pull
    result = subprocess.run(
        ["git", "pull", "origin", "main"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Run migrations
    migrate_result = subprocess.run(
        ["python3.11", "migrate.py"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Restart Passenger
    restart_dir = os.path.join(BASE_DIR, "tmp")
    os.makedirs(restart_dir, exist_ok=True)
    restart_file = os.path.join(restart_dir, "restart.txt")
    with open(restart_file, "w") as f:
        f.write("")

    return {
        "status": "deployed",
        "git_pull": result.stdout.strip(),
        "git_errors": result.stderr.strip() if result.stderr else None,
        "migrations": migrate_result.stdout.strip(),
        "migration_errors": migrate_result.stderr.strip() if migrate_result.stderr else None,
    }


# --- Health & Info ---

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/domains")
async def domains():
    return {
        "supported_domains": [
            "news.bg", "money.bg", "infostock.bg", "topsport.bg",
            "lifestyle.bg", "chr.bg", "webcafe.bg", "mamamia.bg"
        ]
    }
