# Python service vs n8n workflow: parity report

The Python service is meant to behave like [`n8n/real-estate-lead-response-agent.json`](../n8n/real-estate-lead-response-agent.json). This page says exactly what is identical, what is proven, and what differs on purpose.

## How parity is proven

[`tests/test_parity_n8n.py`](../tests/test_parity_n8n.py) loads the workflow file, extracts the JavaScript of the **Normalize & Validate** and **Classify Lead** Code nodes, and runs it in Node.js ([`tests/parity/n8n_runner.js`](../tests/parity/n8n_runner.js)) on each of the 44 enquiries in [`tests/parity/cases.json`](../tests/parity/cases.json). The Python functions must return the same values for:

`rejected`, `reject reason`, `name`, `email`, `phone (E.164)`, `budget`, `validation flags`, `priority`, `review reasons`, `timeline in days`, `follow-up action`.

The cases cover every priority, timeline keywords and ranges, every phone format, budget units, missing and invalid fields, rejection, and all three contradiction rules. Editing the rules in one implementation without the other makes this test fail. Running the *original* Python code (the first commit of this repository) through the same 44 cases showed it disagreed with the workflow on 8 of them. All are fixed: it classified `exploring` and `6+ months` as Needs review instead of Nurture; it read a budget of "5 marla" as 5 million (the workflow reads 5, because `m` only counts as a unit when it stands alone); it treated a budget of `0` as valid and marked the lead Urgent; it rejected a short number starting with `92` that the workflow accepts; and it had none of the three contradiction rules, so a "6 months" lead whose message said "urgent" was filed as Nurture, and an "undecided" one likewise.

## Step-by-step comparison

| Step | n8n workflow | Python service | Same? |
|---|---|---|---|
| Intake | Webhook `real-estate-lead` | `POST /webhooks/leads` | Same data |
| Field names | camelCase and Title Case | snake_case, camelCase and Title Case | Python accepts a superset |
| Secret | `body.secret` | `X-Webhook-Secret` header **or** `secret` in body | Python accepts a superset |
| Validate / normalise | Normalize & Validate node | `normalize_lead()` | **Proven identical** |
| Reject rule | no valid email **and** no valid phone | same | **Proven identical** |
| Classify | Classify Lead node | `classify_lead()` | **Proven identical** |
| Duplicate lookup | monday.com by email, else by phone | local DB by email then phone, **and** monday.com by email then phone | Python searches both identifiers |
| Create / update | `create_item` / `change_multiple_column_values`, stage set only on create | same GraphQL, stage set only on create | Same |
| Activity note | `create_update` with HTML summary | same content | Same |
| Follow-up task | item on the tasks board | same | Same (optional in Python) |
| Team email | Gmail to one `salesRepEmail` | SMTP to the assigned rep | Different transport |
| Retries | 3 tries, 2 s apart | 3 tries, 2 s apart | Same |
| Failures | error output → admin email with manual steps | recorded on the lead + admin email/Slack with manual steps | Same intent |
| Rejected lead | admin email, nothing stored | admin email/Slack, nothing stored | Same |
| Bad secret | ignored silently, no admin email | `401`, no admin alert | Python is stricter |

## Intentional differences

1. **HTTP responses.** n8n answers `200` immediately for everything (its webhook is set to respond when received), so a caller can never learn that a lead was rejected. Python answers `401` for a bad secret, `422` for a rejected lead and `200` with the result for a stored lead. Both processing paths then continue the same way.
2. **Local database.** Python stores every lead, task and event in SQLite and can list, filter and report on them. The n8n flow keeps nothing outside monday.com.
3. **Round-robin routing.** Python assigns each new lead to the next active rep in `config/routing_rules.json` (and can set the monday.com Owner column through `monday_user_id`). The n8n flow has one `salesRepEmail`, and optionally one `salesRepMondayUserId`.
4. **Repeat enquiries keep earlier details.** If a returning buyer sends a form with a blank location, Python keeps the stored one and clears a "Missing phone" flag that the stored record already answers. n8n sends only the fields that are present, so monday.com keeps its existing values too, but it would still flag the repeat as missing a phone.
5. **Follow-up due time.** n8n stores a date (`yyyy-MM-dd`; Urgent is "today"). Python also keeps the precise time (Urgent is "now + 1 hour") and sends the date part to monday.com. Around midnight, the date Python sends can be one day later than n8n's.
6. **Slack and the management API** exist only in Python.
7. **Email service.** n8n uses Gmail OAuth2; Python uses any SMTP server. Python replaces the sample `@example.com` rep addresses with `SALES_REP_EMAIL` so a template address never receives real leads.

## What is *not* proven

- Neither implementation has been run against a live monday.com account in this repository's tests. The Python monday.com client is exercised against an in-memory fake that implements the same four GraphQL operations the workflow uses. Run one real lead through your board before launch ([docs/MONDAY_SETUP.md](MONDAY_SETUP.md#verify-with-a-real-lead)).
- The n8n workflow itself (node wiring, credentials, Gmail) was not executed inside n8n here. Only its Code-node logic was run, and its connections were checked to point at existing nodes.
