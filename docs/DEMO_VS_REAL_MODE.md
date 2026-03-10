# Alex — Insurance Broker AI
## Demo Mode vs Production — Technical Guide

---

## 1. Demo Data — Inventar Date Sintetice

### 1.1 What Is in the Demo

| Data Type | Source File | Records | Details |
|-----------|-------------|---------|---------|
| Clients | `mock_clients.json` | 6 | 3 individual RO, 1 company RO, 1 individual DE, 1 company DE |
| Products | `mock_products.json` | 10 | RCA(3), CASCO(3), PAD(1), CMR(1), KFZ(2) |
| Policies | `mock_policies.json` | 8 | Various types, expiry dates near present |
| Insurers | `mock_insurers.json` | 7 | 5 RO (ALZ, GEN, OMA, ASI, GRA), 2 DE (ALZ_DE, AXA_DE) |
| Claims | Seeded in DB | 1 | CLME7C01D — SC Logistic Trans, open |

> **Note:** Prices in demo data are for demonstration only and do not reflect real market rates. Real pricing is configured per client in Phase 2.

### 1.2 Demo Clients

| ID | Name | Type | Country | Email | Policies |
|----|------|------|---------|-------|----------|
| CLI001 | Andrei Ionescu | Individual | RO | andrei.ionescu@gmail.com | RCA + CASCO |
| CLI002 | SC Logistic Trans SRL | Company | RO | office@logistictrans.ro | RCA Fleet + CMR |
| CLI003 | Maria Popescu | Individual | RO | maria.popescu@yahoo.com | CASCO + PAD |
| CLI004 | Johann Schmidt | Individual | DE | j.schmidt@firma-schmidt.de | KFZ |
| CLI005 | Ion Gheorghe | Individual | RO | ion.gheorghe@hotmail.com | CASCO |
| CLI006 | Immobilien GmbH Muller | Company | DE | info@mueller-immobilien.de | (no policies) |

### 1.3 Demo Products

| Product ID | Insurer | Type | Rating |
|------------|---------|------|--------|
| PROD_RCA_ALZ | Allianz-Tiriac | RCA | AA |
| PROD_RCA_GEN | Generali Romania | RCA | AA |
| PROD_RCA_OMA | Omniasig VIG | RCA | A+ |
| PROD_CASCO_ALZ | Allianz-Tiriac | CASCO | AA |
| PROD_CASCO_GEN | Generali Romania | CASCO | AA |
| PROD_CASCO_OMA | Omniasig VIG | CASCO | A+ |
| PROD_PAD_OMA | Omniasig VIG | PAD | A+ |
| PROD_CMR_GEN | Generali Romania | CMR | AA |
| PROD_KFZ_ALZ_DE | Allianz Deutschland | KFZ | AA |
| PROD_KFZ_AXA_DE | AXA Versicherung | KFZ | AA |

### 1.4 Database Schema

**Broker Tables:**

```sql
clients (id, name, id_number, phone, email, address, client_type, country, source, notes, created_at)
policies (id, client_id, policy_type, insurer, policy_number, start_date, end_date, annual_premium, insured_sum, currency, installments, status, broker_commission_pct)
insurers (id, name, country, products, rating, broker_contact)
products (id, insurer_id, insurer_name, product_type, annual_premium, currency, insured_sum, deductible, coverage_summary, exclusions, rating)
offers (id, client_id, created_at, valid_until, status, file_path, products_count, notes)
claims (id, client_id, policy_id, incident_date, reported_date, description, status, damage_estimate, insurer_claim_number, notes)
```

**Admin Tables:**

```sql
companies (id, name, slug, country, is_active, monthly_token_limit, plan_tier, created_at)
users (id, company_id, email, hashed_password, full_name, role, is_active, created_at)
tool_permissions (user_id, tool_name)
audit_log (id, user_id, company_id, tool_name, input_summary, success, tokens_used, created_at)
token_usage (id, company_id, user_id, month, tokens_used)
```

### 1.5 How to Reset the Demo

```bash
# Delete existing database
rm mcp-server/insurance_broker.db

# Recreate and populate with demo data
cd mcp-server && python -m insurance_broker_mcp.data.seed_db

# Recreate admin tables
python scripts/create_superadmin.py
```

### 1.6 How to Add New Demo Data

