# n8n workflow

File: [`n8n/real-estate-lead-response-agent.json`](../n8n/real-estate-lead-response-agent.json) (22 nodes, included unchanged).

## Import and configure

1. n8n → **Workflows → Import from file** → choose the JSON.
2. **Credentials**
   - *Header Auth* named `monday.com API Token`: Name `Authorization`, Value = your monday.com API token. Select it on the five monday.com HTTP nodes (Find Existing Lead, Update Existing Lead, Create New Lead, Log Enquiry Update, Create Follow-up Task).
   - *Gmail OAuth2*. Select it on the three Gmail nodes (Email Sales Rep, Notify Admin: Rejected, Alert Admin: Failure).
3. Open the **Config** node and replace every `REPLACE_...` value with your IDs ([docs/MONDAY_SETUP.md](MONDAY_SETUP.md)), plus `salesRepEmail`, `adminEmail`, and a long random `webhookSecret`. If you leave `webhookSecret` empty, authentication is switched off.
4. **Activate** the workflow and copy the **Production** URL of the *Google Form Webhook* node (`/webhook/real-estate-lead`). Use that URL in the Apps Script ([docs/GOOGLE_FORM_SETUP.md](GOOGLE_FORM_SETUP.md)).

## Flow

```text
Google Form Webhook → Config → Normalize & Validate → Is Valid?
   valid   → Classify Lead → Find Existing Lead → Parse Lookup → Lead Exists?
                 yes → Update Existing Lead ┐
                 no  → Create New Lead      ┴→ Resolve Lead ID → Log Enquiry Update
                        → Create Follow-up Task → Verify Follow-up → Email Sales Rep
   invalid → Build Reject Report → Notify Admin: Rejected
   any error output → Build Failure Report → Alert Admin: Failure
```

Business rules are the same as the Python service; see [PARITY.md](PARITY.md). Things specific to n8n:

- The webhook answers `200` immediately, whatever happens afterwards.
- A wrong `secret` is dropped silently (no admin email) so an attacker cannot flood your inbox.
- **Retry a failed run safely** from **Executions → open the run → Retry**; the duplicate lookup makes it update the existing item. If the failed step was *Email Sales Rep*, do not retry (the lead and task already exist); tell the rep yourself.

## Test without a form

```bash
curl -X POST https://YOUR-N8N/webhook/real-estate-lead \
  -H "Content-Type: application/json" \
  -d '{"secret":"YOUR_SECRET","fullName":"Ahmed Khan","email":"ahmed@example.com","phone":"0300 1234567","propertyType":"Plot","budget":"PKR 1.5 crore","preferredLocation":"Islamabad","buyingTimeline":"within 7 days","message":"Please call me"}'
```

While building, use the **Test** URL (`/webhook-test/...`) and click *Listen for test event* first.
