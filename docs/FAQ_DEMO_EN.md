# Alex — Insurance Broker AI
## Complete Demo & FAQ Guide
### For Sales Presentations & Client Onboarding

---

> **Platform:** Custom AI Agent built on Anthropic Claude Sonnet
> **Current phase:** MVP — running on GCP Cloud Run (Frankfurt) — GDPR compliant
> **Final deployment:** VM (Hetzner Frankfurt or equivalent) — planned post-MVP
> **Live Demo URL:** https://insurance-broker-alex-elo6xae6nq-ey.a.run.app

---

## PART 1 — COMMERCIAL PROPOSITION

### What Makes Alex Different

Alex is not a generic AI assistant. It is a structured AI agent built specifically around insurance brokerage workflows — connected directly to your client database, product catalog, and policy registry.

| Capability | Generic AI Chatbot | Alex (Ours) |
|---|---|---|
| AI Base | Generic | Claude Sonnet — built for structured workflows |
| Your Data | ❌ No access | ✅ Connected to your clients, policies, products |
| Process Customization | ❌ None | ✅ 24 tools built on your specific workflows |
| Skills per Employee | ❌ No | ✅ Role-based configuration per employee |
| Access Control | ❌ None | ✅ Granular, per role, per tool |
| Desktop Automation | ❌ No | ✅ Controls local apps via local agent |
| **PDF/Document Scan** | ❌ No | ✅ Vision AI — any document |
| **Accident Photo Analysis** | ❌ No | ✅ Damage assessment in seconds |
| **Handwritten Forms** | ❌ No | ✅ Constatare amiabilă, etc. |
| **Regulatory Reports** | ❌ No | ✅ ASF + BaFin automated |
| **Multi-language** | Partial | ✅ EN / RO / DE natively |

---

### Our Delivery Phases

**Phase 1 — Mapping & Discovery (Weeks 1–2)**
We map your processes: policy issuance, renewal, claims management, regulatory reporting, client communication. We identify where AI delivers immediate value.

**Phase 2 — Cloud Infrastructure & Build (Weeks 2–4)**
We deploy Alex on GCP Cloud Run with all 24 broker tools connected to your data. Full integration testing on your real workflows.

**Phase 3 — Customisation & Training (Weeks 5–6)**
Alex configured with your brokerage name, your partner insurers, your commission structures. Individual training per employee in their language.

**Phase 4 — Go-Live & Handover (Week 7)**
Production go-live. 30-day priority support. Monitoring setup. Runbook delivered.

**Post go-live — VM Migration**
After MVP validation on Cloud Run, the system migrates to a dedicated VM (Hetzner Frankfurt or equivalent) for better cost control and performance at scale.

---

## PART 2 — WHAT ALEX CAN DO TODAY (LIVE DEMO)

### System Architecture

```
Browser / Employee Device
        ↓  HTTPS
GCP Cloud Run (europe-west3 Frankfurt) [MVP]
→ VM Hetzner Frankfurt [Production]
    ├── Chainlit — Chat Interface
    ├── Claude Sonnet (Anthropic) — AI Engine
    ├── 24 Broker Tools — connected to your data
    ├── Admin Panel — user & permission management
    ├── REST API — n8n / external automation
    └── SQLite DB (dev) → PostgreSQL (prod)
         ↑
    Local Agent (employee computer)
    ├── Desktop automation (TextEdit, Word, Excel, etc.)
    ├── Intranet / VPN access
    └── Browser automation (RCA portals, insurer sites)
```

**Data flow security:**
- All data stays on GCP europe-west3 (Frankfurt) — GDPR Article 6 compliant
- No client personal data sent outside the EU
- API calls encrypted TLS 1.3
- Claude API receives only anonymised, structured tool calls — never raw client records

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

| Policy | Client | Type | Insurer | Expires |
|---|---|---|---|---|
| RCA-GEN-2025-001234 | Andrei Ionescu | RCA | Generali Romania | 14 Mar 2026 |
| CASCO-ALZ-2025-056789 | Andrei Ionescu | CASCO | Allianz-Tiriac | 14 Mar 2026 |
| RCA-OMA-2026-009901 | SC Logistic Trans | RCA (Fleet) | Omniasig | **10 Mar 2026** ⚠️ |
| CMR-GEN-2025-003344 | SC Logistic Trans | CMR | Generali Romania | 31 May 2026 |
| CASCO-ALZ-2024-112233 | Maria Popescu | CASCO | Allianz-Tiriac | 14 Jun 2026 |
| PAD-2025-456789 | Maria Popescu | PAD | Pool PAD Romania | 11 Mar 2026 |
| KFZ-ALZ-DE-2025-998877 | Johann Schmidt | KFZ 🇩🇪 | Allianz Deutschland | 30 Sep 2026 |
| CASCO-OMA-2025-778899 | Ion Gheorghe | CASCO | Omniasig | **24 Mar 2026** ⚠️ |