1. Edit the corresponding JSON file in `mcp-server/insurance_broker_mcp/data/`
2. Add new records following the existing format
3. Run `python -m insurance_broker_mcp.data.seed_db` (uses `INSERT OR REPLACE`)
4. Verify with `python scripts/test_all_tools.py`

### 1.7 Demo Limitations

| Aspect | Limitation | Impact |
|--------|------------|--------|
| Prices | Demonstrative, do not reflect market | Offers have placeholder prices |
| Policy numbers | Fictional | Cannot be verified externally |
| Email | SMTP not configured | Offers are not actually sent |
| RCA verification | Only in local DB | Does not check via CEDAM |
| ASF/BaFin reports | Based on synthetic data | Numbers are illustrative |
| Volume | 6 clients, 8 policies | Does not test performance at scale |
| HEALTH/LIFE | No products in catalog | Cross-sell suggests but cannot generate offer |

---

## 2. Phase 1 vs Phase 2 — MVP and Production

### 2.1 Phase 1 — MVP (Current): Cloud Run

The system runs on Google Cloud Run (Frankfurt):
- **URL:** https://insurance-broker-alex-603810013022.europe-west3.run.app
- **Database:** SQLite (file in container)
- **Advantages:** rapid deployment, zero infrastructure management, automatic scaling
- **Limitations:** stateless (data lost on restart), per-request cost at high volume

**Purpose:** Test the platform with employees. Validate which tools are useful. Identify what needs to be built differently in Phase 2. The MVP is built on our research into brokerage workflows — not yet on the client's real processes.

---

### 2.2 Phase 2 — Production: Dedicated VM on Google Cloud

After MVP validation with the client's internal test team, the system migrates to a dedicated VM on Google Cloud (Frankfurt):
- Persistent PostgreSQL database (backed up daily, 30-day retention)
- Dedicated MCP server built on real process mapping
- Constant performance, no cold starts
- Full control of infrastructure
- Predictable cost

**What changes in Phase 2:**
- MCP server rebuilt on the client's real workflows — not on our assumptions
- All demo data replaced with real client data (clients, policies, products, real prices) — only after contract and DPA are signed
- Per-employee skills and permissions configured on their actual roles
- Email integration (SMTP) active
- Custom branding (company name and logo in all documents)
- Full audit log and RBAC active

> **GDPR:** Phase 1 runs exclusively on synthetic data. No real client records are imported or processed before the Data Processing Agreement (DPA) is signed. Real data migration begins only in Phase 2, after both the service contract and DPA are in place.

---

## 3. Production Architecture — Technical Details

### 3.1 SQLite → PostgreSQL Migration

**Step 1: Provision VM on Google Cloud**

```bash
# Create VM in europe-west3 (Frankfurt — GDPR)
gcloud compute instances create alex-broker-prod \
  --machine-type=e2-standard-4 \
  --zone=europe-west3-a \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=100GB
```

**Step 2: Install PostgreSQL**

```bash
apt install postgresql-16
sudo -u postgres createdb insurance_broker
sudo -u postgres createuser broker_app
```

**Step 3: PostgreSQL Schema**

Schema is identical to SQLite with minor differences:

```sql
CREATE TABLE clients (
    id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    id_number VARCHAR(50),
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    address TEXT,
    client_type VARCHAR(20) DEFAULT 'individual',
    country VARCHAR(5) DEFAULT 'RO',
    source VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
-- All other tables: same pattern
```

**Step 4: Update Connection String**

Add to `.env`:
```
DB_HOST=localhost
DB_NAME=insurance_broker
DB_USER=broker_app
DB_PASS=<password>
```

**Step 5: Update Code**

Each tool file in `mcp-server/insurance_broker_mcp/tools/` switches from:

```python
# Current (SQLite):
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
```

To:

```python
# Production (PostgreSQL):
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host=os.environ["DB_HOST"],
    database=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASS"],
    cursor_factory=RealDictCursor
)
```

**Recommended:** Create a `shared/database.py` module with connection pool:

```python
from psycopg2 import pool

_pool = pool.SimpleConnectionPool(1, 10, dsn=os.environ["DATABASE_URL"])

def get_db():
    return _pool.getconn()

def release_db(conn):
    _pool.putconn(conn)
```

### 3.2 Real Data Migration — Clients

> **GDPR prerequisite:** Real client data is imported only after the Data Processing Agreement (DPA) is signed. During Phase 1 (MVP), all testing is done with synthetic data only.

