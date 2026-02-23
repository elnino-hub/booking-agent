#!/usr/bin/env python3
"""
Booking Agent Integration Test Suite
Tests every workflow path, verifies correct tool usage via n8n execution logs.

Prerequisites:
  - FastAPI server running (uvicorn execution.api:app)
  - ngrok tunnel active
  - n8n workflow (set N8N_WORKFLOW_ID in .env) is ACTIVE (not test mode)

Usage: python execution/test_agent.py
"""

import os
import sys
import time
import sqlite3
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load .env from project root (parent of execution/)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_ROOT, ".env"))

# ── Config ─────────────────────────────────────────────────────────────────────
N8N_BASE_URL  = os.getenv("N8N_BASE_URL", "https://your-n8n-instance.com")
N8N_API_KEY   = os.getenv("N8N_API_KEY")
WORKFLOW_ID   = os.getenv("N8N_WORKFLOW_ID")
DB_PATH       = os.path.join(_ROOT, os.getenv("DB_PATH", "history.db"))
# n8n chat trigger: public webhook requires the workflow to be activated
# AND the chatTrigger to have public:true set.
# If that fails (404), the test script falls back to reporting the error.
CHAT_URL      = f"{N8N_BASE_URL}/webhook/booking-agent-chat"
# n8n chat trigger also accepts the action:sendMessage format
CHAT_PAYLOAD_TEMPLATE = {"action": "sendMessage", "chatInput": "{message}", "sessionId": "{session_id}"}
API_HEADERS   = {"X-N8N-API-KEY": N8N_API_KEY}

TOOL_NODES = {"CheckAvailability", "BookAppointment", "CancelAppointment", "RescheduleAppointment"}

CONFIRMATION_PHRASES = [
    "confirm", "sure you want", "shall i", "do you want me to",
    "is that correct", "proceed", "go ahead", "want to cancel", "want me to cancel",
]

# ── Test Scenarios ─────────────────────────────────────────────────────────────
TEST_SCENARIOS = [
    # ── Phase 1: Read-only ─────────────────────────────────────────────────────
    {
        "id": 1, "name": "Availability check", "phase": "read-only",
        "input": "What's on my calendar this week?",
        "must_fire": ["CheckAvailability"],
        "must_not_fire": ["BookAppointment", "CancelAppointment", "RescheduleAppointment"],
    },
    {
        "id": 2, "name": "Free slot query", "phase": "read-only",
        "input": "Am I free this Friday afternoon?",
        "must_fire": ["CheckAvailability"],
        "must_not_fire": ["BookAppointment", "CancelAppointment", "RescheduleAppointment"],
    },
    {
        "id": 3, "name": "Next week view", "phase": "read-only",
        "input": "What do I have next week?",
        "must_fire": ["CheckAvailability"],
        "must_not_fire": [],
    },
    {
        "id": 4, "name": "Hallucination guard (repeat question)", "phase": "read-only",
        "input": "What meetings do I have?",
        "must_fire": ["CheckAvailability"],
        "must_not_fire": [],
        "hallucination_check": True,
    },
    # ── Phase 2: Write (modifies real calendar) ────────────────────────────────
    {
        "id": 5, "name": "Book appointment (clean slot)", "phase": "write",
        "input": "Book a meeting called [TEST] Integration Test on April 30 2026 at 3pm IST for 1 hour",
        "must_fire": ["CheckAvailability", "BookAppointment"],
        "must_not_fire": [],
    },
    {
        "id": 6, "name": "Conflict warning (should warn, NOT book)", "phase": "write",
        "input": "Book a meeting on April 30 2026 at 3pm IST for 1 hour",
        "must_fire": ["CheckAvailability"],
        "must_not_fire": ["BookAppointment"],
        "notes": "Expects agent to flag conflict with [TEST] Integration Test from test 5",
    },
    {
        "id": 7, "name": "Vague booking (should ask, NOT book)", "phase": "edge-case",
        "input": "Book something for me",
        "must_fire": [],
        "must_not_fire": ["BookAppointment", "CancelAppointment", "RescheduleAppointment"],
    },
    {
        "id": 8, "name": "Cancel by name (no event ID)", "phase": "write",
        "input": "Cancel my [TEST] Integration Test meeting",
        "must_fire": ["CheckAvailability"],
        "must_not_fire": [],
        "multi_turn": True,  # Agent may ask for confirmation first
        "multi_turn_must_fire": ["CancelAppointment"],
    },
    # ── Phase 3: Reschedule + cleanup ──────────────────────────────────────────
    {
        "id": 9, "name": "Book for reschedule test", "phase": "write",
        "input": "Book a meeting called [TEST] Reschedule Target on May 1 2026 at 3pm IST for 1 hour",
        "must_fire": ["CheckAvailability", "BookAppointment"],
        "must_not_fire": [],
    },
    {
        "id": 10, "name": "Reschedule by name", "phase": "write",
        "input": "Reschedule my [TEST] Reschedule Target meeting to 4pm on May 1 2026",
        "must_fire": ["CheckAvailability"],
        "must_not_fire": [],
        "multi_turn": True,
        "multi_turn_must_fire": ["RescheduleAppointment"],
    },
    {
        "id": 11, "name": "Cancel cleanup (Reschedule Target)", "phase": "write",
        "input": "Cancel my [TEST] Reschedule Target meeting",
        "must_fire": ["CheckAvailability"],
        "must_not_fire": [],
        "multi_turn": True,
        "multi_turn_must_fire": ["CancelAppointment"],
    },
]

