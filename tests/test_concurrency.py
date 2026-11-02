"""Simultaneous webhook calls must neither duplicate a lead nor skew round-robin assignment."""
from concurrent.futures import ThreadPoolExecutor

from app.database import connect
from app.services import normalize_lead, process_lead


def lead(i: int, email: str | None = None) -> dict:
    return normalize_lead({
        "full_name": f"Lead {i}", "email": email or f"lead{i}@example.com", "phone": f"030012345{i:02d}",
        "budget": "1 crore", "buying_timeline": "within 7 days",
    })


def run_parallel(leads, workers=8):
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(process_lead, leads))


def test_same_enquiry_submitted_at_once_creates_one_lead(client):
    # `client` fixture runs startup, which creates the tables.
    same = [normalize_lead({"full_name": "Twin", "email": "twin@example.com", "budget": "1 crore",
                            "buying_timeline": "7 days"}) for _ in range(12)]
    results = run_parallel(same)
    with connect() as db:
        assert db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 1
    assert sum(1 for _, duplicate, _ in results if not duplicate) == 1


def test_round_robin_stays_balanced_under_load(client):
    results = run_parallel([lead(i) for i in range(20)])
    owners = [row["assigned_to"] for row, _, _ in results]
    assert owners.count("Sales Representative 1") == 10 and owners.count("Sales Representative 2") == 10
