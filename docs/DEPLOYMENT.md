# Deployment and operations

## Before you deploy

1. Generate two secrets: `python -c "import secrets; print(secrets.token_urlsafe(32))"` for `WEBHOOK_SECRET`, and another for `API_KEY`.
2. Set `ENVIRONMENT=production`. In this mode the app **refuses to start** if either secret is missing, shorter than 16 characters, or a known placeholder, and the management API answers `503` if `API_KEY` is empty.
3. Replace the sample reps in `config/routing_rules.json` with real people (the app warns at startup while sample `@example.com` addresses remain).
4. Never commit `.env` or any token.

## Render

Create a **Blueprint** from the repository. `render.yaml` sets production mode, generates both secrets (read them in the Render dashboard → Environment), and mounts a 1 GB disk at `/opt/render/project/src/data` for the SQLite file. Persistent disks require a paid plan; on a free plan the database is wiped on every deploy. Add the `MONDAY_*`, `SMTP_*`, `SLACK_WEBHOOK_URL`, `SALES_REP_EMAIL` and `ADMIN_EMAIL` variables from `.env.example` in the dashboard.

## Railway

Deploy from GitHub (the `Procfile` provides the start command). Add a volume mounted at `/app/data` and set `DATABASE_URL=sqlite:////app/data/leads.db`, `ENVIRONMENT=production` and the secrets.

## Docker

```bash
docker build -t lead-response-agent .
docker run -d --name lead-agent --env-file .env -p 8000:8000 -v lead-data:/app/data lead-response-agent
```

The container runs as an unprivileged user, stores the database in the `/app/data` volume, and has a built-in health check.

## After deploying

- `GET /health` returns `{"status":"ok"}`.
- Send one test lead with the secret; confirm it in `GET /api/leads` (with `X-API-Key`).
- Verify monday.com, email and Slack delivery separately ([MONDAY_SETUP.md](MONDAY_SETUP.md#verify-with-a-real-lead)).
- Put the service behind HTTPS (Render and Railway do this for you; add a reverse proxy elsewhere).

## Operations

- **Backups:** copy the SQLite file while the service is idle, or use `sqlite3 leads.db ".backup backup.db"`. Test a restore.
- **Monitoring:** watch `GET /health` and `GET /api/stats` (`by_crm_status.failed` should stay at zero). Failures also reach `ADMIN_EMAIL`.
- **Stuck CRM sync:** `GET /api/leads?crm_status=failed`, fix the cause, then `POST /api/leads/{id}/resync` for each.
- **Logs:** set `LOG_LEVEL=DEBUG` temporarily if needed; tokens and passwords are never logged.

## Scaling limits

Run exactly **one** instance. SQLite and the in-process background work are designed for a single low-volume service; the round-robin and duplicate checks are only safe within one process. Moving to several replicas needs PostgreSQL and a shared job queue. Add rate limiting at your proxy or platform if the webhook URL is public.
