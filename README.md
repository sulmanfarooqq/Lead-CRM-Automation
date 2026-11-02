# Real Estate Lead Response Agent — Lead & CRM Automation (Python/FastAPI + n8n + monday.com)

[![CI](https://github.com/sulmanfarooqq/Lead-CRM-Automation/actions/workflows/ci.yml/badge.svg)](https://github.com/sulmanfarooqq/Lead-CRM-Automation/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)

**Real estate lead automation that captures every website or Google Form enquiry, validates and qualifies it, removes duplicates, routes it to a sales rep, creates the follow-up task in monday.com, and emails the team, with no buyer ever contacted automatically.**

This repository ships the **same system in two forms** so you can pick the one that fits the client:

| | Python / FastAPI service | n8n workflow |
|---|---|---|
| Where | [`app/`](app) | [`n8n/real-estate-lead-response-agent.json`](n8n/real-estate-lead-response-agent.json) |
| Best for | Self-hosting, custom code, an API with its own database and tests | No-code teams already running n8n |
| Lead intake | `POST /webhooks/leads` | n8n webhook `real-estate-lead` |
| CRM | monday.com (find → create/update → note → task) | same |
| Team alerts | SMTP email, Slack | Gmail |
| Extras | SQLite history, round-robin reps, REST API, resync | simple visual flow |

The qualification and validation logic is **proven identical**: the test suite runs the real JavaScript from the n8n workflow's Code nodes and checks that the Python code gives the same answer on 44 test enquiries. See [docs/PARITY.md](docs/PARITY.md) for the exact comparison and the few intentional differences.

> **Safety by design:** the system only messages your **team**. It never emails, texts or calls a buyer.

## Contents

- [How it works](#how-it-works)
- [Features](#features)
- [Quick start (Python)](#quick-start-python)
- [Send a test lead](#send-a-test-lead)
- [Priority rules](#priority-rules)
- [Connect Google Forms](#connect-google-forms)
- [Connect monday.com](#connect-mondaycom)
- [Email and Slack notifications](#email-and-slack-notifications)
- [API reference](#api-reference)
- [Configuration](#configuration)
- [Deploy](#deploy)
- [Use the n8n workflow instead](#use-the-n8n-workflow-instead)
- [Tests](#tests)
- [Project layout](#project-layout)
- [Limitations](#limitations)
- [Documentation](#documentation)

## How it works

```text
Google Form ──► Apps Script ──► POST /webhooks/leads        (or the n8n webhook)
Website form ─────────────────►        │
                                       ▼
                       check webhook secret ──✗──► 401, nothing stored
                                       │
                       validate + normalise (name, email, E.164 phone, budget)
                                       │
              no valid email AND no valid phone? ──► reject, alert admin
                                       │
                 duplicate? (email, then phone) ──► update existing lead
                                       │
                 classify: Urgent / High priority / Nurture / Needs review
                                       │
                 assign sales rep (round-robin) and save lead + follow-up task
                                       │  (answers the caller here)
                       ┌───────────────┴────────────────┐
                       ▼                                ▼
        monday.com: find → create/update      email / Slack the sales rep
        → activity note → follow-up task      (never the buyer)
                       │
        any failure ──► admin alert with manual steps; POST /api/leads/{id}/resync retries safely
```

## Features

- **Lead capture webhook** with constant-time shared-secret authentication (header or JSON body).
- **Validation that keeps leads:** a lead is rejected only when it has *no* valid email *and* no valid phone. Any other gap becomes a flag and the lead goes to **Needs review**.
- **Phone normalisation to E.164** (`0300 1234567`, `+92 300…`, `0092…`, `92300…` all become `+923001234567`; default country code configurable).
- **Budget parser** for `750k`, `50 lakh`, `1.5 crore`, `2 million`, `$1.2m`, `1,50,00,000`.
- **Priority classification** (Urgent, High priority, Nurture, Needs review) including contradiction detection, for example a "6 months" timeline with an "urgent" message.
- **Duplicate detection** by email, then phone, locally **and** in monday.com. A repeat enquiry updates the existing lead, keeps its owner and stage, and never erases details it did not repeat.
- **Round-robin routing** across active sales reps, safe under concurrent requests.
- **monday.com sync** with 3 retries, an activity note, and a follow-up task on a tasks board. Retries never create a second item.
- **Failure handling:** every CRM or notification failure is recorded on the lead and emailed to the admin with manual steps; `POST /api/leads/{id}/resync` retries.
- **Protected management API** (`X-API-Key`) for leads, due follow-ups, completing tasks, and statistics.
- **Production safeguards:** the app refuses to start in production with a missing or weak secret, caps request size, escapes all HTML in emails and CRM notes, and never logs tokens.
- **Docker, Render and Railway** ready, with GitHub Actions CI.

## Quick start (Python)

Requires Python 3.11+.

```bash
git clone https://github.com/sulmanfarooqq/Lead-CRM-Automation.git
cd Lead-CRM-Automation
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                 # Windows PowerShell: Copy-Item .env.example .env
```

Generate two secrets and put them in `.env` as `WEBHOOK_SECRET` and `API_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Replace the sample sales reps in [`config/routing_rules.json`](config/routing_rules.json) with your real team, then start the server:

```bash
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/docs> for the interactive API documentation. The app works with no CRM and no email configured, so you can try it immediately; leads are still stored and visible through the API.

## Send a test lead

```bash
curl -X POST http://127.0.0.1:8000/webhooks/leads \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: YOUR_WEBHOOK_SECRET" \
  -d @examples/sample_lead.json
```

```json
{
  "lead_id": 1,
  "status": "created",
  "priority": "Urgent",
  "assigned_to": "Sales Representative 1",
  "follow_up_due": "2026-11-02T17:43:36+05:00",
  "follow_up_action": "Call the buyer within 1 hour, then confirm by email",
  "is_duplicate": false,
  "crm_status": "not_configured",
  "message": "Lead stored. Team notifications are being sent; the buyer was not contacted.",
  "warnings": []
}
```

Send the same command again and you get `"status": "updated"` and `"is_duplicate": true`. Try [`examples/sample_lead_needs_review.json`](examples/sample_lead_needs_review.json) to see flags and **Needs review** in action, and [`examples/sample_lead_google_form.json`](examples/sample_lead_google_form.json) for the field names the Google Form bridge sends. View stored leads:

```bash
curl http://127.0.0.1:8000/api/leads -H "X-API-Key: YOUR_API_KEY"
```

## Priority rules

No AI is involved, so results are predictable and auditable. Thresholds and follow-up times live in [`config/routing_rules.json`](config/routing_rules.json).

| Priority | When | Follow-up action | Due |
|---|---|---|---|
| **Urgent** | Timeline ≤ 7 days, or *asap / today / tomorrow / this week* | Call the buyer within 1 hour, then confirm by email | 1 hour |
| **High priority** | 8–30 days | Call within 24 hours and propose viewing slots | 24 hours |
| **Nurture** | More than 30 days, or *undecided / just looking / exploring* | Send property information within 3 days | 3 days |
| **Needs review** | Anything missing, unreadable or contradictory | Verify the details, then re-classify | 1 day |

A timeline range such as `1-2 weeks` uses its upper bound. **Needs review** triggers on: missing name, email, phone, budget or timeline; an invalid email or phone; an unreadable budget or timeline; a long or undecided timeline with an urgent-sounding message; an urgent timeline with a "just browsing" message.

## Connect Google Forms

[`integrations/google-apps-script/Code.gs`](integrations/google-apps-script/Code.gs) sends each form response to the webhook, and works with both the Python service and the n8n workflow. The secret is kept in Apps Script *Script Properties*, never in the code. Step-by-step instructions: [docs/GOOGLE_FORM_SETUP.md](docs/GOOGLE_FORM_SETUP.md).

## Connect monday.com

1. Create a **Leads** board with columns Email, Phone, Property Type, Budget (**Numbers**), Preferred Location, Buying Timeline, Message (Long text), Stage (Status), Priority (Status), Follow-up Due (Date).
2. Optionally create a **Follow-up Tasks** board with a Date column and a Text column.
3. Put your API token, board ID and the *column IDs* in `.env`.

Full walkthrough, including how to find column IDs: [docs/MONDAY_SETUP.md](docs/MONDAY_SETUP.md). Leave `MONDAY_API_TOKEN` empty to run without a CRM.

## Email and Slack notifications

Set `SMTP_*` (plus `SALES_REP_EMAIL` and `ADMIN_EMAIL`) for email and `SLACK_WEBHOOK_URL` for Slack. Each new or repeat lead emails the assigned rep an HTML summary with a link to the lead in monday.com. Rejected enquiries and failures go to `ADMIN_EMAIL`. Port `587` uses STARTTLS and `465` uses implicit SSL. With nothing configured the app still works and logs a warning.

## API reference

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/` | none | Service information |
| `GET` | `/health` | none | Health check (verifies the database; `503` when it is down) |
| `POST` | `/webhooks/leads` | `X-Webhook-Secret` | Capture and process a lead |
| `GET` | `/api/leads` | `X-API-Key` | List leads. Filters: `limit`, `priority`, `crm_status` |
| `GET` | `/api/leads/{id}` | `X-API-Key` | One lead with its original payload |
| `POST` | `/api/leads/{id}/resync` | `X-API-Key` | Retry the monday.com sync safely |
| `GET` | `/api/follow-ups/due` | `X-API-Key` | Open follow-up tasks that are due |
| `POST` | `/api/follow-ups/{id}/complete` | `X-API-Key` | Mark a task done |
| `GET` | `/api/stats` | `X-API-Key` | Counts by priority and CRM status |

Webhook responses: `200` stored, `401` wrong secret, `413` body too large, `422` no valid email or phone (or invalid field types).

## Configuration

Every setting is an environment variable; [`.env.example`](.env.example) documents them all. The important ones:

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | Set to `production` to enforce strong secrets at startup |
| `WEBHOOK_SECRET`, `API_KEY` | Authentication (16+ random characters in production) |
| `DATABASE_URL` | SQLite path, for example `sqlite:///./data/leads.db` |
| `DEFAULT_COUNTRY_CODE`, `TIMEZONE` | Phone normalisation and due-time calculation |
| `MONDAY_*` | CRM connection and column IDs |
| `SMTP_*`, `SALES_REP_EMAIL`, `ADMIN_EMAIL`, `SLACK_WEBHOOK_URL` | Notifications |

## Deploy

**Render:** create a Blueprint from this repo. [`render.yaml`](render.yaml) sets production mode, generates both secrets and mounts a disk for SQLite (disks need a paid plan). **Railway:** deploy from GitHub, attach a volume, set `DATABASE_URL=sqlite:////app/data/leads.db`. **Docker:**

```bash
docker build -t lead-response-agent .
docker run --env-file .env -p 8000:8000 -v lead-data:/app/data lead-response-agent
```

Details, backups and scaling notes: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Run **one** instance; SQLite is not meant for several replicas.

## Use the n8n workflow instead

Import [`n8n/real-estate-lead-response-agent.json`](n8n/real-estate-lead-response-agent.json) into n8n, add a Header Auth credential for monday.com and a Gmail OAuth2 credential, fill in the **Config** node, and activate. Setup and node-by-node description: [docs/N8N_WORKFLOW.md](docs/N8N_WORKFLOW.md).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
node tests/parity/apps_script_check.js      # Google Apps Script bridge
```

The parity tests need Node.js 18+; they are skipped automatically when Node is absent. The monday.com tests run against an in-memory fake, so the suite needs no network and no credentials.

## Project layout

```text
app/                         FastAPI service
  main.py                    routes and startup checks
  services.py                normalise, classify, route, store (port of the n8n Code nodes)
  monday.py                  monday.com GraphQL client with retries
  notifications.py           email, Slack and admin alerts
  pipeline.py                background CRM sync + notifications, failure handling
  security.py  config.py  database.py  schemas.py
config/routing_rules.json    sales reps, thresholds, follow-up actions
n8n/                         importable n8n workflow
integrations/google-apps-script/Code.gs
examples/                    sample webhook payloads
tests/                       pytest suite + n8n parity runner
docs/                        setup, parity, deployment, handover, SEO
```

## Limitations

Stated plainly so nobody oversells this system:

- **Not yet verified against a live monday.com account.** The GraphQL queries match monday's documented API and are covered by tests against a fake, but you must run one real lead through your own board (see [docs/MONDAY_SETUP.md](docs/MONDAY_SETUP.md#verify-with-a-real-lead)) before going live.
- **SQLite, single instance.** No multi-replica deployment.
- **No background scheduler.** Due follow-ups are listed by the API; nothing pings the rep when a task becomes overdue.
- **No buyer-facing messages** (email, SMS, WhatsApp) by design.
- **monday.com sync is "at least once".** If the app crashes between the CRM call and saving its result, a resync could create one extra item. The window is tiny and the admin alert explains how to clean it up.

## Documentation

[Google Form setup](docs/GOOGLE_FORM_SETUP.md) · [monday.com setup](docs/MONDAY_SETUP.md) · [n8n workflow](docs/N8N_WORKFLOW.md) · [Python vs n8n parity](docs/PARITY.md) · [Workflow specification](docs/WORKFLOW.md) · [Deployment](docs/DEPLOYMENT.md) · [Client handover](docs/CLIENT_HANDOVER.md) · [Demo script](docs/VIDEO_DEMO_SCRIPT.md) · [SEO plan](docs/SEO.md)

## License

[MIT](LICENSE). Built by **Techtox**, an automation agency focused on practical business systems.
