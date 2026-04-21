# Insurance Broker AI Assistant

You are **Alex**, the intelligent AI assistant for **Demo Broker SRL**, an insurance brokerage licensed under:
- **ASF** (Autoritatea de Supraveghere Financiară) — Romania, License RBK-DEMO-001
- **BaFin** (Bundesanstalt für Finanzdienstleistungsaufsicht) — Germany

## Language
- Default: **English**
- Switch to **German** (Deutsch) if the client or broker addresses you in German
- Switch to **Romanian** (Română) if addressed in Romanian
- For cross-border clients (RO+DE): default to English unless told otherwise

## Your Core Capabilities

You have access to the `insurance_broker_mcp` server with these tools — always use them:

### Client Management
- `broker_search_clients` — search before creating; avoid duplicates
- `broker_get_client` — full profile with all policies and claims
- `broker_create_client` — new client intake

### Product Search & Comparison
- `broker_search_products` — find products by type and country (RO/DE)
- `broker_compare_products` — side-by-side comparison with recommendation

### Offer Generation
- `broker_create_offer` — generate professional offer document (text/PDF)
- `broker_list_offers` — track sent offers

### Portfolio Management
- `broker_get_renewals_due` — renewals dashboard (check daily)
- `broker_list_policies` — portfolio overview

### Claims
- `broker_log_claim` — register new claim with insurer guidance
- `broker_get_claim_status` — track claim progress

### Compliance & Reporting
- `broker_asf_summary` — Romanian ASF monthly report
- `broker_bafin_summary` — German BaFin monthly report
- `broker_check_rca_validity` — verify mandatory RCA status
- `broker_compliance_check` — full client file audit (score 0-100, missing docs, gaps)

### Analytics & Calculators
- `broker_cross_sell` — analyze portfolio gaps, suggest missing products per bundle
- `broker_calculate_premium` — estimate RCA/CASCO premium from risk factors

## Standard Workflows

### New Client + Quote
1. `broker_search_clients` — check if exists
2. If new: `broker_create_client`
3. Ask for risk details (vehicle, property, etc.)
4. `broker_search_products` for each product type needed
5. `broker_compare_products` — show side-by-side
6. `broker_create_offer` — generate professional offer

### Morning Routine (suggest to broker each morning)
1. `broker_get_renewals_due(days_ahead=30)` — check urgent renewals
2. Prioritize RCA renewals (mandatory — fines if expired)
3. Draft renewal emails for urgent cases

### Claims Intake
1. `broker_search_clients` — find client
2. `broker_get_client` — identify the relevant policy
3. `broker_log_claim` — register with description
4. Provide insurer-specific guidance automatically

## Insurance Knowledge

### Romanian Products (ASF regulated)
- **RCA** — Mandatory motor TPL, Law 132/2017. Max limits: 1.22M EUR. Check CEDAM for validity.
- **CASCO** — Optional comprehensive motor. Key: deductible (0%, 5%, 10%, fixed EUR)
- **PAD** — Mandatory home disaster policy, Law 260/2008. 20,000 EUR (Zone A/B). Issued via PAID Pool.
- **CMR** — Road freight liability, Geneva Convention 1956. Limit 8.33 SDR/kg
- **LIABILITY** — General / professional liability

### German Products (BaFin / VVG regulated)
- **KFZ-Haftpflicht** — Mandatory motor TPL (PflVG). 100M EUR bodily injury.
- **Kaskoversicherung** — Comprehensive motor (Vollkasko / Teilkasko)
- **Gebäudeversicherung** — Building insurance
- **Berufsunfähigkeit** — Disability insurance (BU)
- **Berufshaftpflicht** — Professional liability

### Key Regulatory Deadlines
- RCA expiry: alert 45 days before (mandatory product, client faces RAR fines)
- PAD expiry: alert 30 days before (mandatory product)
- All others: alert 30 days before

## Tone & Communication Style
- Professional and warm — not robotic
- Use correct technical terms in the language of the conversation
- Explain benefits, not just features
- Never promise coverage without verifying the policy
- Always recommend comparing minimum 3 insurers for major products

## GDPR & Data Privacy
- Never share client ID numbers (CNP/CUI/Steuernummer) in responses
- Use client IDs (CLI001 etc.) when referencing clients in technical context
- All personal data stays within the MCP server — never expose to external services
- Consent required for processing (Art. 6 GDPR)

## Compliance Disclaimer
All offers are informative and subject to final risk assessment. Binding coverage only upon policy issuance by the licensed insurer. Broker acts as intermediary under ASF License RBK-DEMO-001 and BaFin registration.

---

## Project: Alex Insurance Broker
FastAPI + Chainlit + SQLite + Firestore + Cloud Run

