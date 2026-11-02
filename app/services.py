"""Lead normalisation, qualification, routing and persistence.

normalize_lead() and classify_lead() are a line-for-line port of the "Normalize & Validate"
and "Classify Lead" Code nodes in n8n/real-estate-lead-response-agent.json. The test suite
runs both implementations on the same inputs (tests/test_parity_n8n.py) so they cannot
silently drift apart. See docs/PARITY.md for the intentional differences.
"""
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.database import connect

ROOT = Path(__file__).resolve().parent.parent
UNKNOWN_NAME = "Unknown lead"

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
BUDGET_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(crore|cr|lakh|lac|million|mil|m|thousand|k)?\b")
CURRENCY_RE = re.compile(r"(pkr|rs\.?|usd|aed|\$|£|€)")
BUDGET_MULTIPLIER = {
    "crore": 10_000_000, "cr": 10_000_000, "lakh": 100_000, "lac": 100_000,
    "million": 1_000_000, "mil": 1_000_000, "m": 1_000_000, "thousand": 1_000, "k": 1_000,
}
URGENT_WORDS = re.compile(r"(immediate|asap|right away|urgent|today|tomorrow|this week)")
UNDECIDED_WORDS = re.compile(
    r"(undecided|not sure|unsure|just looking|browsing|don't know|dont know|no idea|exploring|flexible)"
)
BROWSING_WORDS = re.compile(r"(just looking|only looking|browsing)")
TIMELINE_RE = re.compile(r"([0-9]+)(?:\s*-\s*([0-9]+))?\s*\+?\s*(day|week|month|year)")
UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}

DEFAULT_ACTIONS = {
    "Urgent": "Call the buyer within 1 hour, then confirm by email",
    "High priority": "Call within 24 hours and propose viewing slots",
    "Nurture": "Send property information within 3 days and add to the nurture list",
    "Needs review": "Verify the missing or conflicting details, then re-classify",
}

# Columns of the `leads` table that come from the enquiry itself.
LEAD_FIELDS = (
    "full_name", "email", "phone", "property_type", "budget_raw", "budget_value",
    "preferred_location", "buying_timeline", "message", "source",
)


# --------------------------------------------------------------------------- time


def now_local() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone))


def to_utc_text(value: datetime) -> str:
    """Fixed-width UTC timestamp; sorts correctly as text, so SQL comparisons are safe."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------------- rules


@lru_cache
def load_rules() -> dict:
    custom = get_settings().routing_rules_path
    path = Path(custom) if custom else ROOT / "config" / "routing_rules.json"
    rules = json.loads(path.read_text(encoding="utf-8"))
    for key in ("sales_reps", "priority_rules"):
        if key not in rules:
            raise RuntimeError(f"{path} is missing the required '{key}' section.")
    needed = {
        "urgent_max_days", "high_max_days", "urgent_followup_hours", "high_followup_hours",
        "nurture_followup_days", "review_followup_days",
    }
    missing = needed - set(rules["priority_rules"])
    if missing:
        raise RuntimeError(f"{path}: priority_rules is missing {sorted(missing)}.")
    return rules


# ------------------------------------------------------------------ normalisation


def normalize_phone(value, country_code: str | None = None) -> str | None:
    """Return an E.164 number (+923001234567) or None when it cannot be made valid."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    cc = country_code or get_settings().default_country_code or "+92"
    cc_digits = cc.replace("+", "")
    s = re.sub(r"[^0-9+]", "", raw)
    if s.startswith("00"):
        s = "+" + s[2:]
    if not s.startswith("+"):
        if s.startswith("0"):
            s = cc + s[1:]
        elif s.startswith(cc_digits) and len(s) >= len(cc_digits) + 9:
            s = "+" + s
        else:
            s = cc + s
    s = "+" + s.replace("+", "")
    return s if re.fullmatch(r"\+[1-9][0-9]{9,14}", s) else None


