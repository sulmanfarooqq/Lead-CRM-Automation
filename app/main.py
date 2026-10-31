import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Query
from app.config import get_settings
from app.database import init_db, connect
from app.schemas import LeadIn, LeadResult
from app.services import save_lead, now_local
from app.integrations import monday_sync, notify_team

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app=FastAPI(title="Techtox Lead Response Agent",version="1.0.0",
 description="Self-hosted lead capture, qualification, routing and CRM synchronization API.",lifespan=lifespan)

@app.get("/")
def root():
    return {"name":get_settings().app_name,"status":"running","docs":"/docs","health":"/health","webhook":"/webhooks/leads"}

@app.get("/health")
def health():
    return {"status":"ok"}

@app.post("/webhooks/leads",response_model=LeadResult)
def receive_lead(payload:LeadIn,x_webhook_secret:str|None=Header(default=None)):
    settings=get_settings()
    if (x_webhook_secret or payload.secret) != settings.webhook_secret:
        raise HTTPException(status_code=401,detail="Invalid webhook secret")
    data=payload.model_dump(exclude={"secret"},mode="json")
    if not data.get("email") and not data.get("phone"):
        raise HTTPException(status_code=422,detail="Provide at least one valid email or phone number")
    try: lead,duplicate=save_lead(data)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc))
    synced,crm_ref=monday_sync(lead)
    if synced and crm_ref:
        with connect() as db: db.execute("UPDATE leads SET crm_item_id=? WHERE id=?",(crm_ref,lead["id"]))
    notifications=notify_team(lead,duplicate)
    warnings=json.loads(lead["review_reasons"])
    if not synced: warnings.append(f"CRM sync: {crm_ref}")
    if not (notifications["email_sent"] or notifications["slack_sent"]):
        warnings.append("No team notification delivered; configure SMTP or Slack.")
    return LeadResult(lead_id=lead["id"],status="updated" if duplicate else "created",
      priority=lead["priority"],assigned_to=lead.get("assigned_to") or "Unassigned",
      follow_up_due=lead["follow_up_due"],is_duplicate=duplicate,
      message="Lead processed. Team notifications attempted; buyer was not contacted.",
      crm_synced=synced,warnings=warnings)

@app.get("/api/leads")
def list_leads(limit:int=Query(default=50,ge=1,le=200)):
    with connect() as db: rows=db.execute("SELECT * FROM leads ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
    return [dict(r) for r in rows]

@app.get("/api/leads/{lead_id}")
def get_lead(lead_id:int):
    with connect() as db: row=db.execute("SELECT * FROM leads WHERE id=?",(lead_id,)).fetchone()
    if not row: raise HTTPException(status_code=404,detail="Lead not found")
    return dict(row)

@app.get("/api/follow-ups/due")
def due_followups():
    with connect() as db:
        rows=db.execute("""SELECT t.*,l.full_name,l.email,l.phone,l.priority,l.assigned_to
          FROM follow_up_tasks t JOIN leads l ON l.id=t.lead_id
          WHERE t.status='Open' AND t.due_at<=? ORDER BY t.due_at""",
          (now_local().isoformat(),)).fetchall()
    return [dict(r) for r in rows]

@app.get("/api/stats")
def stats():
    with connect() as db:
        total=db.execute("SELECT COUNT(*) n FROM leads").fetchone()["n"]
        rows=db.execute("SELECT priority,COUNT(*) count FROM leads GROUP BY priority").fetchall()
        tasks=db.execute("SELECT COUNT(*) n FROM follow_up_tasks WHERE status='Open'").fetchone()["n"]
    return {"total_leads":total,"by_priority":{r["priority"]:r["count"] for r in rows},"open_followups":tasks}
