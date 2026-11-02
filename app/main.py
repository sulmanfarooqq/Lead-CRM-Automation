import json
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.background import BackgroundTask

from app import __version__, monday
from app.config import get_settings, startup_problems
from app.database import connect, init_db
from app.pipeline import report_rejected, run_integrations
from app.schemas import LeadIn, LeadResult
from app.security import require_api_key, verify_webhook_secret
from app.services import get_lead, load_rules, normalize_lead, now_local, process_lead, to_utc_text
from app.notifications import PLACEHOLDER_DOMAINS

log = logging.getLogger("lead_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    errors, warnings = startup_problems(settings)
    for line in warnings:
        log.warning(line)
    if errors:
        for line in errors:
            log.error(line)
        raise RuntimeError("Refusing to start: " + " ".join(errors))
    for rep in load_rules()["sales_reps"]:
        if rep.get("active", True) and rep.get("email", "").lower().endswith(PLACEHOLDER_DOMAINS):
            log.warning("Sales rep '%s' still uses a sample email address; edit config/routing_rules.json.", rep["name"])
    init_db()
    yield


app = FastAPI(
    title="Techtox Lead Response Agent",
    version=__version__,
    description=(
        "Self-hosted real estate lead capture, qualification, routing and CRM synchronisation API. "
        "Python/FastAPI equivalent of the bundled n8n workflow."
    ),
    lifespan=lifespan,
)


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > get_settings().max_request_bytes:
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})
    return await call_next(request)


@app.get("/", tags=["service"])
def root():
    return {
        "name": get_settings().app_name, "version": __version__, "status": "running",
        "docs": "/docs", "health": "/health", "webhook": "/webhooks/leads",
    }


@app.get("/health", tags=["service"])
def health():
    try:
        with connect() as db:
            db.execute("SELECT 1")
    except Exception:
        log.exception("Health check: database unavailable")
        return JSONResponse(status_code=503, content={"status": "error", "detail": "database unavailable"})
    return {"status": "ok"}


@app.post("/webhooks/leads", response_model=LeadResult, tags=["webhook"])
def receive_lead(
    payload: LeadIn,
    background: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None),
):
    """Receive one enquiry. The secret may be sent as the X-Webhook-Secret header or as `secret` in the JSON body."""
    verify_webhook_secret(x_webhook_secret or payload.secret)

    normalized = normalize_lead(payload.model_dump(exclude={"secret"}))
    if normalized["rejected"]:
        return JSONResponse(
            status_code=422,
            content={"detail": normalized["reject_reason"] + ": provide a valid email address or phone number.",
                     "flags": normalized["flags"]},
            background=BackgroundTask(report_rejected, normalized),
        )

    lead, duplicate, cls = process_lead(normalized)
    background.add_task(run_integrations, lead["id"], duplicate)

    return LeadResult(
        lead_id=lead["id"],
        status="updated" if duplicate else "created",
        priority=cls.priority,
        assigned_to=lead.get("assigned_to") or "Unassigned",
        follow_up_due=lead["follow_up_due"],
        follow_up_action=cls.action,
        is_duplicate=duplicate,
        crm_status="queued" if monday.configured() else "not_configured",
        message="Lead stored. Team notifications are being sent; the buyer was not contacted.",
        warnings=cls.reasons,
    )


# ----------------------------------------------------------------- management API

api = APIRouter(prefix="/api", tags=["management"], dependencies=[Depends(require_api_key)])


def _public(row, include_raw: bool = False) -> dict:
    data = dict(row)
    data["review_reasons"] = json.loads(data.get("review_reasons") or "[]")
    if include_raw:
        data["raw_payload"] = json.loads(data.get("raw_payload") or "{}")
    else:
        data.pop("raw_payload", None)
    return data


@api.get("/leads")
def list_leads(
    limit: int = Query(default=50, ge=1, le=200),
    priority: str | None = Query(default=None),
    crm_status: str | None = Query(default=None, description="pending, synced, failed or not_configured"),
):
    where, args = [], []
    if priority:
        where.append("priority=?")
        args.append(priority)
    if crm_status:
        where.append("crm_sync_status=?")
        args.append(crm_status)
    sql = "SELECT * FROM leads" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY created_at DESC, id DESC LIMIT ?"
    with connect() as db:
        rows = db.execute(sql, (*args, limit)).fetchall()
    return [_public(r) for r in rows]


@api.get("/leads/{lead_id}")
def get_one_lead(lead_id: int):
    lead = get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _public(lead, include_raw=True)


@api.post("/leads/{lead_id}/resync")
def resync_lead(lead_id: int, background: BackgroundTasks):
    """Retry the monday.com sync for a lead (for example after a CRM outage). Safe to repeat: no duplicate item is created."""
    if not get_lead(lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    background.add_task(run_integrations, lead_id, False, False)
    return {"lead_id": lead_id, "status": "resync queued"}


@api.get("/follow-ups/due")
def due_followups():
    with connect() as db:
        rows = db.execute(
            """SELECT t.id, t.lead_id, t.title, t.due_at, t.status, l.full_name, l.email, l.phone,
                      l.priority, l.assigned_to, l.follow_up_action
               FROM follow_up_tasks t JOIN leads l ON l.id=t.lead_id
               WHERE t.status='Open' AND t.due_at<=? ORDER BY t.due_at""",
            (to_utc_text(now_local()),),
        ).fetchall()
    return [dict(r) for r in rows]


@api.post("/follow-ups/{task_id}/complete")
def complete_followup(task_id: int):
    with connect() as db:
        row = db.execute("SELECT status FROM follow_up_tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Follow-up task not found")
        if row["status"] != "Open":
            raise HTTPException(status_code=409, detail=f"Task is already {row['status']}")
        db.execute(
            "UPDATE follow_up_tasks SET status='Done', completed_at=? WHERE id=?",
            (now_local().isoformat(), task_id),
        )
    return {"id": task_id, "status": "Done"}


@api.get("/stats")
def stats():
    with connect() as db:
        total = db.execute("SELECT COUNT(*) n FROM leads").fetchone()["n"]
        by_priority = db.execute("SELECT priority, COUNT(*) c FROM leads GROUP BY priority").fetchall()
        by_crm = db.execute("SELECT crm_sync_status s, COUNT(*) c FROM leads GROUP BY crm_sync_status").fetchall()
        open_tasks = db.execute("SELECT COUNT(*) n FROM follow_up_tasks WHERE status='Open'").fetchone()["n"]
    return {
        "total_leads": total,
        "by_priority": {r["priority"]: r["c"] for r in by_priority},
        "by_crm_status": {r["s"]: r["c"] for r in by_crm},
        "open_followups": open_tasks,
    }


app.include_router(api)