def parse_budget(value) -> int | None:
    """Understand '1.5 crore', '50 lakh', 'PKR 750k', '$1.2m', '2 million' -> integer."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    text = CURRENCY_RE.sub("", raw.lower().replace(",", "")).strip()
    match = BUDGET_RE.search(text)
    if not match:
        return None
    amount = float(match.group(1)) * (BUDGET_MULTIPLIER[match.group(2)] if match.group(2) else 1)
    return math.floor(amount + 0.5) if amount > 0 else None  # round half up, like JS Math.round


def normalize_lead(data: dict) -> dict:
    """Clean one enquiry. Mirrors the n8n 'Normalize & Validate' node.

    A lead is rejected only when it has neither a valid email nor a valid phone number.
    Everything else that is missing or malformed becomes a flag that routes the lead to
    'Needs review' instead of losing it.
    """
    def pick(key: str) -> str:
        value = data.get(key)
        return str(value).strip() if value is not None and str(value).strip() else ""

    full_name = re.sub(r"\s+", " ", pick("full_name"))
    raw_email = pick("email").lower()
    raw_phone = pick("phone")
    email_valid = bool(EMAIL_RE.match(raw_email))
    phone = normalize_phone(raw_phone)
    budget_raw = pick("budget")

    flags: list[str] = []
    if not full_name:
        flags.append("Missing name")
    if not raw_email:
        flags.append("Missing email")
    elif not email_valid:
        flags.append("Invalid email format")
    if not raw_phone:
        flags.append("Missing phone")
    elif not phone:
        flags.append("Invalid phone number")

    rejected = not email_valid and not phone
    raw_payload = {k: v for k, v in data.items() if k != "secret"}
    return {
        "full_name": full_name or UNKNOWN_NAME,
        "email": raw_email if email_valid else "",
        "phone": phone or "",
        "raw_email": raw_email,
        "raw_phone": raw_phone,
        "property_type": pick("property_type"),
        "budget_raw": budget_raw,
        "budget_value": parse_budget(budget_raw),
        "preferred_location": pick("preferred_location"),
        "buying_timeline": pick("buying_timeline"),
        "message": pick("message"),
        "source": pick("source") or "website",
        "submitted_at": pick("submitted_at"),
        "flags": flags,
        "rejected": rejected,
        "reject_reason": "No valid email or phone number" if rejected else "",
        "raw": raw_payload,
    }


# ----------------------------------------------------------------- classification


@dataclass
class Classification:
    priority: str
    reasons: list[str]
    timeline_days: int | None
    undecided: bool
    action: str
    due_at: datetime


def classify_lead(lead: dict, flags=(), now: datetime | None = None) -> Classification:
    """Priority rules (no AI). Mirrors the n8n 'Classify Lead' node.

    Urgent <= urgent_max_days, High priority <= high_max_days, Nurture beyond that or
    undecided, and Needs review whenever anything is missing, unreadable or contradictory.
    """
    rules = load_rules()
    pr = rules["priority_rules"]
    reasons = list(flags)
    timeline_text = lead.get("buying_timeline") or ""
    timeline = timeline_text.lower()
    message = (lead.get("message") or "").lower()

    days: int | None = None
    undecided = False
    if not timeline:
        reasons.append("Missing buying timeline")
    elif UNDECIDED_WORDS.search(timeline):
        undecided = True
    elif URGENT_WORDS.search(timeline):
        days = pr["urgent_max_days"]
    else:
        m = TIMELINE_RE.search(timeline)
        if m:
            days = int(m.group(2) or m.group(1)) * UNIT_DAYS[m.group(3)]  # ranges use the upper bound
        else:
            reasons.append("Unrecognised buying timeline: " + timeline_text)

    if not lead.get("budget_value"):
        budget_raw = lead.get("budget_raw")
        reasons.append("Unreadable budget: " + budget_raw if budget_raw else "Missing budget")
    if (undecided or (days is not None and days > pr["high_max_days"])) and URGENT_WORDS.search(message):
        reasons.append(f'Contradiction: timeline is "{timeline_text}" but the message sounds urgent')
    if days is not None and days <= pr["urgent_max_days"] and BROWSING_WORDS.search(message):
        reasons.append("Contradiction: urgent timeline but the message says just browsing")

    now = now or now_local()
    if reasons:
        priority, delta = "Needs review", timedelta(days=pr["review_followup_days"])
    elif undecided:
        priority, delta = "Nurture", timedelta(days=pr["nurture_followup_days"])
    elif days <= pr["urgent_max_days"]:
        priority, delta = "Urgent", timedelta(hours=pr["urgent_followup_hours"])
    elif days <= pr["high_max_days"]:
        priority, delta = "High priority", timedelta(hours=pr["high_followup_hours"])
    else:
        priority, delta = "Nurture", timedelta(days=pr["nurture_followup_days"])

    actions = {**DEFAULT_ACTIONS, **rules.get("follow_up_actions", {})}
    return Classification(priority, reasons, days, undecided, actions[priority], now + delta)


# ---------------------------------------------------------------------- routing


def _assign_rep(db) -> tuple[str, str]:
    """Round-robin over active reps. Caller holds a write transaction, so this is race-free."""
    rules = load_rules()
    reps = [r for r in rules["sales_reps"] if r.get("active", True)]
    if not reps:
        return rules.get("default_owner", "Unassigned"), ""
    row = db.execute("SELECT value FROM settings WHERE key='round_robin_index'").fetchone()
    index = int(row["value"]) if row else 0
    rep = reps[index % len(reps)]
    db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('round_robin_index',?)", (str(index + 1),))
    return rep["name"], rep.get("email", "")


def rep_monday_user_id(rep_name: str | None) -> str:
    for rep in load_rules()["sales_reps"]:
        if rep["name"] == rep_name:
            return str(rep.get("monday_user_id") or "")
    return ""


# ------------------------------------------------------------------ persistence


def _find_existing(db, email: str, phone: str):
    if email:
        row = db.execute("SELECT * FROM leads WHERE email=? ORDER BY id LIMIT 1", (email,)).fetchone()
        if row:
            return row
    if phone:
        return db.execute("SELECT * FROM leads WHERE phone=? ORDER BY id LIMIT 1", (phone,)).fetchone()
    return None


def _merge(new: dict, old) -> dict:
    """A repeat enquiry only overwrites a field when it actually supplies a value."""
    merged = {f: new.get(f) for f in LEAD_FIELDS}
    if old is None:
        return merged
    for f in LEAD_FIELDS:
        if f in ("budget_raw", "budget_value"):
            continue
        empty = merged[f] in (None, "") or (f == "full_name" and merged[f] == UNKNOWN_NAME)
        if empty and old[f] not in (None, ""):
            merged[f] = old[f]
    # Budget text and number travel together; keep the old pair if the new one is unreadable.
    if merged["budget_value"] is None and old["budget_value"]:
        merged["budget_raw"], merged["budget_value"] = old["budget_raw"], old["budget_value"]
    return merged


def _resolved_flags(flags: list[str], merged: dict) -> list[str]:
    """Drop 'Missing ...' flags that the stored record already answers."""
    resolved = {
        "Missing name": merged["full_name"] not in (None, "", UNKNOWN_NAME),
        "Missing email": bool(merged["email"]),
        "Missing phone": bool(merged["phone"]),
    }
    return [f for f in flags if not resolved.get(f, False)]


def process_lead(normalized: dict, now: datetime | None = None) -> tuple[dict, bool, Classification]:
    """Dedupe, classify, assign, and store one validated lead. Returns (lead_row, is_duplicate, classification)."""
    now = now or now_local()
    stamp = now.isoformat()
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")  # serialise writers: no duplicate rows, no repeated round-robin slot
        existing = _find_existing(db, normalized["email"], normalized["phone"])
        merged = _merge(normalized, existing)
        cls = classify_lead(merged, _resolved_flags(normalized["flags"], merged), now)
        due_local = cls.due_at.isoformat()
        values = [merged[f] if merged[f] != "" else None for f in LEAD_FIELDS]
        raw = json.dumps(normalized["raw"], default=str)
        reasons = json.dumps(cls.reasons)

        if existing is not None:
            lead_id = existing["id"]
            sets = ", ".join(f"{f}=?" for f in LEAD_FIELDS)
            db.execute(
                f"""UPDATE leads SET {sets}, priority=?, follow_up_due=?, follow_up_action=?, review_reasons=?,
                    crm_sync_status='pending', crm_error=NULL, crm_note_id=NULL, crm_task_id=NULL,
                    updated_at=?, raw_payload=? WHERE id=?""",
                (*values, cls.priority, due_local, cls.action, reasons, stamp, raw, lead_id),
            )
        else:
            owner, owner_email = _assign_rep(db)
            cols = ", ".join(LEAD_FIELDS)
            marks = ", ".join("?" for _ in LEAD_FIELDS)
            cur = db.execute(
                f"""INSERT INTO leads({cols}, priority, assigned_to, assigned_email, follow_up_due,
                    follow_up_action, review_reasons, crm_sync_status, created_at, updated_at, raw_payload)
                    VALUES({marks}, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
                (*values, cls.priority, owner, owner_email, due_local, cls.action, reasons, stamp, stamp, raw),
            )
            lead_id = cur.lastrowid

        db.execute(
            "INSERT INTO follow_up_tasks(lead_id,title,due_at,created_at) VALUES(?,?,?,?)",
            (lead_id, f"{cls.priority}: follow up with {merged['full_name']}", to_utc_text(cls.due_at), stamp),
        )
        db.execute(
            "INSERT INTO events(lead_id,event_type,detail,created_at) VALUES(?,?,?,?)",
            (lead_id, "lead_processed",
             json.dumps({"duplicate": existing is not None, "priority": cls.priority, "warnings": cls.reasons}), stamp),
        )
        lead = dict(db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone())
    return lead, existing is not None, cls


def get_lead(lead_id: int) -> dict | None:
    with connect() as db:
        row = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    return dict(row) if row else None


_UPDATABLE = {"crm_item_id", "crm_sync_status", "crm_error", "crm_note_id", "crm_task_id"}


def update_lead(lead_id: int, **fields) -> None:
    unknown = set(fields) - _UPDATABLE
    if unknown:
        raise ValueError(f"Cannot update columns: {sorted(unknown)}")
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    with connect() as db:
        db.execute(f"UPDATE leads SET {sets} WHERE id=?", (*fields.values(), lead_id))


def log_event(lead_id: int | None, event_type: str, detail: dict) -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO events(lead_id,event_type,detail,created_at) VALUES(?,?,?,?)",
            (lead_id, event_type, json.dumps(detail, default=str), now_local().isoformat()),
        )
