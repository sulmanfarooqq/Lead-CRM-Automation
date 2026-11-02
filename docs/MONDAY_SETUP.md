# monday.com setup

The same board layout works for the Python service and the n8n workflow.

## 1. Leads board

Create a board with these columns. Types matter: a wrong type makes monday.com reject the value.

| Column | Type | Python variable (n8n Config key) |
|---|---|---|
| Email | Email | `MONDAY_EMAIL_COLUMN_ID` (`colEmail`) |
| Phone | Text | `MONDAY_PHONE_COLUMN_ID` (`colPhone`) |
| Property Type | Text | `MONDAY_PROPERTY_TYPE_COLUMN_ID` (`colPropertyType`) |
| Budget | **Numbers** | `MONDAY_BUDGET_COLUMN_ID` (`colBudget`) |
| Preferred Location | Text | `MONDAY_LOCATION_COLUMN_ID` (`colLocation`) |
| Buying Timeline | Text | `MONDAY_TIMELINE_COLUMN_ID` (`colTimeline`) |
| Message | Long text | `MONDAY_MESSAGE_COLUMN_ID` (`colMessage`) |
| Stage | Status | `MONDAY_STAGE_COLUMN_ID` (`colStage`) |
| Priority | Status | `MONDAY_PRIORITY_COLUMN_ID` (`colPriority`) |
| Follow-up Due | Date | `MONDAY_FOLLOWUP_COLUMN_ID` (`colFollowUpDue`) |
| Owner (optional) | People | `MONDAY_OWNER_COLUMN_ID` (`colOwner`) |

Status labels (`New`, `Urgent`, `High priority`, `Nurture`, `Needs review`) are created automatically the first time they are used.

## 2. Follow-up tasks board (optional)

A second board with a **Date** column and a **Text** column for notes. Set `MONDAY_TASK_BOARD_ID`, `MONDAY_TASK_DUE_COLUMN_ID`, `MONDAY_TASK_NOTES_COLUMN_ID`. Each lead produces an item named `Follow up (Urgent): Ahmed Khan` with the due date and a link back to the lead. Leave `MONDAY_TASK_BOARD_ID` empty to skip tasks.

## 3. Find the IDs

- **API token:** monday.com → your avatar → **Developers → My access tokens** (or Admin → API). Keep it secret.
- **Board ID:** the number in the board URL (`.../boards/1234567890`).
- **Column IDs:** open the board, click a column header's **⋯ → Developer / Column ID** (enable *Developer mode* in your profile if you do not see it), or run this in monday's API playground:

```graphql
query { boards(ids: [YOUR_BOARD_ID]) { columns { id title type } } }
```

- **Group ID:** usually `topics` for the first group; the playground query `boards(ids:[ID]) { groups { id title } }` lists them.
- **Account URL:** `https://your-account.monday.com`, used only to build links.
- **Owner user IDs:** `query { users { id name email } }`, then put the number in `monday_user_id` for each rep in `config/routing_rules.json`.

## 4. Verify with a real lead

This integration is covered by automated tests against a fake monday.com, **not** against your real account, so do this once before launch:

1. Use a *copy* of the board, or accept that a test lead will appear.
2. Send `examples/sample_lead.json` (Python) or submit the form (n8n).
3. Check: an item named after the lead exists with email, phone, a numeric budget, priority and due date; its **Updates** tab holds the enquiry note; the tasks board has a follow-up item; Stage is `New`.
4. Send the same lead again. There must be **one** lead item, a second note, and a new task. Stage must not reset.
5. Change a column ID in `.env` to something wrong and send a lead: you should receive a `[FAILED]` admin alert naming the step, and `GET /api/leads?crm_status=failed` lists the lead. Fix the ID and call `POST /api/leads/{id}/resync`.

If step 4 shows a second item, the email column is not matching on lookup: confirm `MONDAY_EMAIL_COLUMN_ID` is the Email-type column's ID and report what monday returns.
