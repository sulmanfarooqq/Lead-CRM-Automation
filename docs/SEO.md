# SEO and discoverability plan

How to make this repository and the matching Techtox service page easy to find, without claiming anything the code does not do.

## 1. GitHub repository settings (set these manually)

GitHub's search weighs the repository name, description, topics and README. The *About* box and topics can only be edited on github.com (repository page → gear icon next to **About**).

**Description** (paste as is, under GitHub's 350-character limit):

```text
Real estate lead automation: capture Google Form and website leads, validate and qualify them, remove duplicates, route to sales reps, sync to monday.com and alert the team. Python FastAPI service plus an importable n8n workflow.
```

**Website:** your Techtox service page, or the demo video once it exists.

**Topics** (GitHub allows 20; these 18 all describe real features):

```text
python fastapi n8n n8n-workflow monday-com crm crm-automation lead-management
lead-generation lead-routing real-estate real-estate-automation sales-automation
google-forms webhook workflow-automation sqlite automation
```

**Social preview image:** Settings → General → Social preview. A 1280×640 image of the flow diagram or the monday.com board makes shared links stand out.

**Pin** the repository on your GitHub profile, and consider a short release (`v1.1.0`) so it shows under *Releases*.

## 2. What the README already does for search

- The H1 and first paragraph contain the phrases people search for: *real estate lead automation*, *lead & CRM automation*, *monday.com*, *n8n*, *FastAPI*.
- A comparison table makes it clear that both a Python service and an n8n workflow are included, which matches two different search audiences.
- Headings are descriptive and the table of contents links to them, which GitHub renders as page anchors.
- Honest limitations are included. This builds trust with clients and reviewers, and avoids claims that cannot be defended.

## 3. Target phrases

| Priority | Phrase | Where it appears |
|---|---|---|
| Primary | real estate lead automation | README H1, description, topics |
| Primary | lead management automation / CRM automation | README, description |
| Primary | n8n lead workflow, n8n monday.com | README, N8N_WORKFLOW.md |
| Secondary | Google Form to CRM, Google Forms webhook | GOOGLE_FORM_SETUP.md |
| Secondary | FastAPI lead capture webhook | README, API reference |
| Secondary | lead routing round robin, lead qualification | README, WORKFLOW.md |

Use phrases only where they are true. Do not add keywords for features that are absent (AI chatbot, WhatsApp automation, voice agent, SMS follow-up).

## 4. Techtox website service page

A GitHub README is a technical asset, not an agency landing page. For client enquiries publish a page such as `/services/lead-crm-automation` on the Techtox site.

- **Title:** `Lead & CRM Automation for Real Estate Teams | Techtox`
- **Meta description:** `Techtox builds lead and CRM automation for real estate teams: capture website and Google Form enquiries, qualify and route leads, and organise follow-ups in monday.com.`
- **H1:** `Lead & CRM Automation for Real Estate Teams`
- **Structure:** the problem → how it works (capture, validate, qualify, assign, track, notify) → features → integrations that are actually tested → a real demo video → implementation process → FAQs (data handling, what happens when the CRM is down) → call to action.
- Link to this repository and to the demo video, and link back from the README.

Technical checklist: unique title and description per page, one H1, descriptive URLs, HTTPS, mobile-friendly, alt text on screenshots, canonical URL, XML sitemap submitted in Google Search Console, no `meta keywords` (Google ignores it), and structured data only where it accurately describes the page.

## 5. Build credibility honestly

- Record the demo ([VIDEO_DEMO_SCRIPT.md](VIDEO_DEMO_SCRIPT.md)), publish it on YouTube, and link it in the README and the website.
- Share what you learned (for example, the parity test that runs the n8n code in Node) as a short post linking to the repository.
- Ask real clients for real references. Do not buy links or write testimonials.

## 6. Accuracy rules for all marketing

This project currently provides: webhook capture, validation, duplicate detection (local and in monday.com), rule-based classification, round-robin routing, monday.com sync with notes and tasks, internal email/Slack alerts, failure alerts and resync, and a protected management API.

It does **not** provide: buyer-facing email, SMS or WhatsApp; automatic overdue-task reminders; multi-instance or PostgreSQL deployment; AI-based qualification; or a verified live monday.com integration until you have run the check in [MONDAY_SETUP.md](MONDAY_SETUP.md#verify-with-a-real-lead). Do not claim these on GitHub, the website, proposals or videos. Rankings and indexing are never guaranteed and take time.
