# SEO Plan — Techtox Lead & CRM Automation

This document defines how to describe and promote this project consistently across GitHub, search engines, and the Techtox website.

## 1. Primary search intent

This repository is a Python/FastAPI lead-management automation backend. Its strongest, accurate search themes are:

| Priority | Keyword phrase | Where to use it |
|---|---|---|
| Primary | lead management automation | README title, opening description, service page |
| Primary | CRM automation | README, project description, Techtox service page |
| Primary | Python lead management system | README and technical documentation |
| Secondary | real estate lead automation | Use-case section and Techtox service page |
| Secondary | lead capture webhook | Technical description and API documentation |
| Secondary | automated lead routing | Workflow and feature descriptions |
| Secondary | sales lead follow-up automation | Service page and demo video description |
| Secondary | FastAPI CRM integration | Technology and implementation documentation |
| Secondary | Monday.com CRM integration | Integration documentation |
| Secondary | lead qualification system | Feature description and workflow explanation |

Use related phrases naturally where they accurately describe the code. Do not add unrelated keywords such as AI chatbot, voice agent, WhatsApp automation, or email marketing automation as if this repository implemented them.

## 2. Suggested GitHub repository metadata

Set these fields manually in the repository's **About** section on GitHub.

**Suggested description (copy exactly):**

```text
Python lead management and CRM automation system by Techtox. Capture website leads, validate and qualify inquiries, detect duplicates, route sales reps, and create follow-up tasks with FastAPI.
```

**Suggested topics:**

```text
python
fastapi
crm-automation
lead-management
lead-generation
lead-capture
lead-routing
sales-automation
real-estate-automation
monday-com
slack-webhook
sqlite
```

Keep topics relevant to the actual code. GitHub topics help classify repositories and make related projects discoverable.

## 3. Techtox website landing page SEO

The GitHub repository is a technical portfolio asset. To attract potential customers from Google, publish a dedicated, indexable service page on the official Techtox website. Do not rely on the repository README as the agency's only landing page.

**Suggested page URL:**

```text
/services/lead-crm-automation
```

**Suggested page title:**

```text
Lead & CRM Automation for Real Estate Teams | Techtox
```

**Suggested meta description:**

```text
Techtox builds lead and CRM automation for real estate teams. Capture website inquiries, qualify leads, route them to sales reps, and organize follow-ups.
```

**Suggested H1:**

```text
Lead & CRM Automation for Real Estate Teams
```

**Suggested opening copy:**

```text
Techtox builds lead management automation systems that help real estate teams handle new inquiries consistently. Capture leads from website forms, validate contact details, identify priority inquiries, assign leads to the right sales representative, and organize follow-up tasks in your CRM workflow.
```

The service page must explain the actual service, supported integrations, setup process, limitations, and how a prospect can book a consultation. Add screenshots or a genuine walkthrough video of the working demo. Do not claim guaranteed conversion increases or features that have not been built.

## 4. Recommended service-page structure

1. H1: Lead & CRM Automation for Real Estate Teams
2. The problem: delayed replies, unassigned inquiries, scattered lead records, and missed follow-ups.
3. How the Techtox system works: capture → validate → qualify → assign → track → notify.
4. Features: lead capture, duplicate checks, qualification, sales routing, CRM sync, and internal notifications.
5. Integrations: list only integrations that are currently supported and tested.
6. A real demo: show a sample inquiry moving through the workflow.
7. Implementation process: discovery, workflow mapping, configuration, testing, handover, and support.
8. FAQs: CRM compatibility, data handling, setup requirements, and what happens when an integration fails.
9. CTA: book a meeting with Techtox.

Create separate pages only when there is enough genuinely useful, distinct content. Do not publish near-identical pages targeting tiny keyword variations.

## 5. Technical SEO checklist for the Techtox website

- Give every important page a unique, descriptive HTML `<title>` and meta description.
- Use one clear visible H1 that accurately describes the page.
- Use descriptive URLs and meaningful internal link text.
- Ensure the page works on mobile and loads reliably over HTTPS.
- Add descriptive alt text to meaningful screenshots and diagrams.
- Use canonical URLs where duplicate or alternate URLs exist.
- Create an XML sitemap containing canonical, indexable pages and submit it in Google Search Console.
- Make sure `robots.txt` does not accidentally block important pages.
- Add Open Graph metadata for clean sharing previews.
- Add relevant structured data only when it accurately describes the business or page; validate it before publishing.
- Link the service page to related Techtox services, the contact/booking page, and the project demo.
- Add the page to Google Search Console and monitor indexing, queries, impressions, clicks, and technical issues.

Do not add a `meta keywords` tag for Google. Google says it does not use that tag for ranking. Repeating keywords unnaturally is keyword stuffing, not SEO.

## 6. Build credibility and discovery

- Publish a real project walkthrough on the Techtox website and YouTube.
- Link the demo video back to the matching Techtox service page.
- Link the GitHub repository from the service page as technical project documentation.
- Share useful implementation notes on relevant professional channels, with a link to the detailed project page.
- Ask collaborators or clients for relevant, genuine references when appropriate; do not buy links or create fake testimonials.
- Keep screenshots, setup instructions, integrations, and limitations current.

## 7. Measure results

Use Google Search Console to monitor the Techtox domain, not just GitHub. Track:

- Whether the service page is indexed.
- Search queries that produce impressions.
- Click-through rate for the page's search result.
- Organic clicks to the service page.
- Qualified enquiries and booked meetings originating from organic search.

SEO is an ongoing process. Rankings and indexing are not guaranteed, and changes can take time to be reflected in search results.

## 8. Accuracy rules for Techtox marketing

This repository currently supports local duplicate detection, lead qualification, round-robin assignment, SQLite persistence, optional Monday.com item creation, and optional internal Slack/SMTP notifications.

It currently does not provide an automatic background follow-up scheduler, buyer-facing email/SMS/WhatsApp messaging, remote Monday.com duplicate lookup/update, or multi-instance PostgreSQL deployment. Do not claim these as available features on GitHub, the Techtox website, proposals, or demo videos until they are implemented and tested.
