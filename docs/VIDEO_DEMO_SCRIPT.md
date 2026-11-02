# Demo recording outline (3–5 minutes)

Record with a test board and fake data. Never show real customer details, API tokens, webhook secrets or private account pages.

1. **Problem (20 s).** Enquiries arrive late, get copied into a CRM by hand, and nobody knows who should call first.
2. **Submit the form (30 s).** Fill the Google Form as "Ahmed Khan", `0300 1234567`, `PKR 1.5 crore`, `within 7 days`.
3. **Show the result (60 s).** monday.com: the new item with a normalised phone and numeric budget, priority **Urgent**, the follow-up task, and the activity note. Open the sales rep's email.
4. **Repeat the enquiry (30 s).** Submit the same email again: one lead item, a second note, a new task, stage unchanged.
5. **Needs review (30 s).** Submit a lead with `negotiable` as the budget, or a 6-month timeline with an "urgent" message, and show the flags.
6. **Rejection and security (30 s).** A lead with no email or phone is refused and the admin is alerted; a wrong secret returns `401`.
7. **API and docs (30 s).** `/docs`, `GET /api/leads`, `GET /api/stats`.
8. **Failure handling (30 s).** Show the `[FAILED]` admin email and `POST /api/leads/{id}/resync`.
9. **Close (20 s).** Same logic as the n8n workflow (mention the parity tests); deployed on Render or Docker; the system never messages buyers.

After uploading the video, add its link under the first heading of the README.