> ⚠️ **Urgent renewals for demo:** SC Logistic Trans RCA expires 10 Mar, Ion Gheorghe CASCO expires 24 Mar

### 10 Insurance Products (searchable by AI)

| Product | Insurer | Type | Rating |
|---|---|---|---|
| PROD_RCA_ALZ | Allianz-Tiriac | RCA | AA |
| PROD_RCA_GEN | Generali Romania | RCA | AA |
| PROD_RCA_OMA | Omniasig | RCA | A+ |
| PROD_CASCO_ALZ | Allianz-Tiriac | CASCO | AA |
| PROD_CASCO_GEN | Generali Romania | CASCO | AA |
| PROD_CASCO_OMA | Omniasig | CASCO | A+ |
| PROD_PAD_OMA | Omniasig | PAD | A+ |
| PROD_CMR_GEN | Generali Romania | CMR | AA |
| PROD_KFZ_ALZ_DE | Allianz Deutschland | KFZ 🇩🇪 | AA |
| PROD_KFZ_AXA_DE | AXA Versicherung | KFZ 🇩🇪 | AA |

> **Note:** Product prices shown in demo are for demonstration only and do not reflect real market rates. Actual pricing is configured per client deployment.

### 1 Active Claim

| Claim | Client | Policy | Date | Status |
|---|---|---|---|---|
| CLME7C01D | SC Logistic Trans | CASCO | 08 Mar 2026 | 🟡 Open |

---

## PART 4 — 24 AI TOOLS (WHAT ALEX CAN DO)

### 1. Client Management

**`broker_search_clients`** — Search by name, phone, or email
*Demo:* `"Find Andrei Ionescu"` → returns full profile with policies

**`broker_get_client`** — Full client profile with all active policies
*Demo:* `"Show me CLI002"` → Logistic Trans with 2 policies, 1 claim

**`broker_create_client`** — Add new client to database
*Demo:* `"Create a new client: Mihai Dumitrescu, phone 0745 000 111, RCA needed"`

**`broker_update_client`** — Update client details
*Demo:* `"Update CLI001's phone number to 0722 999 888"`

**`broker_delete_client`** — Remove client from database
*Demo:* `"Delete test client CLI_TEST"`

---

### 2. Policy Management

**`broker_list_policies`** — List by client or portfolio-wide
*Demo:* `"Show all active policies"` → 8 policies with status

**`broker_get_renewals_due`** — Expiring policies with urgency flags
*Demo:* `"What expires in the next 30 days?"` → 🔴 SC Logistic Trans (2 days!), Ion Gheorghe (16 days)

**`broker_check_rca_validity`** — Instant RCA validity check from database
*Demo:* `"Check RCA validity for Maria Popescu"` → status + expiry

---

### 3. Products & Offers

**`broker_search_products`** — Search products by type and country
*Demo:* `"Search RCA products in Romania"` → 3 insurers compared

**`broker_compare_products`** — Side-by-side comparison table
*Demo:* `"Compare PROD_RCA_ALZ, PROD_RCA_GEN, PROD_RCA_OMA"` → recommendation

**`broker_create_offer`** — Generate professional offer document
*Demo:* `"Create an offer for CLI001 with RCA and CASCO in English"` → downloadable file

**`broker_list_offers`** — List all generated offers
*Demo:* `"Show me all offers"`

**`broker_send_offer_email`** — Send offer directly to client email
*Demo:* `"Send the offer to CLI001 by email"`

---

### 4. Claims Processing

**`broker_log_claim`** — Register new damage claim
*Demo:* `"Log a claim for CLI001 on POL001, accident yesterday, broken windshield"`

**`broker_get_claim_status`** — Check claim status + insurer guidance
*Demo:* `"What's the status of CLME7C01D?"` → Generali Romania contact, portal link

