# Business Proposal: Alex — AI Agent System for Insurance Brokerage Operations

**Prepared for:** Insurance Brokerage Client (Germany / Romania)
**Prepared by:** Managed Service Provider — AI Systems & Automation
**Date:** March 2026
**Document Reference:** OFFER-2026-INS-EN-002
**Valid Until:** April 7, 2026

---

## Executive Summary

We propose deploying **Alex**, a fully custom AI agent system built specifically for your insurance brokerage, operating under BaFin (Germany) and ASF (Romania) regulatory frameworks.

Alex is already built and running. A live demo is available today.

This proposal covers everything: the initial build and cloud setup, employee training, and ongoing managed operation. You pay once to get started, then a predictable monthly fee for the system to keep running and improving.

| | |
|---|---|
| **One-time implementation fee** | **€3,500** |
| **Monthly managed service** | **from €490/month** |
| **AI API costs (your account)** | **~€18–95/month** depending on usage |
| **Minimum commitment** | 3 months |

---

## The Problem: Manual Work Is Your Biggest Bottleneck

For a 2–5 person brokerage, every hour spent on administrative work is an hour not spent on clients. The daily burden includes:

- Manually searching and comparing products across 5–10 insurers
- Writing renewal notices and client letters from scratch, every time
- Processing scanned documents, accident photos, and handwritten forms by hand
- Preparing ASF and BaFin monthly compliance reports manually
- Tracking clients and policies across spreadsheets, email threads, and PDFs
- Each employee working differently — no standardised, auditable process

A small team cannot scale under these conditions. Hiring more people is expensive. Compliance errors carry regulatory risk. Client response times suffer.

---

## The Solution: Alex — Your Dedicated Brokerage AI

Alex is not a generic chatbot. It is a structured AI agent connected directly to your data, built around insurance brokerage workflows, and accessible by every employee from a browser — no installation, no technical knowledge required.

---

## What Each Employee Can Do with Alex

### Employee A — Client-Facing Broker

**Morning routine (2 minutes instead of 30):**
> *"Show me everything expiring in the next 14 days"*

Alex returns a prioritised list — RCA policies first (mandatory, fines for expiry), then CASCO, PAD, KFZ — with client contact details and draft renewal messages ready to send.

**New client intake (5 minutes instead of 45):**
> *"New client — Stefan Müller, Munich, needs KFZ and liability for his fleet of 3 vans"*

Alex searches the product database, compares Allianz DE, AXA, and HDI side by side, recommends the best option with clear reasoning, and generates a professional German-language offer document — ready to email.

**Mid-day check:**
> *"Any urgent RCA renewals I may have missed?"*

Alex cross-checks the portfolio and flags anything expiring within 7 days, including clients who have not responded to renewal notices.

---

### Employee B — Claims Handler

**New damage report (3 minutes instead of 20):**
> *"Maria Popescu had a parking accident today — rear bumper, CASCO with Generali Romania"*

Alex logs the claim, retrieves the policy details, provides the exact Generali claims hotline and online portal, lists the required documents, and gives the average processing time. All in one response.

**Status check:**
> *"What is the status of claim CLM-2842?"*

Alex retrieves everything: incident date, reported date, insurer claim reference, current status, and any notes logged by the team.

**Document processing (with Gemini Vision):**
Employee uploads a photo of a handwritten accident report (constatare amiabilă). Alex reads it, extracts the key fields — vehicle registration, damage description, third-party details — and logs them into the system automatically.

---

### Employee C — Compliance and Reporting

**End of month (10 minutes instead of 3 hours):**
> *"Generate the ASF report for February 2026"*

Alex produces a complete monthly report: policies intermediated by class, gross premiums by insurer, broker commissions, total portfolio overview — formatted for ASF submission under Law 236/2018.

> *"And the BaFin report for German business"*

Same for German-regulated contracts: product type, BaFin class codes, premium volumes in EUR, VVG and IDD compliance notes.

**Validity check:**
> *"Is the RCA for SC Logistic Trans SRL still valid?"*

Alex checks the policy, confirms validity status, days remaining, and flags immediately if expired — with the fine exposure under RAR regulations.

---

### All Employees — Cross-Team Capabilities

- **Multi-language:** Alex responds in English, German, or Romanian depending on how you address it
- **Product search:** Compare RCA, CASCO, PAD, CMR, KFZ, VIATA, Liability across all partner insurers simultaneously
- **Offer generation:** Professional offer documents in English, German, or Romanian — with your branding — in under 2 minutes
- **Client history:** Full profile view — all policies, all claims, all offers, renewal timeline — in a single query
- **Audit trail:** Every action logged with timestamp and employee session — supports compliance documentation requirements

