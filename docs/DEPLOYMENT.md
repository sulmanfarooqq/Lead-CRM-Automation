# Deployment and operations

## Environment
Copy .env.example to .env locally. In hosted environments, add variables through the provider dashboard. Never commit credentials or production secrets.

## Render
Create a Blueprint from render.yaml. The service mounts persistent storage at /opt/render/project/src/data and points DATABASE_URL at the mounted SQLite file. Verify the chosen Render plan supports persistent disks before deploying. Use a long generated WEBHOOK_SECRET and configure Monday.com, SMTP and Slack variables only when those integrations are needed.

## Railway
Deploy from GitHub, use the Procfile command, attach a persistent volume and set DATABASE_URL to an absolute path inside the volume. Confirm the mount path matches the configured database path.

## Operations
- Check GET /health after deployment.
- Submit one test lead with the correct webhook secret.
- Check GET /api/leads and GET /api/stats.
- Verify Monday.com, SMTP and Slack delivery independently.
- Back up the database and test a restore.
- Do not run multiple app replicas against a local SQLite file.

## Scaling
SQLite is for a single low-volume instance. Move to managed PostgreSQL and use a distributed-safe assignment mechanism before scaling horizontally. Protect read endpoints, add rate limiting and request-size limits before exposing the service to real customer data.
