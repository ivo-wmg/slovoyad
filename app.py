"""
Slovoyad — Article Evaluation Web App
FastAPI application with evaluation, history, and deploy endpoints.
"""

import os
import hmac
import json
import hashlib
import subprocess

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from dotenv import load_dotenv

load_dotenv()

from config import DEPLOY_SECRET, GEMINI_MODEL
from models import EvaluateRequest, ArticleEvaluation, EvaluationResponse, VersionHistoryResponse
from utils import extract_domain, validate_url, setup_logging, logger, SUPPORTED_DOMAINS
from domains import get_domain_config, UnsupportedDomainError
from scraper import scrape_article, ScrapingError
from evaluator import ArticleEvaluator
from database import save_evaluation, get_latest_evaluation, get_all_versions, get_version_count

setup_logging()

app = FastAPI(title="Slovoyad", version="0.1.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Admin panel ---
from admin import router as admin_router
app.include_router(admin_router)

# --- Static files ---

static_dir = os.path.join(BASE_DIR, "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# --- Pages ---

@app.get("/")
async def index():
    """Serve the main page."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "ok", "message": "Slovoyad is running", "version": "0.1.0"}


# --- API: Evaluate ---

# --- Public permalink for saved evaluations ---

@app.get("/evaluations/{eval_id}")
async def public_evaluation(eval_id: int):
    """Serve the main page for a saved evaluation (public permalink)."""
    index_path = os.path.join(static_dir, "index.html")
    return FileResponse(index_path)


@app.get("/api/evaluations/{eval_id}")
async def api_evaluation_public(eval_id: int):
    """Return a stored evaluation by ID (public, no auth), with version history."""
    from database import get_evaluation_by_id, get_all_versions
    evaluation = get_evaluation_by_id(eval_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    # Include version history for the same URL
    url = evaluation.get("url", "")
    all_versions = get_all_versions(url) if url else []
    evaluation["version_history"] = [
        {"id": v.get("id"), "version": v.get("version"), "evaluated_at": v.get("evaluated_at"),
         "final_overall_score": v.get("final_overall_score")}
        for v in all_versions
    ]
    return evaluation



@app.post("/api/evaluate")
async def api_evaluate(request: EvaluateRequest):
    """
    Evaluate an article URL.
    Returns the current evaluation + version history.
    """
    # 1. Validate URL
    is_valid, result = validate_url(request.url)
    if not is_valid:
        raise HTTPException(status_code=400, detail=result)
    url = result  # cleaned URL

    # 2. Extract domain and get config
    domain = extract_domain(url)
    try:
        domain_config = get_domain_config(domain)
    except UnsupportedDomainError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3. Scrape article
    try:
        logger.info(f"Scraping: {url}")
        article_data = scrape_article(url)
    except ScrapingError as e:
        raise HTTPException(status_code=422, detail=f"Грешка при извличане на статията: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected scraping error: {e}")
        raise HTTPException(status_code=500, detail=f"Неочаквана грешка при извличане: {str(e)}")

    # 4. Evaluate with Gemini
    try:
        logger.info(f"Evaluating with {request.model or GEMINI_MODEL}...")
        evaluator = ArticleEvaluator(model=request.model)
        evaluation = evaluator.evaluate(article_data, domain_config)
    except Exception as e:
        logger.error(f"Evaluation error: {e}")
        raise HTTPException(status_code=500, detail=f"Грешка при анализа: {str(e)}")

    # 5. Save to database
    try:
        eval_dict = evaluation.model_dump()
        version, eval_id = save_evaluation(url, eval_dict)
        logger.info(f"Saved evaluation v{version} id={eval_id} for {domain}")
    except Exception as e:
        logger.error(f"Database save error: {e}")
        # Don't fail the request if DB save fails — return the evaluation anyway
        version = 0
        eval_id = None

    # 6. Build response with version history
    try:
        all_versions = get_all_versions(url)
        current_response = EvaluationResponse(
            evaluation=evaluation,
            version=version,
            evaluated_at=all_versions[0]["evaluated_at"] if all_versions else "",
            url=url,
            id=eval_id,
        )

        previous_responses = []
        for v in all_versions[1:]:
            prev_eval = _db_row_to_evaluation(v)
            previous_responses.append(EvaluationResponse(
                evaluation=prev_eval,
                version=v["version"],
                evaluated_at=v.get("evaluated_at", ""),
                url=url,
            ))

        score_evolution = [float(v["final_overall_score"]) for v in reversed(all_versions)]

        return VersionHistoryResponse(
            current=current_response,
            previous_versions=previous_responses,
            total_versions=len(all_versions),
            score_evolution=score_evolution,
        )

    except Exception as e:
        logger.error(f"Error building history response: {e}")
        # Fallback: return just the current evaluation without history
        return VersionHistoryResponse(
            current=EvaluationResponse(
                evaluation=evaluation,
                version=version,
                evaluated_at="",
                url=url,
            ),
            previous_versions=[],
            total_versions=1,
            score_evolution=[evaluation.final_overall_score],
        )


# --- API: History ---

@app.get("/api/history")
async def api_history(url: str):
    """Get evaluation history for a URL."""
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")

    all_versions = get_all_versions(url)
    if not all_versions:
        raise HTTPException(status_code=404, detail="Няма намерени оценки за този URL.")

    responses = []
    for v in all_versions:
        eval_obj = _db_row_to_evaluation(v)
        responses.append(EvaluationResponse(
            evaluation=eval_obj,
            version=v["version"],
            evaluated_at=v.get("evaluated_at", ""),
            url=url,
        ))

    score_evolution = [float(v["final_overall_score"]) for v in reversed(all_versions)]

    return VersionHistoryResponse(
        current=responses[0],
        previous_versions=responses[1:],
        total_versions=len(responses),
        score_evolution=score_evolution,
    )


# --- API: Domains ---

@app.get("/api/domains")
async def api_domains():
    """Return list of supported domains."""
    return {"supported_domains": sorted(SUPPORTED_DOMAINS)}


# --- API: Health ---

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.2.0", "model": GEMINI_MODEL}


# --- API: PDF Export ---

@app.get("/api/pdf")
async def api_pdf(url: str):
    """Generate PDF report for the latest evaluation of a URL."""
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")

    latest = get_latest_evaluation(url)
    if not latest:
        raise HTTPException(status_code=404, detail="No evaluation found for this URL")

    try:
        from pdf_generator import generate_evaluation_pdf

        eval_dict = dict(latest)
        # Parse JSON fields
        for key in ("justifications", "strengths", "weaknesses", "spelling_errors"):
            val = eval_dict.get(key)
            if isinstance(val, str):
                import json as _json
                try:
                    eval_dict[key] = _json.loads(val)
                except Exception:
                    pass

        # Flatten justifications into eval_dict
        justs = eval_dict.pop("justifications", {}) or {}
        if isinstance(justs, dict):
            eval_dict.update(justs)

        pdf_bytes = generate_evaluation_pdf(
            eval_data=eval_dict,
            url=url,
            version=eval_dict.get("version", 1),
            evaluated_at=str(eval_dict.get("evaluated_at", "")),
        )

        from datetime import datetime
        domain = eval_dict.get("domain", "report")
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{domain}-{ts}.pdf"'
            },
        )
    except ImportError:
        raise HTTPException(status_code=500, detail="PDF generation not available (weasyprint not installed)")
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")


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
        ["python3.9", "migrate.py"],
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


# --- Helpers ---

def _db_row_to_evaluation(row: dict) -> ArticleEvaluation:
    """Convert a database row dict to an ArticleEvaluation model."""
    justifications = row.get("justifications", {})
    if isinstance(justifications, str):
        justifications = json.loads(justifications)

    strengths = row.get("strengths", [])
    if isinstance(strengths, str):
        strengths = json.loads(strengths)

    weaknesses = row.get("weaknesses", [])
    if isinstance(weaknesses, str):
        weaknesses = json.loads(weaknesses)

    return ArticleEvaluation(
        domain=row.get("domain", ""),
        title_scraped=row.get("title_scraped", ""),
        classification=row.get("classification", ""),
        originality_reason=justifications.get("originality_reason", ""),
        originality=row.get("originality", 5),
        significance_reason=justifications.get("significance_reason", ""),
        significance_locality=row.get("significance_locality", 5),
        quality_reason=justifications.get("quality_reason", ""),
        quality_and_depth=row.get("quality_and_depth", 5),
        trust_reason=justifications.get("trust_reason", ""),
        trust_and_sources=row.get("trust_and_sources", 5),
        domain_specific_reason=justifications.get("domain_specific_reason", ""),
        domain_specific_score=row.get("domain_specific_score", 5),
        strengths=strengths if isinstance(strengths, list) else [],
        weaknesses=weaknesses if isinstance(weaknesses, list) else [],
        ai_probability=row.get("ai_probability", 0),
        ai_reasoning=row.get("ai_reasoning", ""),
        spelling_errors=row.get("spelling_errors", []) if isinstance(row.get("spelling_errors"), list) else [],
        confidence=row.get("confidence", 70),
        final_overall_score=float(row.get("final_overall_score", 5.0)),
    )
