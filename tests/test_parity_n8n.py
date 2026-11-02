"""Proves the Python implementation behaves like the n8n workflow.

The REAL JavaScript from the workflow's 'Normalize & Validate' and 'Classify Lead' Code nodes
is executed with Node.js on every case in tests/parity/cases.json, and the Python functions
must produce the same answers. If someone edits one implementation and not the other, this
test fails.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.schemas import LeadIn
from app.services import classify_lead, normalize_lead

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tests" / "parity" / "n8n_runner.js"
CASES = ROOT / "tests" / "parity" / "cases.json"
WORKFLOW = ROOT / "n8n" / "real-estate-lead-response-agent.json"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is required to execute the n8n workflow code")

CASE_LIST = json.loads(CASES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def n8n_results():
    out = subprocess.run([NODE, str(RUNNER), str(WORKFLOW), str(CASES)], capture_output=True, text=True, check=True, timeout=60)
    results = json.loads(out.stdout)
    assert [r["name"] for r in results] == [c["name"] for c in CASE_LIST]
    return results


def python_side(payload: dict):
    data = LeadIn.model_validate({**payload, "secret": "x"}).model_dump(exclude={"secret"})
    normalized = normalize_lead(data)
    classification = None if normalized["rejected"] else classify_lead(normalized, normalized["flags"])
    return normalized, classification


@pytest.mark.parametrize("index", range(len(CASE_LIST)), ids=[c["name"] for c in CASE_LIST])
def test_python_matches_n8n(index, n8n_results):
    case, js = CASE_LIST[index], n8n_results[index]
    n, c = python_side(case["payload"])
    jn = js["normalize"]

    assert n["rejected"] == jn["isRejected"]
    assert n["reject_reason"] == jn["rejectReason"]
    assert n["full_name"] == jn["fullName"]
    assert n["email"] == jn["email"]
    assert n["phone"] == jn["phone"]
    assert n["budget_value"] == jn["budget"]
    assert n["flags"] == jn["flags"]

    if n["rejected"]:
        assert js["classify"] is None
        return
    jc = js["classify"]
    assert c.priority == jc["priority"]
    assert c.reasons == jc["reviewReasons"]
    assert c.timeline_days == jc["timelineDays"]
    assert c.action == jc["followUpAction"]


def test_workflow_file_is_the_one_in_the_repo_and_is_valid():
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    names = {n["name"] for n in workflow["nodes"]}
    assert {"Google Form Webhook", "Normalize & Validate", "Classify Lead", "Find Existing Lead",
            "Create New Lead", "Update Existing Lead", "Create Follow-up Task", "Email Sales Rep"} <= names
    # Every connection must point at a node that exists.
    for source, outputs in workflow["connections"].items():
        assert source in names
        for branch in outputs["main"]:
            for link in branch:
                assert link["node"] in names