**Step 0: Validation with sample data (before full import)**

Before importing the full client database, we validate the import process with a small representative sample — 20–50 records, anonymised or pseudonymised where possible. This confirms the data format is correct and the import pipeline works, without exposing the full client database before it is necessary.

**Option A: CSV Import (recommended to start)**

Expected CSV format:
```csv
name,phone,email,address,client_type,country,id_number,source,notes
"Popescu Ion","+40722123456","ion@email.com","Str. Libertatii 5, Bucuresti","individual","RO","1830415251234","referral","Old client"
```

Import script: adapt `seed_db.py` to read CSV instead of JSON.

**Option B: CRM API Connection**

```python
def sync_clients_from_crm():
    resp = requests.get("https://crm.broker.ro/api/v1/clients",
                       headers={"Authorization": f"Bearer {CRM_TOKEN}"})
    for client in resp.json()["data"]:
        upsert_client(
            name=client["full_name"],
            phone=client["phone"],
            email=client["email"],
        )
```

**Option C: Direct Database Connection**

```sql
CREATE MATERIALIZED VIEW alex_clients AS
SELECT
    crm_client_id AS id,
    concat(first_name, ' ', last_name) AS name,
    phone, email, address,
    CASE WHEN company_name IS NOT NULL THEN 'company' ELSE 'individual' END AS client_type
FROM crm_clients;
```

### 3.3 Real Data Migration — Products

**Current state:** Products are static in `mock_products.json`. Prices are demonstrative.

**Options for production:**

| Method | Description | Effort | Update Frequency |
|--------|-------------|--------|-----------------|
| Manual CSV | Broker uploads real price list periodically | Low | Monthly/quarterly |
| Admin panel CRUD | Admin interface for products | Medium | Any time |
| Insurer API | Connect to each insurer's API | High | Real-time |

**Required fields from each insurer:**
- Product type (RCA, CASCO, etc.)
- Product name
- Annual premium (or calculation formula) — configured by broker
- Deductible
- Coverage summary
- Exclusions
- Broker commission (%)

### 3.4 Insurer API Integrations

| Insurer | API Available? | Integration Type | Phase |
|---------|---------------|-----------------|-------|
| Allianz-Tiriac RO | Broker portal API | REST | Phase 2 |
| Generali Romania | Price comparison API | SOAP/REST | Phase 2 |
| Omniasig VIG | Manual upload | CSV | Phase 2 |
| Asirom VIG | Broker portal | Web scrape | Phase 3 |
| Groupama | Partner API | REST | Phase 3 |
| CEDAM (RCA verification) | Public API | REST | Phase 3 |
| PAID Pool (PAD) | Delegate portal | Web | Phase 3 |
| Allianz Deutschland | Makler API | REST | Phase 2 |
| AXA Versicherung | AXA Portal | REST | Phase 2 |

### 3.5 Email Production Configuration

**Production recommendations:**

1. **SendGrid** (recommended) — tracking, analytics, deliverability
2. Configure **SPF**, **DKIM**, **DMARC** on the company's domain
3. Use a dedicated subdomain: `oferte@notifications.broker.ro`
4. Monitor bounce rate and spam complaints

### 3.6 Authentication and Security

**Required environment variables:**
```
CHAINLIT_AUTH_SECRET=<random 64-character string>
ADMIN_JWT_SECRET=<random 64-character string>
```

**User setup:**
1. Create superadmin: `python scripts/create_superadmin.py`
2. Access `/admin` → Login
3. Create the client's company
4. Create accounts for each employee
5. Configure permissions per user (RBAC)

**Roles:**
- **superadmin** — full access, manages all companies
- **company_admin** — manages company users and permissions
- **broker** — access only to tools approved by admin

---

## 4. Migration Plan: Cloud Run MVP → Production VM

> **GDPR prerequisite before Phase 2 data import:** Service contract signed + Data Processing Agreement (DPA) signed. Real client data is never imported before these are in place.

### Week 1–2: Process Mapping + Contract (Phase 2 start)
- [ ] Individual sessions with each employee — map real workflows
- [ ] Full documentation: client intake, renewals, claims, reporting
- [ ] Identify required integrations (CRM, email, insurer portals)
- [ ] Sign service contract + Data Processing Agreement (DPA) ← **required before any data export**
- [ ] Request sample data export from client (20–50 records, anonymised if possible) — for import validation only

