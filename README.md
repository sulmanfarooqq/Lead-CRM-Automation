# Techtox Lead & CRM Automation

Python-first, self-hostable lead response backend for real-estate agencies. Receives inquiries, validates contact details, detects repeat leads, classifies buying urgency, assigns sales reps, creates follow-up tasks, optionally syncs Monday.com and alerts the team.

> Demo foundation. Configure and test integrations with client-owned accounts before production. This version does not send messages to buyers.

## Demo video
After recording, upload your walkthrough to YouTube and replace this placeholder:
**[Watch the Techtox demo](ADD_YOUR_VIDEO_URL_HERE)**

Suggested walkthrough: submit lead → validation and priority → duplicate submission → assigned representative and follow-up → CRM/team notifications → invalid webhook secret.

## Architecture
```text
Website / Google Form
       |
POST /webhooks/leads
       |
Secret + payload validation
       |
Duplicate detection
       |
Priority classification
       |
Round-robin assignment
       |
SQLite persistence
   /          \
Monday.com   Follow-up task
   \          /
 SMTP email / Slack alert
```

## Features
- Shared-secret protected webhook and Pydantic validation.
- Email validation, phone normalization and budget parsing (thousand/lakh/crore).
- Urgent, High priority, Nurture and Needs review classifications.
- Local duplicate detection by email or normalized phone.
- Configurable round-robin sales assignment.
- SQLite lead, event and follow-up task storage.
- Optional Monday.com item creation, SMTP notifications and Slack alerts.
- Lead, due-follow-up and statistics API endpoints.
- JSON configuration, Render blueprint and Docker support.

## Run locally
Requirements: Python 3.11+ and pip.

```bash
git clone https://github.com/sulmanfarooqq/Lead-CRM-Automation.git
cd Lead-CRM-Automation
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` (PowerShell: `Copy-Item .env.example .env`). Set a unique `WEBHOOK_SECRET`. Edit `config/routing_rules.json` with the client's actual representatives. Then run:

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs.

## Test webhook
Set the `secret` in `examples/sample_lead.json` to match `WEBHOOK_SECRET`, then:

```bash
curl -X POST http://127.0.0.1:8000/webhooks/leads -H "Content-Type: application/json" -d @examples/sample_lead.json
```

For production, remove the JSON secret and send it as `X-Webhook-Secret` header.

## API
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Service information |
| GET | `/health` | Hosting health check |
| POST | `/webhooks/leads` | Receive and process lead |
| GET | `/api/leads` | List leads |
| GET | `/api/leads/{id}` | Read one lead |
| GET | `/api/follow-ups/due` | List due follow-ups |
| GET | `/api/stats` | Lead totals |

## JSON configuration
- `config/lead_fields.json`: field definitions.
- `config/routing_rules.json`: active reps, round-robin and qualification thresholds.
- `examples/sample_lead.json`: sample webhook payload.

Default qualification: Urgent (within 7 days; call within 1 hour), High priority (8–30 days; call within 24 hours), Nurture (over 30 days/undecided; follow up within 3 days), Needs review (missing/unreadable budget or timeline; verify within 1 day). Incomplete leads are retained for review. At least one valid email or phone is required.

## Monday.com
Create a Leads board and columns for Email, Phone, Property Type, Budget, Preferred Location, Buying Timeline, Message, Stage, Priority and Follow-up Due. Add the client's API token, board/group IDs and exact column IDs to hosting environment variables. Test on a dedicated board first.

**Current limitation:** the adapter creates a Monday.com item on each webhook call. Duplicate detection updates the local SQLite record, but remote Monday.com duplicate lookup/update is not implemented yet. Do not advertise cross-system deduplication as complete.

## Notifications
Configure SMTP to email the assigned rep and/or `SLACK_WEBHOOK_URL` to post to a team channel. Delivery is optional; response warnings report unconfigured or failed integrations. No buyer email/SMS is sent. Customer-facing messages require explicit client approval, consent review and approved templates.

## Deploy
**Render:** create a Blueprint from this repository, review `render.yaml`, deploy, set environment secrets, then test `/health` and the webhook. SQLite needs a persistent disk; confirm the chosen plan supports disks or use managed PostgreSQL. Ephemeral storage can lose data on redeploy.

**Railway:** deploy from GitHub, set start command to `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, attach a persistent volume, and set `DATABASE_URL` to the mounted absolute SQLite path (for example `sqlite:////app/data/leads.db`).

**Docker:**
```bash
docker build -t techtox-lead-agent .
docker run --env-file .env -p 8000:8000 -v lead-data:/app/data techtox-lead-agent
```

## Tests
```bash
pytest -q
```

## Production checklist
- Use and rotate a strong webhook secret; never commit credentials.
- Enforce HTTPS, rate limiting and request-size limits.
- Protect lead-reading endpoints with authentication before public exposure.
- Configure persistent storage, backups and restore tests.
- Test duplicate submissions, malformed payloads and integration outages.
- Review client privacy, retention and access requirements.
- Move to PostgreSQL and distributed-safe assignment before multiple replicas.

## Implementation boundaries
Single-instance demo foundation, not an enterprise CRM. SQLite suits low-volume single-instance use. The due-follow-up endpoint lists tasks but no scheduler runs automatically. No buyer calls, emails or SMS. Monday.com integration is create-only. These are documented future enhancements.

Built by **Techtox** — operational automation that captures leads and gives sales teams a clear next action.
