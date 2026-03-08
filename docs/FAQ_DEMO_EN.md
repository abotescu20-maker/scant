# Alex — Insurance Broker AI
## Complete Demo & FAQ Guide
### For Sales Presentations & Client Onboarding

---

> **Platform:** Claude Cowork + Claude Remote Control — a fully agentic AI platform
> **Deployed:** GCP Cloud Run, europe-west3 (Frankfurt) — GDPR compliant
> **AI Engine:** Google Gemini 2.5 Pro
> **Live URL:** https://insurance-broker-alex-603810013022.europe-west3.run.app

---

## PART 1 — COMMERCIAL PROPOSITION

### Why Alex vs. ClawdBot?

We offer you **Claude Cowork + Claude Remote Control** — a custom agentic platform built on your specific brokerage workflows. It does everything ClawdBot promises, and more:

| Capability | ClawdBot | Alex (Ours) |
|---|---|---|
| AI Base | Generic | Gemini 2.5 Pro — most capable |
| Enterprise Security | ❓ Unknown | ✅ Isolated, data stays with you |
| Process Customization | Limited | MCP Server custom on your workflows |
| Skills per Employee | No | Each employee = own configuration |
| Access Control | Basic | Granular, per role, per tool |
| Real Automation | Partial | Agentic end-to-end |
| **PDF/Document Scan** | ❌ No | ✅ Gemini Vision — any document |
| **Accident Photo Analysis** | ❌ No | ✅ Damage assessment in seconds |
| **Handwritten Forms** | ❌ No | ✅ Constatare amiabilă, etc. |
| **Regulatory Reports** | ❌ No | ✅ ASF + BaFin automated |
| **Multi-language** | ❌ No | ✅ EN / RO / DE natively |
| **Export: PDF/XLSX/DOCX** | ❌ No | ✅ All formats |

---

### Our Delivery Phases

**Phase 1 — Mapping & Discovery (Weeks 1–2)**
We map your processes: policy issuance, renewal, claims management, regulatory reporting, client communication. We identify where AI delivers immediate value.

**Phase 2 — Custom MCP Server (Weeks 3–5)**
We build a dedicated MCP server for your company — connected to your existing systems (CRM, policy databases, email, documents). The agent sees what it needs, nothing more.

**Phase 3 — Custom Skills (Weeks 4–6)**
We generate skills specific to your domain:
- 🔍 Claims File Analyst
- 📋 Offer & Policy Generator
- 📞 Client Communication Assistant
- 📊 Reporting & Compliance
- 🔄 Contract Renewal Automation

**Phase 4 — Individual Training & Onboarding (Weeks 6–8)**
Each employee is trained and the platform configured personally. Not generic training — 1:1 sessions based on their specific role.

---

### Skills Available Today ("Out of the Box")

✅ **MCP Server Generators** (Python/TypeScript) — 5K+ installs
✅ **Insurance Analyst Skill** — dedicated to insurance analysis
✅ **Billing Automation** — invoice & policy automation
✅ **Compliance Automation** — regulatory reporting
✅ **Process Mapping** — operational workflow mapping
✅ **Agentic Workflow** — complex workflow orchestration
✅ **Business Analysis Orchestration** — process analysis
✅ **Onboarding Guide Creator** — personalized guides per employee
✅ **Commercial Proposal Writer** — commercial offers
✅ **Agent Workflow Builder** — agentic flow construction

### Custom Skills We Build For You

🔧 **Insurance Broker MCP Skill** — integrated with your specific systems
🔧 **Policy Management Agent** — issuance, modification, renewal
🔧 **Claims Processing Assistant** — full claims file assistance
🔧 **Client Communication Agent** — personalized email/message drafts
🔧 **Regulatory Reporting Skill** — ASF / BaFin automated reporting

---

## PART 2 — WHAT ALEX CAN DO TODAY (LIVE DEMO)

### System Architecture

```
Browser / Employee Device
        ↓  HTTPS
GCP Cloud Run (europe-west3 Frankfurt)
    ├── Chainlit 2.10.0 — Chat Interface
    ├── Google Gemini 2.5 Pro — AI Engine
    ├── 14 Broker Tools — connected to your data
    └── SQLite DB — clients, policies, offers, claims
```

**Data flow security:**
- All data stays on GCP europe-west3 (Frankfurt)
- GDPR Article 6 compliant — data processing agreement available
- No client personal data sent outside the EU
- API calls encrypted TLS 1.3

---

## PART 3 — DEMO SYNTHETIC DATA

### 6 Demo Clients (pre-loaded in system)

