# Alex — Insurance Broker AI
## Demo Mode vs Real Mode — Ghid Tehnic

---

## 1. Demo Mode — Arhitectura Curenta

### 1.1 Inventar Date Sintetice

| Tip Date | Fisier Sursa | Inregistrari | Detalii |
|----------|-------------|--------------|---------|
| Clienti | `mock_clients.json` | 6 | 3 individuali RO, 1 companie RO, 1 individual DE, 1 companie DE |
| Produse | `mock_products.json` | 10 | RCA(3), CASCO(3), PAD(1), CMR(1), KFZ(2) |
| Polite | `mock_policies.json` | 8 | Diverse tipuri, date expirare aproape de prezent |
| Asiguratori | `mock_insurers.json` | 7 | 5 RO (ALZ, GEN, OMA, ASI, GRA), 2 DE (ALZ_DE, AXA_DE) |
| Daune | Seeded in DB | 1 | CLME7C01D — SC Logistic Trans, open |

> **Nota:** Preturile din datele demo sunt demonstrative si nu reflecta piata reala. Preturile reale se configureaza per client in productie.

### 1.2 Clienti Demo

| ID | Nume | Tip | Tara | Email | Polite |
|----|------|-----|------|-------|--------|
| CLI001 | Andrei Ionescu | Individual | RO | andrei.ionescu@gmail.com | RCA + CASCO |
| CLI002 | SC Logistic Trans SRL | Companie | RO | office@logistictrans.ro | RCA Fleet + CMR |
| CLI003 | Maria Popescu | Individual | RO | maria.popescu@yahoo.com | CASCO + PAD |
| CLI004 | Johann Schmidt | Individual | DE | j.schmidt@firma-schmidt.de | KFZ |
| CLI005 | Ion Gheorghe | Individual | RO | ion.gheorghe@hotmail.com | CASCO |
| CLI006 | Immobilien GmbH Muller | Companie | DE | info@mueller-immobilien.de | (fara polite) |

### 1.3 Produse Demo

| ID Produs | Asigurator | Tip | Rating |
|-----------|-----------|-----|--------|
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

### 1.4 Schema Bazei de Date

**Tabele Broker:**

```sql
clients (id, name, id_number, phone, email, address, client_type, country, source, notes, created_at)
policies (id, client_id, policy_type, insurer, policy_number, start_date, end_date, annual_premium, insured_sum, currency, installments, status, broker_commission_pct)
insurers (id, name, country, products, rating, broker_contact)
products (id, insurer_id, insurer_name, product_type, annual_premium, currency, insured_sum, deductible, coverage_summary, exclusions, rating)
offers (id, client_id, created_at, valid_until, status, file_path, products_count, notes)
claims (id, client_id, policy_id, incident_date, reported_date, description, status, damage_estimate, insurer_claim_number, notes)
```

**Tabele Admin:**

```sql
companies (id, name, slug, country, is_active, monthly_token_limit, plan_tier, created_at)
users (id, company_id, email, hashed_password, full_name, role, is_active, created_at)
tool_permissions (user_id, tool_name)
audit_log (id, user_id, company_id, tool_name, input_summary, success, tokens_used, created_at)
token_usage (id, company_id, user_id, month, tokens_used)
```

### 1.5 Cum se Reseteaza Demo-ul

```bash
# Sterge baza de date existenta
rm mcp-server/insurance_broker.db

# Recreeaza si populeaza cu date demo
cd mcp-server && python -m insurance_broker_mcp.data.seed_db

# Recreeaza tabelele admin
python scripts/create_superadmin.py
```

### 1.6 Cum se Adauga Date Demo Noi

1. Editeaza fisierul JSON corespunzator din `mcp-server/insurance_broker_mcp/data/`
2. Adauga inregistrari noi respectand formatul existent
3. Ruleaza `python -m insurance_broker_mcp.data.seed_db` (foloseste `INSERT OR REPLACE`)
4. Verifica cu `python scripts/test_all_tools.py`

