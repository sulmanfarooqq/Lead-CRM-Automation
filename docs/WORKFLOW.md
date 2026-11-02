# Workflow specification (Python service)

The n8n equivalent is described in [N8N_WORKFLOW.md](N8N_WORKFLOW.md); differences are listed in [PARITY.md](PARITY.md).

## Synchronous part (before the caller gets an answer)

1. Receive an enquiry from a website form, the Google Form bridge, or another trusted system.
2. Check the webhook secret (`X-Webhook-Secret` header or `secret` in the body). Wrong → `401`, nothing stored.
3. Normalise: trim and collapse whitespace, lower-case the email, convert the phone to E.164, parse the budget to a number.
4. Reject only if there is **no valid email and no valid phone** (`422`, admin alerted, nothing stored). Everything else becomes a flag.
5. Find an existing lead by email, then by phone.
6. Classify with the rules in `config/routing_rules.json` (flags from step 3 force *Needs review*).
7. New lead → assign the next active rep (round-robin). Repeat lead → keep its owner and its earlier details.
8. Save the lead, a follow-up task and an event, in one database transaction.
9. Answer `200` with the lead id, priority, owner, due time and any warnings.

## Background part (after the answer; failures never lose the lead)

10. monday.com (if configured): find the item (stored id, then email, then phone) → update or create → add an activity note → create a follow-up task on the tasks board. Each stage's id is saved on the lead, so a retry skips what already succeeded.
11. Email the assigned rep and/or post to Slack. The buyer is never contacted.
12. On any failure: store `crm_sync_status = failed` and the error on the lead, and send the admin an alert with manual steps. `POST /api/leads/{id}/resync` retries.

## Follow-up tasks

Every enquiry creates a task (`Open`). `GET /api/follow-ups/due` lists open tasks that are due, and `POST /api/follow-ups/{id}/complete` closes one. There is no scheduler that pings anyone when a task becomes due.