### Week 3–4: Build Dedicated MCP Server + VM Setup
- [ ] Provision VM on Google Cloud (europe-west3 Frankfurt)
- [ ] Install Docker + PostgreSQL on VM
- [ ] Configure custom domain + SSL certificate (Let's Encrypt)
- [ ] Build dedicated MCP server based on real process mapping
- [ ] Validate import pipeline with sample data (anonymised)
- [ ] Full client data export from broker's current system
- [ ] Import real clients into PostgreSQL (post-DPA)
- [ ] Configure products per partner insurer (real prices set by broker)
- [ ] Set up email integration (SMTP)
- [ ] Create user accounts with appropriate permissions
- [ ] Configure n8n workflows (renewal reminders, monthly reports)

### Week 5–6: Training and Testing
- [ ] Run full test suite on production data
- [ ] Individual training sessions per employee (1–2 hours each)
- [ ] Parallel operation: Alex + existing tools for 1 week
- [ ] Collect feedback and adjustments
- [ ] Test emails (send real offers to test addresses)
- [ ] Test ASF/BaFin reports with real data

### Week 7: Go-Live on Production VM
- [ ] Switch DNS to production VM
- [ ] Intensive monitoring first week
- [ ] Priority support for 30 days
- [ ] Weekly review calls with broker team

---

## 5. Code Changes for Production

### 5.1 Files to Modify

| File | What Changes | Why |
|------|-------------|-----|
| All `tools/*.py` | `get_db()` → PostgreSQL connection pool | Production database |
| `shared/db.py` | PostgreSQL connection for admin tables | Admin tables in production |
| `seed_db.py` | Adapted for PostgreSQL + CSV import | Real data |
| `.env` | All production credentials | Real services |
| `CLAUDE.md` | Real broker name, license, products | Customization |
| `Dockerfile` | Add psycopg2 dependency | PostgreSQL driver |
| `requirements.txt` | Add `psycopg2-binary>=2.9.0` | PostgreSQL driver |

### 5.2 Production Environment Variables

```env
# Database
DB_HOST=localhost
DB_NAME=insurance_broker
DB_USER=broker_app
DB_PASS=<password>

# AI
ANTHROPIC_API_KEY=<production key>
CLAUDE_MODEL=claude-sonnet-4-6

# Email
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASS=<SendGrid API key>
SMTP_FROM_NAME=<Broker Company Name>

# Authentication
CHAINLIT_AUTH_SECRET=<random 64-character string>
ADMIN_JWT_SECRET=<random 64-character string>

# App
PORT=8080
```

### 5.3 New Dependencies

Add to `requirements.txt`:
```
psycopg2-binary>=2.9.0
```

---

## 6. Migration FAQ

**Q: Do we lose demo data when switching to production?**
No. The demo remains available with the local SQLite database. Production uses a separate PostgreSQL database on the VM.

**Q: How long does migration take?**
Estimated 5–7 weeks, depending on process complexity and data volume.

**Q: Can we run demo and production in parallel?**
Yes. The demo runs locally with SQLite or on Cloud Run, production runs on the VM with PostgreSQL.

**Q: What happens if the AI API is unavailable?**
The chat interface remains accessible. Previously generated documents remain available. Anthropic SLA: 99.9%.

**Q: Can we add new insurers after go-live?**
Yes. Added to the `products` and `insurers` tables — either manually via SQL or through the admin panel CRUD.

**Q: Are demo prices real?**
No. Demo prices are illustrative. In production, the broker configures real prices per partner insurer.

**Q: When do you need our client data?**
Only in Phase 2, and only after both the service contract and Data Processing Agreement (DPA) are signed. In Phase 1 (MVP), all testing runs on synthetic data — no real client records are needed or requested.

**Q: What data do you need in Phase 1 before signing?**
Only: the list of employees who will participate in the pilot (name, email, role) and optionally your company logo. No client records, no policy data, no pricing data.

**Q: What is different between Phase 1 and Phase 2?**
Phase 1 (MVP) is built on our research into typical brokerage workflows — it is the starting point. Phase 2 is built on the client's actual processes, mapped together with their team. The MCP server in Phase 2 is purpose-built for how their brokerage actually works, not adapted from a generic template.

---

*Document updated: March 2026 | Alex Insurance Broker AI v2.1*