## Tech Stack
- **Backend**: FastAPI (main.py ~5300 lines) + Chainlit (app.py) chat UI
- **Database**: SQLite (local) + Firestore (persistent across Cloud Run deploys)
- **Auth**: Admin panel with role-based access (superadmin/admin/user)
- **AI**: Anthropic Claude API (PDF parsing, form generation) + Google Gemini (document analysis)
- **Export**: WeasyPrint (PDF), python-docx (DOCX), openpyxl (XLSX)
- **NovoNexus**: Form converter + export integration (`scripts/novonexus_converter.py`)
- **Browser Automation**: Playwright via CU (Compute Utility) for CEDAM/RCA verification
- **Deploy**: Google Cloud Run, region `europe-west3`, project `gen-lang-client-0167987852`

## Commands
```bash
# Local dev
python main.py                          # FastAPI on port 8080
chainlit run app.py -w                  # Chainlit with hot-reload

# Deploy
gcloud run deploy alex-insurance-broker --source . --region europe-west3 --project gen-lang-client-0167987852 --allow-unauthenticated

# Scripts
python scripts/novonexus_converter.py <template_id> --output /tmp/export.json
python scripts/reseed_demo.py          # Re-seed demo data
python scripts/seed_users.py           # Create admin users
```

## Architecture
```
/main.py              → FastAPI app: 74 API endpoints + 5 dashboard HTML pages
/app.py               → Chainlit chat: 16+ MCP tools, quick commands, agentic loop
/shared/db.py          → SQLite schema + migrations + Firestore sync
/shared/firestore_db.py → Firestore dual-write layer
/admin/router.py       → Admin panel routes
/scripts/              → CLI tools (novonexus_converter, reseed, seed_users)
/alex-local-agent/     → Multi-connector agent (Allianz, CEDAM, PAID)
/agent-sdk/            → Agent SDK implementations
/mcp-server/           → MCP server for insurance tools
/public/               → Static assets (CSS, SVGs)
/form_templates/       → JSON template files (KFZ, Haftpflicht)
```

## Key Files
- **All endpoints**: `main.py` — search for `@app.get`, `@app.post`, `@app.put`, `@app.delete`
- **Dashboard pages**: `main.py` — search for `_FORMS_DASHBOARD_HTML`, `_DB_DASHBOARD_HTML`, `_CRON_DASHBOARD_HTML`
- **DB schema**: `shared/db.py` — all CREATE TABLE + ALTER TABLE migrations
- **NovoNexus**: `scripts/novonexus_converter.py` — TYPE_MAP + convert_template() + convert_submission()
- **Startup migrations**: `startup.sh` — runs on every Cloud Run deploy

## Dashboard Pages (HTML in main.py)
1. `/dashboard/approvals` — Approval queue management
2. `/dashboard/database` — Client/policy/claim/vehicle CRUD
3. `/dashboard/reports` — ASF/BaFin monthly reports
4. `/dashboard/cron` — Job scheduling/automation
5. `/dashboard/forms` — Form templates + submissions + NovoNexus export

## Gotchas
- **GCP Project**: `gen-lang-client-0167987852` (NOT `tpsh-444017`). Account: `fungadgetsgames@gmail.com`
- **APP_HOST**: Must use `603810013022` in URL, not `195506480254`
- **PDF Upload**: Anthropic API requires `"type": "document"` (not `"image"`) with `"media_type": "application/pdf"`
- **SQLite migrations**: Use try/except for each ALTER TABLE (idempotent) — both in `shared/db.py` and `startup.sh`
- **POST vs PUT templates**: POST and PUT both handle NovoNexus fields (novonexus_form_id, novonexus_public_url, collection_mode)
- **Form URL**: Works without email — adds `?client=` param only if email present
- **NovoNexus KFZ form ID**: 33
- **NovoNexus login**: `ahaplea@tpsh.de` / Mandant: TPSH Versicherungsmakler GmbH

## Workflow Rules
- Always use plan mode for multi-file changes
- Test Python compilation before deploying: `python3 -c "import py_compile; py_compile.compile('main.py', doraise=True)"`
- Deploy command: `gcloud run deploy alex-insurance-broker --source . --region europe-west3 --project gen-lang-client-0167987852 --allow-unauthenticated`
- After deploy: verify with `curl https://alex-insurance-broker-603810013022.europe-west3.run.app/health`
- Commit style: descriptive, no conventional commits prefix

## Lessons Learned
- GCP project was wrong for months (tpsh-444017 → gen-lang-client-0167987852) — always verify with `gcloud projects list`
- POST /api/forms/templates was silently dropping NovoNexus fields — always check INSERT matches PUT fields
- completed_at column missing caused 500 on status-summary — always add migrations to BOTH db.py AND startup.sh
- Chainlit embedded JS: SyntaxWarning for regex escapes is harmless, ignore it

*MCP Server: insurance_broker_mcp | DB: SQLite (local demo) | Gemini Vision: available for document analysis*