| ID | Name | Type | Country | Email |
|---|---|---|---|---|
| CLI001 | Andrei Ionescu | Individual | 🇷🇴 RO | andrei.ionescu@gmail.com |
| CLI002 | SC Logistic Trans SRL | Company | 🇷🇴 RO | office@logistictrans.ro |
| CLI003 | Maria Popescu | Individual | 🇷🇴 RO | maria.popescu@yahoo.com |
| CLI004 | Johann Schmidt | Individual | 🇩🇪 DE | j.schmidt@firma-schmidt.de |
| CLI005 | Ion Gheorghe | Individual | 🇷🇴 RO | ion.gheorghe@hotmail.com |
| CLI006 | Immobilien GmbH Müller | Company | 🇩🇪 DE | info@mueller-immobilien.de |

### 8 Active Policies

| Policy | Client | Type | Insurer | Premium | Expires |
|---|---|---|---|---|---|
| RCA-GEN-2025-001234 | Andrei Ionescu | RCA | Generali Romania | 1,792 RON | 14 Mar 2026 |
| CASCO-ALZ-2025-056789 | Andrei Ionescu | CASCO | Allianz-Tiriac | 8,430 RON | 14 Mar 2026 |
| RCA-OMA-2026-009901 | SC Logistic Trans | RCA (Fleet) | Omniasig | 18,400 RON | **10 Mar 2026** ⚠️ |
| CMR-GEN-2025-003344 | SC Logistic Trans | CMR | Generali Romania | 12,600 RON | 31 May 2026 |
| CASCO-ALZ-2024-112233 | Maria Popescu | CASCO | Allianz-Tiriac | 5,200 RON | 14 Jun 2026 |
| PAD-2025-456789 | Maria Popescu | PAD | Pool PAD Romania | 100 RON | 11 Mar 2026 |
| KFZ-ALZ-DE-2025-998877 | Johann Schmidt | KFZ (🇩🇪) | Allianz Deutschland | 1,250 EUR | 30 Sep 2026 |
| CASCO-OMA-2025-778899 | Ion Gheorghe | CASCO | Omniasig | 7,890 RON | **24 Mar 2026** ⚠️ |

> ⚠️ **Urgent renewals for demo:** SC Logistic Trans RCA expires 10 Mar, Ion Gheorghe CASCO expires 24 Mar

### 10 Insurance Products (searchable by AI)

| Product | Insurer | Type | Premium | Rating |
|---|---|---|---|---|
| PROD_RCA_ALZ | Allianz-Tiriac | RCA | 1,847 RON | AA |
| PROD_RCA_GEN | Generali Romania | RCA | 1,792 RON | AA |
| PROD_RCA_OMA | Omniasig | RCA | 1,934 RON | A+ |
| PROD_CASCO_ALZ | Allianz-Tiriac | CASCO | 8,430 RON | AA |
| PROD_CASCO_GEN | Generali Romania | CASCO | 7,890 RON | AA |
| PROD_CASCO_OMA | Omniasig | CASCO | 8,120 RON | A+ |
| PROD_PAD_OMA | Omniasig | PAD | 100 RON | A+ |
| PROD_CMR_GEN | Generali Romania | CMR | 1,800 EUR | AA |
| PROD_KFZ_ALZ_DE | Allianz Deutschland | KFZ 🇩🇪 | 1,250 EUR | AA |
| PROD_KFZ_AXA_DE | AXA Versicherung | KFZ 🇩🇪 | 1,180 EUR | AA |

### 1 Active Claim

| Claim | Client | Policy | Date | Status | Estimate |
|---|---|---|---|---|---|
| CLME7C01D | SC Logistic Trans | CASCO | 08 Mar 2026 | 🟡 Open | 2,800 RON |

---

## PART 4 — 14 AI TOOLS (WHAT ALEX CAN DO)

### 1. Client Management

**`broker_search_clients`** — Search by name, phone, or email
*Demo:* `"Find Andrei Ionescu"` → returns full profile with policies

**`broker_get_client`** — Full client profile with all active policies
*Demo:* `"Show me CLI002"` → Logistic Trans with 2 policies, 1 claim

**`broker_create_client`** — Add new client to database
*Demo:* `"Create a new client: Mihai Dumitrescu, phone 0745 000 111, RCA needed"`

---

### 2. Policy Management

**`broker_list_policies`** — List by client or portfolio-wide
*Demo:* `"Show all active policies"` → 8 policies with status

**`broker_get_renewals_due`** — Expiring policies with urgency flags
*Demo:* `"What expires in the next 30 days?"` → 🔴 SC Logistic Trans (2 days!), Ion Gheorghe (16 days)

**`broker_check_rca_validity`** — Instant RCA validity check
*Demo:* `"Check RCA validity for Maria Popescu"` → status + expiry

---

### 3. Products & Offers

**`broker_search_products`** — Search products by type and country
*Demo:* `"Search RCA products in Romania"` → 3 insurers compared