---

## Technical Architecture

| Component | What It Does | Where It Runs |
|---|---|---|
| **Alex (Chainlit Web UI)** | Browser chat interface — no installation | Google Cloud (EU) |
| **Custom MCP Server** | 14 broker-specific tools, your data, your logic | Google Cloud (EU) |
| **PostgreSQL Database** | Clients, policies, claims, offers — your data only | Google Cloud (EU) |
| **Claude API (Anthropic)** | AI reasoning, language, decision-making | Anthropic (US/EU) |
| **Gemini Vision API (Google)** | OCR: scanned docs, accident photos, handwritten forms | Google Cloud (EU) |
| **Google Cloud Run** | Serverless hosting — scales to zero when not in use | europe-west3 (Frankfurt) |

**Data sovereignty:** All client data stays on your GCP instance in Frankfurt. Anthropic's API receives only anonymised, structured tool calls — no client names, policy numbers, or personal identifiers ever leave your server.

---

## Implementation: What You Are Paying For

### Phase 1 — Process Mapping and Discovery (Weeks 1–2) · €600

- One-on-one structured interviews with each team member
- Full documentation of current workflows: client intake, renewals, claims, reporting
- Gap analysis: where time is being lost, where compliance risk exists
- Delivery: workflow map document + integration specification
- Output used to customise every tool, prompt, and automation in Phase 2

### Phase 2 — Cloud Infrastructure and MCP Server Build (Weeks 2–4) · €1,200

- GCP project setup: Cloud Run, Cloud SQL (PostgreSQL), Secret Manager, IAM
- Custom domain configuration + SSL certificate
- Full deployment of the MCP server with all 14 broker tools:
  - Client management (search, create, full profile)
  - Product search and comparison (all partner insurers)
  - Offer generation (EN/DE/RO, your branding)
  - Renewals dashboard (urgency-sorted, draft letters)
  - Claims intake and status tracking (insurer-specific guidance)
  - Gemini Vision OCR pipeline (scanned policies, accident photos, handwritten forms)
  - ASF monthly report generator (Law 236/2018)
  - BaFin monthly report generator (VVG + IDD)
  - RCA validity checker
- Data migration: import your existing client and policy data
- Integration testing with your real documents and workflows

### Phase 3 — Customisation, Branding, and Employee Training (Weeks 5–6) · €900

- Alex customised with your brokerage name, partner insurers, commission structures
- Role-specific configuration per employee (claims handler, client broker, compliance)
- Live training sessions — each employee, in their preferred language (EN/DE/RO)
- Usage guides delivered in English and German
- Feedback round: adjustments based on real employee use

### Phase 4 — Go-Live, Handover, and First Month Support (Week 7) · €800

- Production go-live on GCP
- Monitoring setup: uptime alerts, error notifications, usage dashboard
- 30-day intensive support period: priority response, immediate fixes
- Runbook delivered: how to restart, update, add a new employee

**Total one-time implementation fee: €3,500**

*Payments: 50% on contract signing, 50% on go-live.*

---

## Monthly Managed Service

After go-live, you pay a monthly fee for the system to keep running, improving, and staying compliant.

### What Is Included Every Month

- GCP hosting management (Cloud Run, Cloud SQL, monitoring, backups)
- All software updates — new features, bug fixes, dependency patches
- Compliance template updates when ASF or BaFin guidance changes
- Employee support — questions answered within 1 business day
- Monthly usage report: tokens used, tools called, most common workflows
- New tool additions for simple requests (up to 2 hours/month included)
- 99.5% uptime SLA

### Monthly Tiers

| Tier | Employees | Hosting | Monthly Fee |
|---|---|---|---|
| **Starter** | 2–3 | GCP Cloud Run (Frankfurt) | **€490/month** |
| **Growth** | 4–6 | GCP Cloud Run + dedicated DB | **€690/month** |
| **Scale** | 7–15 | GCP Cloud Run + HA setup + priority support | **€990/month** |

**Additional employee beyond tier limit:** +€75/month each.

---

## AI API Costs — Your Account, Your Control

The AI models are billed directly to your API accounts. This keeps costs transparent, under your control, and independent of our service fee.