---

### 5. Analytics & Compliance

**`broker_cross_sell`** — Identify missing coverage for a client
*Demo:* `"What products is CLI001 missing?"` → recommends based on profile

**`broker_calculate_premium`** — Estimate premium for a product
*Demo:* `"Estimate premium for CASCO on CLI002"`

**`broker_compliance_check`** — Check regulatory compliance status
*Demo:* `"Run compliance check on CLI004"`

**`broker_asf_summary`** — Monthly ASF report (Romania — Law 236/2018)
*Demo:* `"Generate ASF report for February 2026"`

**`broker_bafin_summary`** — Monthly BaFin report (Germany — VVG/IDD)
*Demo:* `"Generate BaFin report for February 2026"`

---

### 6. Web & Desktop Automation

**`broker_check_rca`** — Check RCA validity via browser automation
*Demo:* `"Check RCA for plate B123ABC online"`

**`broker_browse_web`** — Browse any website and extract information
*Demo:* `"Go to aida.info.ro and check plate B05CDE"`

**`broker_computer_use_status`** — Check if local agent is online
*Demo:* `"Is the local agent connected?"`

**`broker_run_task`** — Run any desktop or automation task on local machine
*Demo:* `"Open TextEdit and write the client summary"` (requires local agent running)

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
→ German client with Allianz Deutschland

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
- Your data is stored exclusively on GCP servers in Frankfurt (europe-west3) during MVP, then moves to a dedicated VM in Frankfurt post go-live
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
1. Vision AI reads the document natively — no OCR library needed
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
Pricing is available on request and tailored to the number of employees and specific requirements. Contact us for a custom proposal.

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

### Q10: What happens if the AI API goes down?
- Alex displays a clear error message in the chat
- The Chainlit interface remains accessible
- All previously generated documents remain available
- No data is lost
- Our monitoring alerts within 5 minutes of any outage

### Q11: Can different employees have different access levels?
Yes — the Admin Panel provides:
- **Superadmin (MSP):** full access, creates companies and users
- **Company Admin:** manages their company's users and permissions
- **Broker (Agent):** access only to tools their manager enables

Example: Trainee brokers can search clients and view policies, but cannot create offers or log claims until approved.

### Q12: What does the export feature produce?
From any offer or report Alex generates, you can download:
- **PDF** — professional format with broker logo, ready to send to clients
- **XLSX** — for further analysis in Excel, portfolio management
- **DOCX** — editable Word document for customization before sending

### Q13: What is the local agent and do we need it?
The local agent is a small Python script that runs on an employee's computer. It enables Alex to:
- Open and control desktop applications (Word, Excel, local insurance software)
- Access intranet systems and VPN-protected portals
- Automate tasks on the local machine

It is optional — Alex works fully without it for all cloud-based tasks.

### Q14: What is the current deployment status?
Alex is currently in **MVP phase**, running on Google Cloud Run (Frankfurt). This means:
- Fully functional — all 24 tools operational
- Used for demos, testing, and initial client pilots
- After MVP validation, the system migrates to a dedicated VM (Hetzner Frankfurt) for production use

---

## PART 7 — TECHNICAL STACK

| Component | Technology |
|---|---|
| Chat Interface | Chainlit 2.x |
| AI Engine | Claude Sonnet (Anthropic) |
| Backend | Python 3.12 |
| Database | SQLite (dev) → PostgreSQL (prod) |
| Current Deployment | GCP Cloud Run — europe-west3 |
| Final Deployment | VM — Hetzner Frankfurt (post-MVP) |
| Container | Docker |
| Local Agent | Python — macOS / Windows / Linux |

---

## PART 8 — CONTACT & NEXT STEPS

**Interested in a live demo?**

1. Visit the demo: https://insurance-broker-alex-elo6xae6nq-ey.a.run.app
2. Try the demo scripts from Part 5
3. Schedule a 1:1 session: we walk through your specific workflows
4. We prepare a custom offer within 48 hours

**For questions about GDPR, data residency, or custom integrations:**
Contact us directly — we provide full technical documentation and sign NDAs before any deep-dive.

---

*Alex — Insurance Broker AI | Powered by Claude Sonnet (Anthropic) | GCP Frankfurt (EU) → VM Frankfurt (prod) | ASF & BaFin Compliant*
*Document version: 2.0 | Date: March 2026*
