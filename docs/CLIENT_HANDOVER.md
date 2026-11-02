# Client handover checklist

## Agree with the client

- [ ] Lead sources and the exact form questions ([GOOGLE_FORM_SETUP.md](GOOGLE_FORM_SETUP.md)).
- [ ] Priority thresholds and follow-up times (`config/routing_rules.json`).
- [ ] Active sales reps, their emails and monday.com user IDs.
- [ ] Who receives admin alerts (`ADMIN_EMAIL`) and who answers them.
- [ ] That buyers are **never** contacted automatically; written approval is needed before any buyer-facing message is added.

## Configure

- [ ] monday.com Leads board and Tasks board with the right column types ([MONDAY_SETUP.md](MONDAY_SETUP.md)).
- [ ] Secrets set in the hosting dashboard, not in Git.
- [ ] SMTP and/or Slack set up with the client's approval.
- [ ] Persistent storage and a backup routine ([DEPLOYMENT.md](DEPLOYMENT.md)).

## Test before go-live

- [ ] New lead appears in monday.com with a task and the team gets the email.
- [ ] The same lead again: still one lead item, a new note, stage not reset.
- [ ] A lead with a bad phone or missing budget lands in **Needs review**.
- [ ] A lead with no valid email or phone is rejected and the admin is alerted.
- [ ] A wrong webhook secret is refused.
- [ ] Break a monday.com column ID on purpose: the admin gets a `[FAILED]` alert; after the fix `resync` repairs it.

## Hand over

- [ ] Webhook URL, API key location and the `/docs` page.
- [ ] A recorded walkthrough ([VIDEO_DEMO_SCRIPT.md](VIDEO_DEMO_SCRIPT.md)) with no real customer data in it.
- [ ] The limitations from the README, said out loud: single instance, no overdue-task reminders, no buyer messaging.
- [ ] Who to contact for support and how changes to rules are requested.