### 1.7 Limitari Demo

| Aspect | Limitare | Impact |
|--------|---------|--------|
| Preturi | Demonstrative, nu reflecta piata | Ofertele au preturi placeholder |
| Numere polite | Fictive | Nu pot fi verificate extern |
| Email | SMTP neconfigurat | Ofertele nu se trimit efectiv |
| Verificare RCA | Doar local in DB | Nu verifica prin CEDAM |
| Rapoarte ASF/BaFin | Bazate pe date sintetice | Cifrele sunt estimative |
| Volum | 6 clienti, 8 polite | Nu testeaza performanta la scara |
| HEALTH/LIFE | Fara produse in catalog | Cross-sell sugereaza dar nu poate oferta |

---

## 2. Deployment — MVP vs Productie

### 2.1 Faza MVP (Curenta) — Cloud Run

Sistemul ruleaza pe Google Cloud Run (europe-west3, Frankfurt):
- **URL:** https://insurance-broker-alex-elo6xae6nq-ey.a.run.app
- **Baza de date:** SQLite (fisier local in container)
- **Avantaje:** deploy rapid, zero administrare infrastructura, scalare automata
- **Limitari:** stateless (datele se pierd la restart), cost per request la volum mare

### 2.2 Faza Productie — VM Dedicata

Dupa validarea MVP, sistemul migreaza pe VM dedicata (Hetzner Frankfurt sau echivalent):
- Baza de date persistenta (PostgreSQL)
- Performanta constanta, fara cold starts
- Control complet al infrastructurii
- Cost predictibil

---

## 3. Real Mode — Arhitectura Productie

### 3.1 Migrare SQLite → PostgreSQL

**Pas 1: Provisionare VM**

```bash
# Hetzner Cloud CLI (exemplu)
hcloud server create \
  --name alex-broker-prod \
  --type cx32 \
  --image ubuntu-24.04 \
  --location fsn1
```

**Pas 2: Instalare PostgreSQL**

```bash
apt install postgresql-16
sudo -u postgres createdb insurance_broker
sudo -u postgres createuser broker_app
```

**Pas 3: Schema PostgreSQL**

Schema ramane identica cu SQLite, cu mici diferente:

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
-- Restul tabelelor: acelasi pattern
```

**Pas 4: Actualizare Connection String**

Adauga in `.env`:
```
DB_HOST=localhost
DB_NAME=insurance_broker
DB_USER=broker_app
DB_PASS=<parola>
```

**Pas 5: Actualizare Cod**

Fiecare fisier tool din `mcp-server/insurance_broker_mcp/tools/` trece de la:

```python
# Curent (SQLite):
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
```

La:

```python
# Productie (PostgreSQL):
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

**Recomandare:** Creeaza un modul `shared/database.py` cu connection pool:

```python
from psycopg2 import pool

_pool = pool.SimpleConnectionPool(1, 10, dsn=os.environ["DATABASE_URL"])

def get_db():
    return _pool.getconn()

def release_db(conn):
    _pool.putconn(conn)
```

### 3.2 Integrare Date Reale — Clienti

**Optiunea A: Import CSV (recomandat pentru start)**

Format CSV asteptat:
```csv
name,phone,email,address,client_type,country,id_number,source,notes
"Popescu Ion","+40722123456","ion@email.com","Str. Libertatii 5, Bucuresti","individual","RO","1830415251234","referral","Client vechi"
```

Script import: adapteaza `seed_db.py` sa citeasca CSV in loc de JSON.

**Optiunea B: Conectare CRM via API**

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

**Optiunea C: Conectare directa la baza de date existenta**

```sql
CREATE MATERIALIZED VIEW alex_clients AS
SELECT
    crm_client_id AS id,
    concat(first_name, ' ', last_name) AS name,
    phone, email, address,
    CASE WHEN company_name IS NOT NULL THEN 'company' ELSE 'individual' END AS client_type
FROM crm_clients;
```