**`broker_compare_products`** — Side-by-side comparison table
*Demo:* `"Compare PROD_RCA_ALZ, PROD_RCA_GEN, PROD_RCA_OMA"` → recommendation

**`broker_create_offer`** — Generate professional offer document
*Demo:* `"Create an offer for CLI001 with RCA and CASCO in English"` → downloadable `.txt` file

**`broker_list_offers`** — List all generated offers
*Demo:* `"Show me all sent offers"` → 3 offers generated today

---

### 4. Claims Processing

**`broker_log_claim`** — Register new damage claim
*Demo:* `"Log a claim for CLI001 on POL001, accident yesterday, broken windshield, estimate 1200 RON"`

**`broker_get_claim_status`** — Check claim status + insurer guidance
*Demo:* `"What's the status of CLME7C01D?"` → Generali Romania contact, portal link, avg 15 days

---

### 5. Regulatory Compliance

**`broker_asf_summary`** — Monthly ASF report (Romania — Law 236/2018)
*Demo:* `"Generate ASF report for February 2026"` → policy counts by type, premiums by ASF codes (A10=RCA, A3=CASCO)

**`broker_bafin_summary`** — Monthly BaFin report (Germany — VVG/IDD)
*Demo:* `"Generate BaFin report for February 2026"` → German classification (Kraftfahrzeughaftpflicht, etc.)

---

### COMING IN SPRINT 1 (next update)

**`broker_send_offer_email`** — Send offer directly to client email from chat
**`broker_analyze_document`** — Upload PDF/image → Gemini Vision extracts data automatically
**Admin Panel** — `/admin` with login, user management, tool permissions, audit log
**Export** — Download offers as PDF, XLSX, or DOCX

---

## PART 5 — DEMO SCRIPTS (Copy & Paste into Alex)

### Script 1: Morning Renewals Check (30 sec)
```
Show me all policies expiring in the next 30 days
```
→ Alex shows urgency table with 🔴🟡 flags

```
Which clients need to be called today?
```
→ Alex prioritizes SC Logistic Trans and Ion Gheorghe

---

### Script 2: Full Client Workflow (2 min)
```
Find client Andrei Ionescu
```
→ Profile loads with 2 active policies

```
Search RCA products for Romania and compare all options
```
→ 3-way comparison: Allianz vs Generali vs Omniasig

```
Create an offer for CLI001 with the cheapest RCA option
```
→ Professional offer generated, downloadable file attached

---

### Script 3: Claims Processing (1 min)
```
Maria Popescu had a parking accident this morning. Her car is a Dacia Logan.
The other driver hit her rear bumper. Damage estimate around 800 RON.
Log the claim on her CASCO policy.
```
→ Alex finds the client, finds CASCO-ALZ-2024-112233, creates claim, gives Allianz contact + portal

---

### Script 4: German Client — BaFin Compliant (1 min)
```
Show me Johann Schmidt's profile and his KFZ policy details
```
→ German client with Allianz Deutschland, 1,250 EUR/year

```
Generate BaFin report for January 2026
```
→ German-format regulatory report with Kraftfahrzeughaftpflicht classification

---

### Script 5: Compliance Report (30 sec)
```
Generate the ASF monthly summary for February 2026
```
→ Full ASF report: total active policies, premiums, ASF class breakdown

---

### Script 6: New Client Registration (1 min)
```
I have a new client: Cristina Avram, phone 0742 555 888,
email cristina@gmail.com, lives in Bucharest, needs RCA for her car.
Create her profile and search RCA options.
```
→ Client created with ID, then instant product search

---

## PART 6 — FAQ FOR PROSPECTS

### Q1: What is Alex exactly?
Alex is an AI assistant built specifically for insurance brokerage operations. It connects directly to your client database, policy records, and insurer product catalog. It can search, compare, generate offers, log claims, and produce regulatory reports — all in a natural conversation, in English, Romanian, or German.

### Q2: How does Alex protect our client data? (GDPR)
- Your data is stored exclusively on GCP servers in Frankfurt (europe-west3)
- Data never leaves the EU
- GDPR Article 6 compliant — lawful basis for processing
- We sign a Data Processing Agreement (DPA) as data processor
- You remain the data controller
- Personal data (CNP, ID numbers) are never displayed in chat responses
- Full audit log of who accessed what, when

### Q3: Can Alex make mistakes?
Yes, like any AI. That's why:
- All offers and reports require human review before sending to clients
- Claims are logged but a broker must verify before submitting to insurer
- Regulatory reports (ASF/BaFin) are drafts — your compliance officer approves
- Alex explicitly marks its outputs as AI-generated and recommends verification
- The system is a decision support tool, not an autonomous decision maker

