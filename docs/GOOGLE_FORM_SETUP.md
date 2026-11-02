# Connect a Google Form

A Google Form cannot call a webhook by itself. [`integrations/google-apps-script/Code.gs`](../integrations/google-apps-script/Code.gs) is a small script, attached to the form's response sheet, that forwards each new response. It works with the Python service and with the n8n workflow.

## 1. Build the form

Use these question titles (case does not matter; extra spaces are ignored). Other wording is fine if you add it to `FIELD_TITLES` in the script.

| Question | Type | Accepted titles |
|---|---|---|
| Full Name | Short answer | full name, name, your name |
| Email | Short answer | email, email address, your email |
| Phone | Short answer | phone, phone number, mobile, mobile number, whatsapp number, contact number |
| Property Type | Dropdown or short answer | property type, type of property |
| Budget | Short answer | budget, your budget, budget (pkr) |
| Preferred Location | Short answer | preferred location, location, area, preferred area |
| Buying Timeline | Dropdown or short answer | buying timeline, timeline, when do you plan to buy, purchase timeline |
| Message | Paragraph | message, additional details, comments, notes |

Use **short answer** for Budget and Phone, not number validation, so people can type `1.5 crore` or `0300 1234567`. A dropdown for Buying Timeline with options like `Within 7 days`, `Within 30 days`, `In 3 months`, `Undecided` gives the cleanest classification.

## 2. Install the script

1. In the form open **Responses → Link to Sheets**, then open the sheet.
2. **Extensions → Apps Script**. Delete the sample code and paste the contents of `Code.gs`.
3. **Project Settings (gear icon) → Script properties → Add script property**:
   - `WEBHOOK_URL` — Python: `https://YOUR-HOST/webhooks/leads`. n8n: the **Production** URL of the webhook node (`https://YOUR-N8N/webhook/real-estate-lead`, not the `webhook-test` URL).
   - `WEBHOOK_SECRET` — the same value as the server's `WEBHOOK_SECRET` (for n8n, the `webhookSecret` value in the **Config** node).
4. Select `setupTrigger` in the function dropdown and **Run**. Approve the permissions (Sheets and external requests). This installs the "on form submit" trigger once.
5. Select `testSubmission` and **Run**. Open **Executions** to see the log line `HTTP 200 ...`.

The secret is stored in Script Properties, so it is not visible in the code if the sheet is shared.

## 3. Check it end to end

Submit the real form once. A Python deployment shows the lead in `GET /api/leads`; an n8n deployment shows an execution under **Executions**. A script failure (for example a wrong secret returns HTTP 401) appears in Apps Script **Executions**; add a failure-notification email under **Triggers → Failure notification settings** so you hear about it.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `HTTP 401` | `WEBHOOK_SECRET` differs between the script and the server |
| `HTTP 422` | The response has neither a valid email nor a valid phone. Check the question titles match the table |
| Fields arrive empty | The question title is not in `FIELD_TITLES`; add it |
| Nothing happens | The trigger is missing: run `setupTrigger` again and check **Triggers** |
| n8n shows no execution | You used the `webhook-test` URL, or the workflow is not **Active** |