### 3.3 Integrare Date Reale — Produse

**Starea curenta:** Produsele sunt statice in `mock_products.json`. Preturile sunt demonstrative.

**Optiuni pentru productie:**

| Metoda | Descriere | Efort | Frecventa Update |
|--------|----------|-------|------------------|
| CSV manual | Brokerul incarca lista de preturi reale periodic | Mic | Lunar/trimestrial |
| Admin panel CRUD | Interfata admin pentru produse | Mediu | Oricand |
| API asigurator | Conectare la API-ul fiecarui asigurator | Mare | Real-time |

**Campuri necesare de la fiecare asigurator:**
- Tip produs (RCA, CASCO, etc.)
- Nume produs
- Prima anuala (sau formula de calcul) — configurata de broker
- Fransiza (deductible)
- Acoperire (coverage summary)
- Excluderi
- Comision broker (%)

### 3.4 Integrare API Asiguratori

| Asigurator | API Disponibil? | Tip Integrare | Faza |
|-----------|----------------|---------------|------|
| Allianz-Tiriac RO | Portal broker API | REST | Faza 2 |
| Generali Romania | API comparare preturi | SOAP/REST | Faza 2 |
| Omniasig VIG | Upload manual | CSV | Faza 2 |
| Asirom VIG | Portal broker | Web scrape | Faza 3 |
| Groupama | API parteneri | REST | Faza 3 |
| CEDAM (verificare RCA) | API public | REST | Faza 3 |
| PAID Pool (PAD) | Portal delegat | Web | Faza 3 |
| Allianz Deutschland | Makler API | REST | Faza 2 |
| AXA Versicherung | AXA Portal | REST | Faza 2 |

### 3.5 Configurare Email Productie

**Recomandari pentru productie:**

1. **SendGrid** (recomandat) — tracking, analytics, deliverability
2. Configureaza **SPF**, **DKIM**, **DMARC** pe domeniul companiei
3. Foloseste un subdomain dedicat: `oferte@notifications.broker.ro`
4. Monitorizeaza bounce rate si spam complaints

### 3.6 Autentificare si Securitate

**Variabile de mediu necesare:**
```
CHAINLIT_AUTH_SECRET=<string random 64 caractere>
ADMIN_JWT_SECRET=<string random 64 caractere>
```

**Setup utilizatori:**
1. Creeaza superadmin: `python scripts/create_superadmin.py`
2. Acceseaza `/admin` → Login
3. Creeaza compania clientului
4. Creeaza conturi pentru fiecare angajat
5. Configureaza permisiuni per utilizator (RBAC)

**Roluri:**
- **superadmin** — acces complet, gestioneaza toate companiile
- **company_admin** — gestioneaza utilizatorii si permisiunile companiei
- **broker** — acces doar la tool-urile aprobate de admin

---

## 4. Plan de Tranzitie: Cloud Run MVP → VM Productie

### Faza 1: Infrastructura VM (Saptamana 1)

