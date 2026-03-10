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

This is not an off-the-shelf product. We built a functional agentic platform based on our research into insurance brokerage workflows, and we deploy it as a starting point — then shape it together with your team into the exact tool your employees need.

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
| **Local Agent** | Desktop & intranet automation on employee machines | Employee computer |

**Data sovereignty:** All client data stays on your GCP instance in the EU. The AI API receives only anonymised, structured tool calls — no client names, policy numbers, or personal identifiers ever leave your server.

---

## How We Work Together — Two Phases

### Phase 1 — MVP: Agentic Platform Already Running

We have built a fully functional agentic platform based on our research into insurance brokerage workflows. This is the starting point — not the final product.

**What is already built and running today:**
- Chainlit browser chat interface — no installation for employees
- Claude Sonnet (Anthropic) as the AI engine
- 24 broker tools: client management, product search and comparison, offer generation, renewals dashboard, claims intake and tracking, ASF/BaFin compliance reports, Vision AI for document processing, web automation, desktop automation
- Provisional MCP server with synthetic demo data (6 clients, 10 products, 8 policies)
- Admin panel with role-based access control (RBAC) per employee
- Local agent for desktop and intranet automation
- Deployed on Google Cloud Run (Frankfurt, GDPR compliant)

**The purpose of Phase 1:**
We test and build together with your employees. They validate what is useful, what is missing, and what needs to be adjusted. The MVP is the foundation — not the ceiling.

---

### Phase 2 — Full Implementation: Built Around Your Real Workflows

After validating the MVP with your internal test team, we build the production system from the ground up — on your real processes, not on our assumptions.

**What Phase 2 includes:**

- **Process mapping with your team** — structured sessions with each employee, documenting every workflow: client intake, renewals, claims, reporting, communication
- **Dedicated MCP server** built on the real process map — connected to your actual systems: CRM, policy databases, email, insurer portals
- **Custom skills per role** — each employee's Alex is configured around their specific tasks and responsibilities
- **Real data migration** — all your clients, policies, products, and prices imported and configured by your team
- **Individual training** — each employee trained on their own workflows with real data
- **Migration to a dedicated VM on Google Cloud** — from Cloud Run (prototyping) to a dedicated, secured VM with persistent database, constant performance, and predictable cost

**The result:** An AI system that matches your actual operation — not a generic tool adapted to fit.

---

## Monthly Managed Service

After go-live, you pay a monthly fee for the system to keep running, improving, and staying compliant.

### What Is Included Every Month

- Cloud hosting management (VM, database, monitoring, backups)
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

The AI model is billed directly to your Anthropic API account. This keeps costs transparent, under your control, and independent of our service fee.

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

### AI API Costs

Costs depend on usage volume and are billed directly by Anthropic. Estimates available on request.

---

## Security and Regulatory Compliance

### Data Architecture

- **Your data:** stored exclusively on your GCP instance in the EU
- **API calls:** Claude receives anonymised, structured instructions only — e.g. "compare RCA products for vehicle category X" — never raw client records
- **Vision AI:** document images processed in-memory, not stored beyond the API call
- **Access control:** each employee has an individual login, sessions are isolated and logged
- **Backups:** automated daily backups with 30-day retention

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
| Phase 1 — MVP deployment and onboarding | TBD |
| Phase 2 — Process mapping, dedicated build, VM migration | TBD |
| | |
| **Managed Service (monthly)** | **TBD** |
| **AI API costs (your account)** | **TBD** |

---

## Next Steps

1. **Schedule a live demo** — See Alex running with real insurance scenarios. No commitment required. The demo environment is live today.
2. **Discovery call (1 hour)** — We walk through your current workflows and identify where Phase 2 customisation will have the most impact.
3. **MVP pilot** — Your employees use Alex on demo data, give feedback, validate which tools matter most.
4. **Phase 2 kick-off** — Process mapping begins. We build the production system around your real workflows.

---

*This document is confidential and prepared exclusively for the named recipient.*
*Pricing is indicative and subject to final scope confirmation. Prices exclude applicable VAT.*
*AI API costs vary by usage and are billed directly by Anthropic.*

---

**Document Reference:** OFFER-2026-INS-EN-003
**Valid Until:** TBD
