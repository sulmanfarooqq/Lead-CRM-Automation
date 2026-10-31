# Workflow specification

1. Receive an inquiry from a website form, Google Form bridge or trusted integration.
2. Authenticate the webhook secret and validate the payload.
3. Normalize contact details and require at least one valid contact method.
4. Detect repeat leads by email or phone.
5. Classify priority using the JSON rules.
6. Assign new leads using round-robin routing.
7. Save the lead, event record and follow-up task in SQLite.
8. Attempt Monday.com synchronization.
9. Attempt team notifications through SMTP and Slack.
10. Return a structured result to the source.

Repeat leads update the local record and retain their current owner. The current Monday.com adapter creates items; CRM-side duplicate update is a documented next step.