- [ ] Provisionare VM (Hetzner fsn1 sau echivalent Frankfurt)
- [ ] Instalare Docker + PostgreSQL
- [ ] Configurare domeniu custom + certificat SSL (Let's Encrypt)
- [ ] Setup backup automat (pg_dump zilnic)
- [ ] Deploy container Docker pe VM
- [ ] Verificare health check si accesibilitate

### Faza 2: Migrare Date (Saptamana 2)

- [ ] Export date clienti din sistemul actual al brokerului (CRM/Excel/CSV)
- [ ] Transformare in schema Alex (script Python)
- [ ] Import clienti in PostgreSQL
- [ ] Import polite active
- [ ] Import lista asiguratori parteneri cu date contact
- [ ] Import catalog produse real de la asiguratori (preturi configurate de broker)
- [ ] Verificare integritate date

### Faza 3: Configurare (Saptamana 3)

- [ ] Configurare SMTP pentru trimitere email-uri
- [ ] Creare companie in Admin Panel (`/admin`)
- [ ] Creare conturi utilizator pentru fiecare angajat
- [ ] Setare permisiuni tool-uri per rol (RBAC)
- [ ] Personalizare cu numele real al brokerului si licenta
- [ ] Actualizare branding in template-urile de oferte
- [ ] Configurare n8n workflows (renewals, rapoarte lunare)

### Faza 4: Testare si Training (Saptamanile 4-5)

- [ ] Rulare suita completa de teste pe datele de productie
- [ ] Sesiuni training individualizate per angajat (1-2 ore fiecare)
- [ ] Rulare paralela: Alex + tool-urile existente timp de 1 saptamana
- [ ] Colectare feedback si ajustari
- [ ] Testare email-uri (trimitere oferte reale pe adrese test)
- [ ] Testare rapoarte ASF/BaFin cu date reale

### Faza 5: Go-Live (Saptamana 6)

- [ ] Switch la DNS productie
- [ ] Monitorizare intensiva prima saptamana
- [ ] Suport prioritar 30 de zile
- [ ] Review saptamanal cu echipa brokerului

---

## 5. Ce se Schimba in Cod pentru Productie

### 5.1 Fisiere de Modificat

| Fisier | Ce se Schimba | De Ce |
|--------|--------------|-------|
| Toate `tools/*.py` | `get_db()` → PostgreSQL connection pool | Baza de date productie |
| `shared/db.py` | Conexiune PostgreSQL pentru tabele admin | Tabele admin in productie |
| `seed_db.py` | Adaptat pentru PostgreSQL + import CSV | Date reale |
| `.env` | Toate credentialele de productie | Servicii reale |
| `CLAUDE.md` | Nume real broker, licenta, produse | Personalizare |
| `Dockerfile` | Adauga psycopg2 dependency | Driver PostgreSQL |
| `requirements.txt` | Adauga `psycopg2-binary>=2.9.0` | Driver PostgreSQL |

### 5.2 Variabile de Mediu Productie

```env
# Baza de date
DB_HOST=localhost
DB_NAME=insurance_broker
DB_USER=broker_app
DB_PASS=<parola>

# AI
ANTHROPIC_API_KEY=<cheie productie>
CLAUDE_MODEL=claude-sonnet-4-6

# Email
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASS=<cheie API SendGrid>
SMTP_FROM_NAME=<Numele Companiei Broker>

# Autentificare
CHAINLIT_AUTH_SECRET=<string random 64 caractere>
ADMIN_JWT_SECRET=<string random 64 caractere>

# App
PORT=8080
```

### 5.3 Dependente Noi

Adauga in `requirements.txt`:
```
psycopg2-binary>=2.9.0
```

---

## 6. Intrebari Frecvente Tranzitie

**Q: Pierdem datele demo cand trecem pe real?**
Nu. Demo-ul ramane disponibil cu baza de date SQLite locala. Productia foloseste PostgreSQL separat.

**Q: Cat dureaza migrarea?**
Estimat 4-6 saptamani, depinde de complexitatea datelor existente.

**Q: Putem rula demo si productie in paralel?**
Da. Demo-ul ruleaza local cu SQLite sau pe Cloud Run, productia pe VM cu PostgreSQL.

**Q: Ce se intampla daca API-ul AI e indisponibil?**
Interfata chat ramane accesibila. Documentele generate anterior raman disponibile. Anthropic SLA: 99.9%.

**Q: Putem adauga asiguratori noi dupa go-live?**
Da. Se adauga in tabelul `products` si `insurers` — fie manual prin SQL, fie prin viitorul CRUD in admin panel.

**Q: Preturile din demo sunt reale?**
Nu. Preturile din demo sunt demonstrative. In productie, brokerul configureaza preturile reale per asigurator partener.

---

*Document actualizat: Martie 2026 | Alex Insurance Broker AI v2.0*
