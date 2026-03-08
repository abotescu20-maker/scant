# Insurance Broker AI Demo Script
## 5-Act Demo — approx. 15 minutes

**Setup:** Open terminal in `~/Desktop/insurance-broker-agent/` and run `claude`

---

## ACT 1 — New Client Intake + Product Search (4 min)

**Broker says:**
```
New client: Andrei Ionescu, phone +40745123456, email andrei.ionescu@gmail.com.
He has a BMW X5 2021, 195kW, wants RCA and CASCO. Check if he's in the system first.
```

**What Claude does (visible):**
1. Calls `broker_search_clients(query="Andrei Ionescu")`
2. Finds CLI001 — already exists! Returns profile with existing policies.
3. Shows: RCA at Generali (active, expires Mar 2026), CASCO at Allianz (active)

**Expected output:**
```
Found client: Andrei Ionescu (CLI001)
Active policies: 2
- RCA: Generali Romania — expires 2026-03-14 (6 days!) ⚠️
- CASCO: Allianz-Tiriac — expires 2026-03-14

⚠️ URGENT: RCA expires in 6 days! Recommend immediate renewal.
```

**Key talking point:** Agent proactively spotted the urgent renewal — ClawdBot doesn't do this.

---

## ACT 2 — Product Comparison + Offer (4 min)

**Broker says:**
```
Great, let's renew his RCA. Search for the best options and compare them, then generate an offer in English.
```

**What Claude does:**
1. Calls `broker_search_products(product_type="RCA", country="RO")`
2. Returns 3 options: Allianz 1847 RON, Generali 1792 RON, Omniasig 1934 RON
3. Calls `broker_compare_products(product_ids="PROD_RCA_ALZ,PROD_RCA_GEN,PROD_RCA_OMA")`
4. Shows comparison table with recommendation
5. Calls `broker_create_offer(client_id="CLI001", product_ids="PROD_RCA_ALZ,PROD_RCA_GEN,PROD_RCA_OMA", language="en", valid_days=30)`

**Expected output:**
```
## RCA Comparison — 3 Insurers

| Criterion        | Allianz-Tiriac | Generali ✅    | Omniasig    |
|------------------|----------------|----------------|-------------|
| Annual Premium   | 1,847 RON      | **1,792 RON**  | 1,934 RON   |
| Deductible       | 0%             | 0%             | 0%          |
| Rating           | AA             | AA             | A+          |

💡 Recommendation: Generali at 1,792 RON — lowest premium, same rating, avg 14-day claims.

✅ Offer OFF-XXXXXXXX generated and saved to output/
```

**Key talking point:** Full comparison + professional offer in 30 seconds. Manual process: 2 hours.

---

## ACT 3 — Renewals Dashboard (2 min)

**Broker says:**
```
What else is expiring in the next 30 days across all our clients?
```

**What Claude does:**
1. Calls `broker_get_renewals_due(days_ahead=30)`
2. Returns prioritized list

**Expected output:**
```
## Policies Expiring in Next 30 Days

### 🔴 URGENT — Expiring within 7 days (2 policies)
| Client          | Type | Insurer  | Expires    | Days Left |
|-----------------|------|----------|------------|-----------|
| Andrei Ionescu  | RCA  | Generali | 2026-03-14 | **6 days**|
| SC Logistic SRL | RCA  | Omniasig | 2026-03-10 | **2 days**|

### 🟡 ATTENTION — Expiring 8-30 days
| Client       | Type  | Insurer | Expires    |
|--------------|-------|---------|------------|
| Maria Popescu| CASCO | Allianz | 2026-06-14 |
...
```

**Key talking point:** Entire portfolio at a glance. No spreadsheet needed.

---

## ACT 4 — Claims Assistance (3 min)

**Broker says:**
```
Maria Popescu just called. She had a parking accident this morning, bumped another car.
She has CASCO at Allianz. Log the claim and tell her what to do.
```

**What Claude does:**
1. Calls `broker_search_clients(query="Maria Popescu")` — finds CLI003
2. Calls `broker_get_client(client_id="CLI003")` — retrieves CASCO policy POL005
3. Calls `broker_log_claim(client_id="CLI003", policy_id="POL005", incident_date="2026-03-08", description="Parking accident - bumped another car. Damage to front bumper.", damage_estimate=2500)`

**Expected output:**
```
✅ Claim CLM-XXXXXX logged

### Next Steps — Allianz-Tiriac Asigurari
1. **Call:** 021 302 71 71 (24/7)
2. **Online portal:** https://www.allianz-tiriac.ro/daune
3. **Avg processing time:** 14 business days
4. **Tip:** Allianz has cashless repair at 300+ workshops. Report online for fastest processing.

### Documents Required
- Identity document
- Policy CASCO-ALZ-2024-112233
- Incident photos (min. 5 angles)
- Amicable accident report (if other driver present)
```

**Key talking point:** Insurer-specific claims guidance. Generic AI gives generic advice.

---

## ACT 5 — ASF Compliance Report (2 min)

**Broker says:**
```
Generate the ASF summary for February 2026.
```

**What Claude does:**
1. Calls `broker_asf_summary(month=2, year=2026)`

**Expected output:**
```
## ASF Monthly Activity Report — 02/2026
Law 236/2018 on Insurance Distribution

### Policies Intermediated This Month
| Insurance Class | ASF Code              | Count | Gross Premium | Commission |
|-----------------|-----------------------|-------|---------------|------------|
| RCA             | A10 — Motor vehicle   |  12   | 23,400 RON    | 2,340 RON  |
| CASCO           | A3 — Land vehicles    |   8   | 48,200 RON    | 5,784 RON  |
| PAD             | A9 — Property damage  |   5   |    450 RON    |    45 RON  |
| TOTAL           |                       |  25   | 72,050 RON    | 8,169 RON  |

Broker authorized under ASF Decision RBK-DEMO-001
```

**Key talking point:** Regulatory report ready in 5 seconds. Normally 2-3 hours manual work.

---

## VS. ClawdBot — Closing Argument

| What We Just Did | ClawdBot | Our Agent |
|---|---|---|
| Spotted urgent renewal automatically | ❌ | ✅ |
| Compared 3 insurers with real prices | ❌ Hallucinated | ✅ Real DB |
| Generated professional offer doc | ❌ | ✅ |
| Claims guidance specific to Allianz | ❌ Generic | ✅ Specific |
| ASF report with correct class codes | ❌ | ✅ |
| Client data stays on YOUR server | ❌ Unknown | ✅ Guaranteed |
| Works for both Romania + Germany | ❌ | ✅ |
| Gemini Vision for scanned docs | ❌ | ✅ (Phase 2) |

---

## Next Steps for Client
1. Sign managed service agreement
2. VM provisioned on Cloud
3. Connect to their real policy data
4. Onboard 2 employees with personalized CLAUDE.md
5. Add Gemini Vision for claims photos and scanned policies