### Q4: How does PDF/photo processing work?
When a broker uploads a file (scan, photo, PDF):
1. Gemini Vision reads the document natively — no OCR library needed
2. Extracts structured data: names, dates, amounts, policy numbers
3. Presents extracted data to the broker for verification
4. Offers to pre-fill the corresponding form (new client, new claim, etc.)

Supported: JPG, PNG, PDF (including scanned/handwritten), WEBP

### Q5: What languages does Alex support?
- **English** — default for all operations
- **Romanian** — for RO clients, ASF reports, local documents
- **German** — for DE clients (BaFin), KFZ products, German forms

Switch languages mid-conversation: *"Generează oferta în română pentru CLI001"*

### Q6: What are the pricing tiers?

| Tier | Users | Monthly Fee | Includes |
|---|---|---|---|
| **Starter** | 1–3 | €490/month | Alex chat, 14 tools, email support |
| **Growth** | 4–6 | €890/month | + admin panel, user permissions, audit log |
| **Scale** | 7–15 | €1,490/month | + custom skills, priority support, SLA |

One-time setup fee: **€3,500** (includes deployment, data migration, employee onboarding)

API costs (Gemini): ~€5–25/month, included in all tiers

### Q7: Can it connect to our existing CRM or AMS?
In Phase 2, we build custom connectors. We have built integrations with:
- REST APIs (any CRM with API access)
- Excel/CSV imports
- Email (IMAP/SMTP)
- SharePoint / Google Drive document access
- Direct database connections (PostgreSQL, MySQL, MSSQL)

Standard CRM integrations available: Salesforce, HubSpot, Zoho CRM

### Q8: What insurers are supported?
**Romania (RO):**
- Allianz-Tiriac Asigurări
- Generali Romania
- Omniasig Vienna Insurance Group
- Pool PAD Romania

**Germany (DE):**
- Allianz Deutschland
- AXA Versicherung

More insurers added in your specific deployment based on your partner agreements.

### Q9: How are ASF/BaFin reports generated?
- **ASF (Romania):** Automated mapping per Law 236/2018. Policy types mapped to ASF class codes (A10=RCA, A3=CASCO/KASKO, A8=PAD, A15=CMR). Monthly totals, premium aggregates, regulatory format.
- **BaFin (Germany):** Per VVG (Versicherungsvertragsgesetz) + IDD (Insurance Distribution Directive). German class mapping (Kraftfahrzeughaftpflicht, Kaskoversicherung, etc.). Outputs in IDD-compliant format.

Reports are drafts — your compliance officer reviews and submits officially.

### Q10: What happens if the Gemini API goes down?
- Alex displays a clear error message in the chat
- The Chainlit interface remains accessible
- All previously generated documents remain available
- No data is lost
- Average Gemini uptime: 99.9% (Google SLA)
- Our monitoring alerts within 5 minutes of any outage

### Q11: Can different employees have different access levels?
Yes — the Admin Panel (in Sprint 1 release) provides:
- **Superadmin (MSP):** full access, creates companies and users
- **Company Admin:** manages their company's users and permissions
- **Broker (Agent):** access only to tools their manager enables

Example: Trainee brokers can search clients and view policies, but cannot create offers or log claims until approved.

### Q12: What does the export feature produce?
From any offer or report Alex generates, you can download:
- **PDF** — professional format with broker logo, ready to send to clients
- **XLSX** — for further analysis in Excel, portfolio management
- **DOCX** — editable Word document for customization before sending

---

## PART 7 — TECHNICAL STACK

| Component | Technology | Version |
|---|---|---|
| Chat Interface | Chainlit | 2.10.0 |
| AI Engine | Google Gemini 2.5 Pro | Latest (Mar 2026) |
| AI SDK | google-genai | 1.54.0 |
| Backend | Python | 3.12 |
| Database | SQLite (dev) → PostgreSQL (prod) | — |
| Deployment | GCP Cloud Run | europe-west3 |
| Container | Docker | — |
| File Upload | Chainlit native (max 500MB, 20 files) | — |
| MCP Server | FastMCP | 2.14.5 |

---

## PART 8 — CONTACT & NEXT STEPS

**Interested in a live demo?**

1. Visit the demo: https://insurance-broker-alex-603810013022.europe-west3.run.app
2. Try the demo scripts from Part 5
3. Schedule a 1:1 session: we walk through your specific workflows
4. We prepare a custom offer within 48 hours

**For questions about GDPR, data residency, or custom integrations:**
Contact us directly — we provide full technical documentation and sign NDAs before any deep-dive.

---

*Alex — Insurance Broker AI | Powered by Google Gemini 2.5 Pro | GCP Frankfurt (EU) | ASF & BaFin Compliant*
*Document version: 1.0 | Date: March 2026*
