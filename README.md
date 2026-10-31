# Techtox Lead & CRM Automation — Python Lead Management System

**Techtox Lead & CRM Automation** is a Python and FastAPI project that helps real-estate teams capture website inquiries, validate lead data, detect duplicate leads, qualify sales opportunities, assign leads to representatives, and create follow-up tasks. It is a self-hostable **lead management automation** backend built by **Techtox**, an automation agency focused on practical business systems.

Use this project as a starting point for a **real estate CRM automation**, **lead capture webhook**, or **sales lead routing system**. It includes JSON configuration, SQLite persistence, optional Monday.com CRM sync, Slack and email team notifications, Docker support, and a Render deployment blueprint.

> **Project status:** Demonstration foundation, not a fully managed production CRM. Configure and test all integrations with client-owned accounts before production. This version does not send messages to buyers.

## Techtox agency project

This repository is part of the **Techtox AI Automation** portfolio. Techtox builds business automation systems that reduce repetitive operational work and help teams respond to enquiries consistently. This project demonstrates one specific service: **lead capture, CRM updates, lead qualification, sales assignment, and follow-up task automation**.

- Agency: **Techtox**
- Service: Lead & CRM Automation
- Primary use case: Real-estate lead management and sales follow-up
- Built with: Python, FastAPI, SQLite, JSON, Monday.com API, Slack webhooks
- Repository: [Techtox Lead & CRM Automation on GitHub](https://github.com/sulmanfarooqq/Lead-CRM-Automation)

## Demo video

After recording the walkthrough, upload it to YouTube and replace this placeholder:

**[Watch the Techtox Lead & CRM Automation demo](ADD_YOUR_VIDEO_URL_HERE)**

Suggested walkthrough: submit a lead → validate and qualify it → submit a duplicate → show sales representative assignment and follow-up task → show CRM/team notification → test an invalid webhook secret.

## What this lead automation system does

1. **Captures leads:** receives inquiries from a website, form, or another system through a secure webhook.
2. **Validates lead data:** checks required fields, validates email format, and normalizes phone numbers.
3. **Detects duplicates:** checks existing local records by email or normalized phone number.
4. **Qualifies sales leads:** classifies inquiries using the configured budget and buying timeline rules.
5. **Routes leads to sales reps:** assigns new leads with configurable round-robin distribution.
6. **Creates follow-up tasks:** stores the next action and due time for the sales team.
7. **Connects business tools:** optionally creates Monday.com items and sends internal Slack or SMTP notifications.

## Key features

- Python lead management API built with FastAPI.
- Secure inbound lead capture webhook using a shared secret.
- Pydantic request validation and email validation.
- Phone normalization, including Pakistan country-code handling.
- Budget parsing for thousand, lakh, and crore formats.
- Lead qualification: Urgent, High priority, Nurture, and Needs review.
- Duplicate lead detection by email or normalized phone.
- Configurable round-robin lead distribution.
- SQLite storage for leads, events, and follow-up tasks.
- Optional Monday.com CRM integration.
- Optional Slack alerts and internal email notifications.
- REST API endpoints for leads, follow-ups, health, and statistics.
- JSON-based lead fields and sales routing rules.
- Docker, Render, and Railway deployment guidance.

## Workflow architecture

```text
Website / Lead Form / External System
                 |
                 v
          POST /webhooks/leads
                 |
                 v
       Shared Secret + Validation
                 |
                 v
         Duplicate Lead Check
                 |
                 v
        Lead Qualification Rules
                 |
                 v
        Round-Robin Lead Routing
                 |
                 v
          SQLite Lead Storage
              /       \
             v         v
      Monday.com    Follow-up Task
             \         /
              v       v
        Internal Team Notifications
             Slack / SMTP
```

## Technology stack

| Technology | Purpose |
|---|---|
| Python 3.11+ | Backend programming language |
| FastAPI | Webhook and REST API framework |
| Pydantic | Request validation |
| SQLite | Local lead and task persistence |
| JSON | Lead fields and routing configuration |
| Monday.com GraphQL API | Optional CRM item creation |
| Slack Webhooks | Optional team notifications |
| SMTP | Optional internal email notifications |
| Docker | Containerized deployment |
| Render / Railway | Hosting options |

## Run Techtox Lead & CRM Automation locally

### Requirements

- Python 3.11 or newer
- pip
- Git

### 1. Clone the repository

```bash
git clone https://github.com/sulmanfarooqq/Lead-CRM-Automation.git
cd Lead-CRM-Automation
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` (PowerShell: `Copy-Item .env.example .env`). Set a unique `WEBHOOK_SECRET`. Edit `config/routing_rules.json` and replace the sample sales representatives with the client's actual team members.

### 5. Start the API

```bash
uvicorn app.main:app --reload
```

Open the interactive API documentation at http://127.0.0.1:8000/docs.

## Test the lead capture webhook

Set the `secret` in `examples/sample_lead.json` to match `WEBHOOK_SECRET`, then send a test inquiry:

```bash
curl -X POST http://127.0.0.1:8000/webhooks/leads -H "Content-Type: application/json" -d @examples/sample_lead.json
```

For production, remove the JSON secret from the payload and send it in the `X-Webhook-Secret` request header.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Service information |
| GET | `/health` | Hosting health check |
| POST | `/webhooks/leads` | Capture and process a new lead |
| GET | `/api/leads` | List stored leads |
| GET | `/api/leads/{id}` | Retrieve one lead |
| GET | `/api/follow-ups/due` | List due follow-up tasks |
| GET | `/api/stats` | Lead statistics |

## Configure lead fields and sales routing with JSON

- `config/lead_fields.json`: field definitions used by the lead intake workflow.
- `config/routing_rules.json`: sample sales representatives, round-robin assignment, qualification thresholds, and follow-up timing.
- `examples/sample_lead.json`: example real-estate lead webhook payload.

Default qualification rules:

| Classification | Example condition | Suggested next action |
|---|---|---|
| Urgent | Buying within 7 days | Call within 1 hour |
| High priority | Buying within 8–30 days | Call within 24 hours |
| Nurture | Buying after 30 days or undecided | Follow up within 3 days |
| Needs review | Missing or unreadable budget/timeline | Verify within 1 day |

Incomplete leads are retained for review. At least one valid email address or phone number is required.

## Monday.com CRM integration

Create a dedicated Leads board with columns for Email, Phone, Property Type, Budget, Preferred Location, Buying Timeline, Message, Stage, Priority, and Follow-up Due. Add the client's API token, board/group IDs, and exact column IDs to the hosting environment variables. Test the integration on a dedicated board before connecting live client data.

**Current limitation:** the adapter creates a Monday.com item on each webhook call. Duplicate detection updates the local SQLite record, but remote Monday.com duplicate lookup/update is not implemented. Repeated webhook submissions may therefore create repeated Monday.com items. Do not present cross-system deduplication as complete.

## Internal notifications

Techtox Lead & CRM Automation can optionally notify the assigned representative or internal team through:

- SMTP email notifications.
- Slack incoming webhook notifications.

These are internal team notifications. This version does **not** send buyer-facing email, SMS, or WhatsApp messages. Customer-facing communication requires client approval, consent review, and approved message templates.

## Deployment

### Render

Create a Blueprint from this repository, review `render.yaml`, deploy, configure environment secrets, and test `/health` and the lead webhook. SQLite requires persistent storage. Confirm that the selected hosting plan supports a persistent disk or use managed PostgreSQL. Ephemeral storage can lose data during redeployment.

### Railway

Deploy from GitHub, set the start command to:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Attach a persistent volume and configure `DATABASE_URL` to use the mounted absolute SQLite path (for example, `sqlite:////app/data/leads.db`).

### Docker

```bash
docker build -t techtox-lead-automation .
docker run --env-file .env -p 8000:8000 -v lead-data:/app/data techtox-lead-automation
```

## Run tests

```bash
pytest -q
```

## Production readiness checklist

- Use and rotate a strong webhook secret; never commit credentials.
- Enforce HTTPS, rate limiting, and request-size limits.
- Protect lead-reading API endpoints with authentication before public exposure.
- Configure persistent storage, backups, and restore tests.
- Test duplicate submissions, malformed payloads, and integration outages.
- Review client privacy, data retention, and access requirements.
- Move to PostgreSQL and distributed-safe assignment before running multiple application replicas.

## Known limitations

This is a single-instance demonstration foundation, not an enterprise CRM. SQLite is suitable for low-volume, single-instance use. The due-follow-up endpoint lists tasks, but no background scheduler runs automatically. Buyer calls, emails, SMS, and WhatsApp messages are not implemented. Monday.com integration is create-only. These are future enhancements, not current features.

## SEO and discoverability

See [`docs/SEO.md`](docs/SEO.md) for the Techtox GitHub repository description, recommended GitHub topics, target search phrases, website title and meta description, service-page structure, and technical SEO checklist.

## About Techtox

**Techtox** is an AI automation agency focused on building useful business systems rather than unnecessary software. The Techtox automation service portfolio includes lead capture and CRM automation, appointment and follow-up workflows, and AI-assisted customer support. This GitHub repository documents the technical foundation of the **Techtox Lead & CRM Automation** service.

For business enquiries or a discussion about adapting this workflow, visit the Techtox website or contact the Techtox team through its official business channels.

---

**Built by Techtox — Lead capture, CRM workflow automation, and sales follow-up systems.**
