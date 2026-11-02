from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services import classify_lead

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=ZoneInfo("Asia/Karachi"))


def lead(timeline="within 7 days", budget=10_000_000, message="", budget_raw="1 crore"):
    return {"buying_timeline": timeline, "budget_value": budget, "budget_raw": budget_raw, "message": message}


@pytest.mark.parametrize("timeline, priority", [
    ("within 7 days", "Urgent"),
    ("1 week", "Urgent"),
    ("ASAP", "Urgent"),
    ("tomorrow", "Urgent"),
    ("this week", "Urgent"),
    ("within 8 days", "High priority"),
    ("within 30 days", "High priority"),
    ("1 month", "High priority"),
    ("1-2 weeks", "High priority"),  # a range uses its upper bound: 14 days
    ("2-3 months", "Nurture"),
    ("in 3 months", "Nurture"),
    ("6+ months", "Nurture"),
    ("1 year", "Nurture"),
    ("undecided", "Nurture"),
    ("not sure yet", "Nurture"),
    ("exploring options", "Nurture"),
])
def test_priority_from_timeline(timeline, priority):
    assert classify_lead(lead(timeline), now=NOW).priority == priority


def test_urgent_follow_up_is_due_in_one_hour():
    c = classify_lead(lead("asap"), now=NOW)
    assert c.due_at == NOW + timedelta(hours=1) and "within 1 hour" in c.action


def test_other_follow_up_windows():
    assert classify_lead(lead("20 days"), now=NOW).due_at == NOW + timedelta(hours=24)
    assert classify_lead(lead("4 months"), now=NOW).due_at == NOW + timedelta(days=3)
    assert classify_lead(lead(""), now=NOW).due_at == NOW + timedelta(days=1)


@pytest.mark.parametrize("kwargs, reason", [
    ({"timeline": ""}, "Missing buying timeline"),
    ({"timeline": "whenever it suits"}, "Unrecognised buying timeline: whenever it suits"),
    ({"budget": None, "budget_raw": ""}, "Missing budget"),
    ({"budget": None, "budget_raw": "negotiable"}, "Unreadable budget: negotiable"),
])
def test_missing_or_unreadable_data_needs_review(kwargs, reason):
    c = classify_lead(lead(**kwargs), now=NOW)
    assert c.priority == "Needs review" and reason in c.reasons


def test_contradiction_long_timeline_but_urgent_message():
    c = classify_lead(lead("6 months", message="I need this urgent"), now=NOW)
    assert c.priority == "Needs review"
    assert 'Contradiction: timeline is "6 months" but the message sounds urgent' in c.reasons


def test_contradiction_undecided_but_urgent_message():
    assert classify_lead(lead("undecided", message="asap please"), now=NOW).priority == "Needs review"


def test_contradiction_urgent_timeline_but_just_browsing():
    c = classify_lead(lead("within 3 days", message="I'm just browsing"), now=NOW)
    assert c.priority == "Needs review"
    assert "Contradiction: urgent timeline but the message says just browsing" in c.reasons


def test_flags_from_normalisation_force_review():
    c = classify_lead(lead("within 7 days"), flags=["Missing phone"], now=NOW)
    assert c.priority == "Needs review" and c.reasons[0] == "Missing phone"
