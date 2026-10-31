import json, re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from app.config import get_settings
from app.database import connect

ROOT = Path(__file__).resolve().parent.parent

def now_local():
    return datetime.now(ZoneInfo(get_settings().timezone))

def normalize_phone(value):
    if not value: return None
    cc = get_settings().default_country_code
    digits = re.sub(r"[^0-9+]", "", str(value))
    if digits.startswith("00"): digits = "+" + digits[2:]
    if not digits.startswith("+"):
        digits = cc + digits[1:] if digits.startswith("0") else ("+" + digits if digits.startswith(cc.lstrip("+")) else cc + digits)
    digits = "+" + re.sub(r"[^0-9]", "", digits)
    return digits if re.fullmatch(r"\+[1-9]\d{9,14}", digits) else None

def parse_budget(value):
    if value is None or value == "": return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*(crore|cr|lakh|lac|million|m|thousand|k)?", str(value).lower().replace(",", ""))
    if not match: return None
    mult = {"crore":10_000_000,"cr":10_000_000,"lakh":100_000,"lac":100_000,"million":1_000_000,"m":1_000_000,"thousand":1_000,"k":1_000}
    return round(float(match.group(1)) * mult.get(match.group(2),1))

def classify_lead(data):
    rules = json.loads((ROOT / "config/routing_rules.json").read_text())
    p = rules["priority_rules"]
    reasons, budget = [], parse_budget(data.get("budget"))
    if not data.get("budget"): reasons.append("Missing budget")
    elif budget is None: reasons.append("Budget could not be understood")
    timeline = (data.get("buying_timeline") or "").lower()
    days = None
    if any(x in timeline for x in ("undecided","not sure","browsing","just looking","flexible")): days = 999
    elif any(x in timeline for x in ("today","tomorrow","asap","urgent","immediate","this week")): days = 7
    else:
        m = re.search(r"(\d+)\s*(day|week|month|year)", timeline)
        if m: days = int(m.group(1)) * {"day":1,"week":7,"month":30,"year":365}[m.group(2)]
        else: reasons.append("Missing or unrecognized buying timeline")
    if reasons: priority, delta = "Needs review", timedelta(days=p["review_followup_days"])
    elif days <= p["urgent_max_days"]: priority, delta = "Urgent", timedelta(hours=p["urgent_followup_hours"])
    elif days <= p["high_max_days"]: priority, delta = "High priority", timedelta(hours=p["high_followup_hours"])
    else: priority, delta = "Nurture", timedelta(days=p["nurture_followup_days"])
    return priority, reasons, now_local() + delta

def assign_rep():
    rules = json.loads((ROOT / "config/routing_rules.json").read_text())
    reps = [r for r in rules["sales_reps"] if r.get("active")]
    if not reps: return rules.get("default_owner","Unassigned"), ""
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key='round_robin_index'").fetchone()
        index = int(row["value"]) if row else 0
        rep = reps[index % len(reps)]
        db.execute("UPDATE settings SET value=? WHERE key='round_robin_index'",(str(index+1),))
    return rep["name"], rep.get("email","")

def save_lead(data):
    now, phone = now_local().isoformat(), normalize_phone(data.get("phone"))
    email = str(data.get("email") or "").lower().strip() or None
    if not email and not phone: raise ValueError("A valid email address or phone number is required.")
    priority, reasons, due = classify_lead(data)
    with connect() as db:
        existing = db.execute("SELECT * FROM leads WHERE lower(email)=?",(email,)).fetchone() if email else None
        if not existing and phone: existing = db.execute("SELECT * FROM leads WHERE phone=?",(phone,)).fetchone()
        duplicate = existing is not None
        if duplicate:
            owner, owner_email, lead_id = existing["assigned_to"] or "Unassigned", existing["assigned_email"] or "", existing["id"]
            db.execute("""UPDATE leads SET full_name=?,email=COALESCE(?,email),phone=COALESCE(?,phone),
            property_type=?,budget_raw=?,preferred_location=?,buying_timeline=?,message=?,source=?,
            priority=?,follow_up_due=?,review_reasons=?,updated_at=?,raw_payload=? WHERE id=?""",
            (data["full_name"],email,phone,data.get("property_type"),str(data.get("budget") or ""),
             data.get("preferred_location"),data.get("buying_timeline"),data.get("message"),data.get("source","website"),
             priority,due.isoformat(),json.dumps(reasons),now,json.dumps(data),lead_id))
        else:
            owner, owner_email = assign_rep()
            cur = db.execute("""INSERT INTO leads(full_name,email,phone,property_type,budget_raw,preferred_location,
            buying_timeline,message,source,priority,assigned_to,assigned_email,follow_up_due,review_reasons,
            created_at,updated_at,raw_payload) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["full_name"],email,phone,data.get("property_type"),str(data.get("budget") or ""),
             data.get("preferred_location"),data.get("buying_timeline"),data.get("message"),data.get("source","website"),
             priority,owner,owner_email,due.isoformat(),json.dumps(reasons),now,now,json.dumps(data)))
            lead_id = cur.lastrowid
        db.execute("INSERT INTO follow_up_tasks(lead_id,title,due_at,created_at) VALUES(?,?,?,?)",
                   (lead_id,f"{priority}: follow up with {data['full_name']}",due.isoformat(),now))
        db.execute("INSERT INTO events(lead_id,event_type,detail,created_at) VALUES(?,?,?,?)",
                   (lead_id,"lead_processed",json.dumps({"duplicate":duplicate,"priority":priority,"warnings":reasons}),now))
        return dict(db.execute("SELECT * FROM leads WHERE id=?",(lead_id,)).fetchone()), duplicate
