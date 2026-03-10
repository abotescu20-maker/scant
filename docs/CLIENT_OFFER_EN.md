# Business Proposal: Alex — AI Agent System for Insurance Brokerage Operations

**Prepared for:** Insurance Brokerage Client (Germany / Romania)
**Prepared by:** Managed Service Provider — AI Systems & Automation
**Date:** March 2026
**Document Reference:** OFFER-2026-INS-EN-003
**Valid Until:** TBD

---

## Executive Summary

We propose deploying **Alex**, a fully custom AI agent system built specifically for your insurance brokerage, operating under BaFin (Germany) and ASF (Romania) regulatory frameworks.

Alex is already built and running. A live demo is available today.

This proposal covers everything: the initial build and cloud setup, employee training, and ongoing managed operation. You pay once to get started, then a predictable monthly fee for the system to keep running and improving.

| | |
|---|---|
| **One-time implementation fee** | **TBD** |
| **Monthly managed service** | **TBD** |
| **AI API costs (your account)** | **TBD** |
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

**Document processing (with Vision AI):**
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
- **Desktop automation:** Alex can control local desktop applications and intranet systems via the local agent
- **Web automation:** Alex can browse websites, verify RCA online, extract data from insurer portals

---

## Technical Architecture

| Component | What It Does | Where It Runs |
|---|---|---|
| **Alex (Chainlit Web UI)** | Browser chat interface — no installation | Google Cloud (EU) |
| **24 Broker Tools** | Client, policy, offer, claims, compliance, web, desktop | Google Cloud (EU) |
| **PostgreSQL Database** | Clients, policies, claims, offers — your data only | Google Cloud (EU) |
| **Claude Sonnet (Anthropic)** | AI reasoning, language, decision-making | Anthropic API |
| **Vision AI** | OCR: scanned docs, accident photos, handwritten forms | Google Cloud (EU) |
| **Google Cloud Run** | Serverless hosting — scales automatically | europe-west3 (Frankfurt) |
| **Local Agent** | Desktop & intranet automation on employee machines | Employee computer |

**Data sovereignty:** All client data stays on your GCP instance in Frankfurt. The AI API receives only anonymised, structured tool calls — no client names, policy numbers, or personal identifiers ever leave your server.

---

## Implementation: What You Are Paying For

### Phase 1 — Process Mapping and Discovery (Weeks 1–2) · TBD

- One-on-one structured interviews with each team member
- Full documentation of current workflows: client intake, renewals, claims, reporting
- Gap analysis: where time is being lost, where compliance risk exists
- Delivery: workflow map document + integration specification
- Output used to customise every tool, prompt, and automation in Phase 2

### Phase 2 — Cloud Infrastructure and Build (Weeks 2–4) · TBD

- GCP project setup: Cloud Run, Cloud SQL (PostgreSQL), Secret Manager, IAM
- Custom domain configuration + SSL certificate
- Full deployment with all 24 broker tools:
  - Client management (search, create, update, delete, full profile)
  - Product search and comparison (all partner insurers)
  - Offer generation (EN/DE/RO, your branding)
  - Renewals dashboard (urgency-sorted, draft letters)
  - Claims intake and status tracking (insurer-specific guidance)
  - Vision AI OCR pipeline (scanned policies, accident photos, handwritten forms)
  - ASF monthly report generator (Law 236/2018)
  - BaFin monthly report generator (VVG + IDD)
  - RCA validity checker
  - Web automation (browser-based tasks)
  - Desktop automation (local apps, intranet)
- Data migration: import your existing client and policy data
- Integration testing with your real documents and workflows

### Phase 3 — Customisation, Branding, and Employee Training (Weeks 5–6) · TBD

- Alex customised with your brokerage name, partner insurers, commission structures
- Role-specific configuration per employee (claims handler, client broker, compliance)
- Live training sessions — each employee, in their preferred language (EN/DE/RO)
- Usage guides delivered in English and German
- Feedback round: adjustments based on real employee use

### Phase 4 — Go-Live, Handover, and First Month Support (Week 7) · TBD

- Production go-live on GCP
- Monitoring setup: uptime alerts, error notifications, usage dashboard
- 30-day intensive support period: priority response, immediate fixes
- Runbook delivered: how to restart, update, add a new employee

**Total one-time implementation fee: TBD**

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

| Tier | Employees | Monthly Fee |
|---|---|---|
| **Starter** | 2–3 | TBD |
| **Growth** | 4–6 | TBD |
| **Scale** | 7–15 | TBD |

**Additional employee beyond tier limit:** TBD.

---

## AI API Costs — Your Account, Your Control

The AI models are billed directly to your API accounts. This keeps costs transparent, under your control, and independent of our service fee.

You need one account (free to create):
- **Anthropic Console** — [console.anthropic.com](https://console.anthropic.com) — for Claude Sonnet (the core AI)

### Why API-Only (No Claude Team subscription needed)

You do not need a Claude Team subscription. The Chainlit interface we built replaces the claude.ai web interface entirely. Your employees use Alex directly — no separate logins, no separate subscriptions.

| | Claude Team Plan | API-Only (Our Approach) |
|---|---|---|
| **Monthly cost** | Fixed per seat | Pay per use — scales with actual usage |
| **Interface** | claude.ai web/desktop | Alex (Chainlit) — your branded tool |
| **Control** | Limited — Anthropic's UI | Full — your prompts, your tools, your data |
| **Branding** | "Claude" branding | "Alex" — your assistant |
| **Usage visibility** | None | Full dashboard — tokens, costs, tools |
| **Works with our system** | No (separate product) | Yes — this is what we built |

### Estimated Monthly AI API Costs

Costs depend on usage volume and are billed directly by Anthropic. Estimates available on request.

---

## Security and Regulatory Compliance

### Data Architecture

- **Your data:** stored exclusively on your GCP Cloud SQL instance in Frankfurt (europe-west3)
- **API calls:** Claude receives anonymised, structured instructions only — e.g. "compare RCA products for vehicle category X" — never raw client records
- **Vision AI:** document images processed in-memory, not stored beyond the API call
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
| **Implementation (one-time)** | **TBD** |
| Phase 1 — Process Mapping | TBD |
| Phase 2 — Cloud Build | TBD |
| Phase 3 — Customisation + Training | TBD |
| Phase 4 — Go-Live + First Month Support | TBD |
| | |
| **Managed Service (monthly)** | **TBD** |
| **AI API costs (your accounts)** | **TBD** |

---

## Next Steps

1. **Review this proposal** — We are available for a call in English, German, or Romanian to answer any questions.
2. **Schedule a live demo** — See Alex running with real insurance scenarios. No commitment required. The demo environment is live today.
3. **Discovery call (1 hour)** — We map your current workflows and confirm which tools to prioritise in Phase 2.
4. **Sign and start** — 50% of the implementation fee on contract signing. Phase 1 begins immediately.

---

*This document is confidential and prepared exclusively for the named recipient.*
*All pricing is valid for 30 days from the document date. Prices exclude applicable VAT.*
*AI API cost estimates are based on typical usage and may vary. Actual costs billed directly by Anthropic.*

---

**Document Reference:** OFFER-2026-INS-EN-003
**Valid Until:** TBD