You need two accounts (both free to create):
- **Anthropic Console** — [console.anthropic.com](https://console.anthropic.com) — for Claude (the core AI)
- **Google AI Studio** — [aistudio.google.com](https://aistudio.google.com) — for Gemini Vision (OCR)

### Why API-Only (No Claude Team subscription needed)

You do not need a Claude Team subscription ($125/month for 5 seats). The Chainlit interface we built replaces the claude.ai web interface entirely. Your employees use Alex directly — no separate logins, no separate subscriptions.

| | Claude Team Plan | API-Only (Our Approach) |
|---|---|---|
| **Monthly cost** | $125/mo (5 seats minimum) | $0 subscription — pay per use |
| **Interface** | claude.ai web/desktop | Alex (Chainlit) — your branded tool |
| **Control** | Limited — Anthropic's UI | Full — your prompts, your tools, your data |
| **Branding** | "Claude" branding | "Alex" — your assistant |
| **Usage visibility** | None | Full dashboard — tokens, costs, tools |
| **Works with our system** | No (separate product) | Yes — this is what we built |

### Estimated Monthly API Costs

Usage scenario: 3 employees, ~50 queries/day, 22 working days

| Model | Best For | Estimated Cost/Month |
|---|---|---|
| **Claude Sonnet 4.5** ⭐ | All daily tasks — client search, offers, renewals, reports | **~€18–25/month** |
| **Claude Opus 4.5** | Complex document analysis, ambiguous queries | **~€90–110/month** |
| **Gemini 2.0 Flash** | OCR — scanned policies, accident photos, handwritten forms | **~€2–5/month** |

**Recommendation: Claude Sonnet 4.5 handles 95% of daily brokerage tasks at 1/5th the cost of Opus.** We configure the system to use Sonnet by default and escalate to Opus only when specifically needed.

### Total Monthly Cost Scenarios

| Scenario | Managed Service | AI APIs | **Total/Month** |
|---|---|---|---|
| **3 employees, Sonnet only** | €490 | ~€20 | **~€510/month** |
| **3 employees, Sonnet + Gemini Vision** | €490 | ~€25 | **~€515/month** |
| **5 employees, Sonnet + Gemini Vision** | €690 | ~€40 | **~€730/month** |
| **3 employees, Opus (heavy use)** | €490 | ~€100 | **~€590/month** |

*AI API costs are billed directly by Anthropic and Google to your accounts. The figures above are estimates based on typical brokerage usage patterns.*

---

## Security and Regulatory Compliance

### Data Architecture

- **Your data:** stored exclusively on your GCP Cloud SQL instance in Frankfurt (europe-west3)
- **API calls:** Claude receives anonymised, structured instructions only — e.g. "compare RCA products for vehicle category X" — never raw client records
- **Gemini Vision:** document images processed in-memory, not stored by Google beyond the API call
- **Access control:** each employee has an individual login, sessions are isolated and logged
- **Backups:** automated daily backups with 30-day retention on GCP

### Regulatory Coverage

| Framework | How Alex Supports It |
|---|---|
| **GDPR Article 6** | Lawful basis documented, EU data residency, access controls, audit logs |
| **ASF Law 236/2018 (RO)** | Monthly report generator, broker workflow documentation, policy class mapping |
| **BaFin VVG + IDD 2016/97/EU (DE)** | Advice documentation trail, disclosure support, German product class codes |
| **RAR (RO vehicle authority)** | RCA validity checker with fine exposure alerts |

Compliance templates are updated at no extra charge when regulatory guidance changes.

---

## Investment Summary

| Item | Cost |
|---|---|
| **Implementation (one-time)** | **€3,500** |
| Phase 1 — Process Mapping | €600 |
| Phase 2 — Cloud Build + MCP Server | €1,200 |
| Phase 3 — Customisation + Training | €900 |
| Phase 4 — Go-Live + First Month Support | €800 |
| | |
| **Managed Service (monthly)** | **from €490/month** |
| **AI API costs (your accounts)** | **~€20–45/month** typical |
| | |
| **Typical first-year total cost** | **~€9,540** |
| *(€3,500 setup + €490×12 + €25×12 APIs)* | |

For comparison: one junior administrative employee in Germany costs €30,000–€40,000 per year in salary alone, before social contributions, equipment, and management overhead.

---

## Next Steps

1. **Review this proposal** — We are available for a call in English, German, or Romanian to answer any questions.
2. **Schedule a live demo** — See Alex running with real insurance scenarios. No commitment required. The demo environment is live today.
3. **Discovery call (1 hour)** — We map your current workflows and confirm which tools to prioritise in Phase 2.
4. **Sign and start** — 50% of the implementation fee on contract signing. Phase 1 begins immediately.

---

*This document is confidential and prepared exclusively for the named recipient.*
*All pricing is valid for 30 days from the document date. Prices exclude applicable VAT.*
*AI API cost estimates are based on typical usage and may vary. Actual costs billed directly by Anthropic and Google.*

---

**Document Reference:** OFFER-2026-INS-EN-002
**Valid Until:** April 7, 2026