# ── Helpers ────────────────────────────────────────────────────────────────────
def clear_history():
    """Delete all rows from messages table to prevent cross-test contamination."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM messages")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  [WARN] Could not clear history: {e}")


def send_chat(message):
    """POST a chat message to n8n. Returns agent text response."""
    resp = requests.post(
        CHAT_URL,
        json={"chatInput": message},
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        data = data[0] if data else {}
    return data.get("output") or str(data)


def get_latest_execution_nodes():
    """
    Fetch the most recent workflow execution.
    Returns (set_of_fired_node_names, exec_status, exec_id).
    """
    r = requests.get(
        f"{N8N_BASE_URL}/api/v1/executions",
        params={"workflowId": WORKFLOW_ID, "limit": 1},
        headers=API_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    execs = r.json().get("data", {}).get("executions", [])
    if not execs:
        return set(), "unknown", None

    exec_id = execs[0]["id"]
    r2 = requests.get(
        f"{N8N_BASE_URL}/api/v1/executions/{exec_id}",
        headers=API_HEADERS,
        timeout=15,
    )
    r2.raise_for_status()
    exec_data = r2.json()
    run_data = (
        exec_data.get("data", {})
        .get("resultData", {})
        .get("runData", {})
    )
    return set(run_data.keys()), exec_data.get("status", "unknown"), exec_id


def needs_confirmation(response_text):
    """Check if the agent is asking for confirmation before proceeding."""
    text = (response_text or "").lower()
    return any(p in text for p in CONFIRMATION_PHRASES)


def evaluate(scenario, all_fired_nodes, agent_response):
    """
    Returns (status, issues).
    all_fired_nodes: union of nodes fired across all turns.
    """
    issues = []
    for node in scenario.get("must_fire", []):
        if node not in all_fired_nodes:
            issues.append(f"MISSING: {node} should have fired but didn't")
    for node in scenario.get("must_not_fire", []):
        if node in all_fired_nodes:
            issues.append(f"UNEXPECTED: {node} fired but shouldn't have")
    for node in scenario.get("multi_turn_must_fire", []):
        if node not in all_fired_nodes:
            issues.append(f"MISSING (multi-turn): {node} should have fired but didn't")
    if scenario.get("hallucination_check"):
        evasion = ["don't have access", "cannot access", "no access", "i can't see", "unable to access"]
        if any(p in (agent_response or "").lower() for p in evasion):
            issues.append("HALLUCINATION: Agent evaded tool call with an excuse")
    return ("PASS", []) if not issues else ("FAIL", issues)


# ── Test Runner ────────────────────────────────────────────────────────────────
def run_scenario(scenario):
    """Run a single scenario (with optional multi-turn confirmation). Returns result dict."""
    print(f"\n[{scenario['id']:02d}] {scenario['name']}  [{scenario['phase']}]")
    if "notes" in scenario:
        print(f"  NOTE: {scenario['notes']}")
    print(f"  > {scenario['input']}")

    clear_history()
    time.sleep(1)

    all_fired = set()
    last_response = None
    last_exec_id = None

    # ── Turn 1 ──────────────────────────────────────────────────────────────
    try:
        last_response = send_chat(scenario["input"])
    except Exception as e:
        print(f"  ERROR sending chat: {e}")
        return {"scenario": scenario, "status": "ERROR", "issues": [str(e)], "fired": set()}

    preview = str(last_response)[:130].replace("\n", " ")
    print(f"  Response (T1): {preview}...")

    time.sleep(1)
    try:
        fired_t1, _, last_exec_id = get_latest_execution_nodes()
        all_fired |= fired_t1
    except Exception as e:
        print(f"  ERROR fetching execution: {e}")
        return {"scenario": scenario, "status": "ERROR", "issues": [f"execution fetch failed: {e}"], "fired": set()}

    # ── Turn 2 (if multi-turn and agent asked for confirmation) ─────────────
    if scenario.get("multi_turn") and needs_confirmation(last_response):
        print(f"  Agent asked for confirmation — sending follow-up...")
        time.sleep(1)
        try:
            last_response = send_chat("Yes, go ahead")
            preview2 = str(last_response)[:130].replace("\n", " ")
            print(f"  Response (T2): {preview2}...")
            time.sleep(1)
            fired_t2, _, last_exec_id = get_latest_execution_nodes()
            all_fired |= fired_t2
        except Exception as e:
            print(f"  ERROR in turn 2: {e}")

    fired_tools = all_fired & TOOL_NODES
    print(f"  Tools fired: {fired_tools or 'none'}")

    status, issues = evaluate(scenario, all_fired, last_response)
    for issue in issues:
        print(f"  ! {issue}")
    print(f"  {'PASS' if status == 'PASS' else 'FAIL'}")

    return {
        "scenario": scenario,
        "status": status,
        "issues": issues,
        "fired": fired_tools,
        "response": last_response,
        "exec_id": last_exec_id,
    }


def run_all():
    print("=" * 65)
    print("  BOOKING AGENT INTEGRATION TEST SUITE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Workflow: {WORKFLOW_ID}")
    print("=" * 65)

    results = []
    for scenario in TEST_SCENARIOS:
        result = run_scenario(scenario)
        results.append(result)
        time.sleep(2)  # Rate limiting between tests

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  SUMMARY")
    print("=" * 65)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    total  = len(results)
    print(f"  PASSED: {passed}/{total}  |  FAILED: {failed}  |  ERRORS: {errors}")
    print()

    for r in results:
        sid    = r["scenario"]["id"]
        name   = r["scenario"]["name"]
        status = r["status"]
        symbol = "OK" if status == "PASS" else ("ERR" if status == "ERROR" else "FAIL")
        fired  = ", ".join(sorted(r.get("fired", set()))) or "-"
        print(f"  [{sid:02d}] {symbol:<4}  {name}")
        print(f"        Tools: {fired}")
        for issue in r.get("issues", []):
            print(f"        -> {issue}")

    print("=" * 65)

    if failed or errors:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
