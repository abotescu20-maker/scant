# Alex Agent SDK — Asistentul Autonom de Asigurări

## Ce este Alex Agent SDK?

Alex Agent SDK este un sistem de inteligență artificială care lucrează **automat, 24/7**, fără intervenție umană. Analizează portofoliul de asigurări, detectează riscuri, identifică oportunități și trimite rapoarte profesionale pe email.

---

## Ce face în fiecare zi?

### Dimineața (7:30) — Briefing Matinal
Alex trimite un email cu rezumatul zilei:
- Câte polițe sunt active, câte expiră, câte daune sunt deschise
- Ce trebuie făcut AZI (apeluri urgente, documente de trimis)
- Prioritizare automată: RCA obligatoriu mereu primul

### De două ori pe zi (8:00 + 14:00) — Monitorizare Reînnoire
- Scanează TOATE polițele din portofoliu
- Alertează brokerul când o poliță se apropie de expirare
- RCA = prioritate maximă (amendă ASF dacă expiră)
- Include: nume client, telefon, email, ce poliță, câte zile mai sunt

### Vineri (17:00) — Follow-up Daune
- Verifică toate dosarele de daună deschise
- Flaggează cele întârziate (>14 zile fără răspuns)
- Sugerează acțiuni: "Sună asigurătorul", "Solicită documente"
- Raportează valoarea totală a daunelor în curs

### Lunar (1st) — Raport Conformitate ASF/BaFin
- Generează automat raportul lunar pentru autorități
- ASF (România): prime brute, comisioane, polițe intermediate
- BaFin (Germania): activitate pe piața germană
- Verifică conformitatea cu legislația în vigoare

### Luni (10:00) — Oportunități Cross-sell
- Analizează fiecare client: ce are și ce-i lipsește
- Identifică: "SC Logistic are RCA dar nu are CMR" → oportunitate
- Estimează cât ar aduce fiecare vânzare nouă
- Prioritizează: întâi companiile mari, apoi persoanele fizice

---

## Exemple Reale din Testare (14 Martie 2026)

### Alertă Urgentă Detectată
> **Gheorghe Popa** — RCA Omniasig expiră în **3 zile** (18 martie)
> Primă: 1.500 RON | Tel: +40733445566
> **ACȚIUNE:** Sună IMEDIAT pentru reînnoire — risc amendă ASF!

### Daună Întârziată Detectată
> **CLM001 — Andrei Ionescu** — Accident DN1, deschis de **15 zile**
> Estimare: 3.200 RON | Asigurător: Allianz CASCO
> **ACȚIUNE URGENTĂ:** Contactează asigurătorul azi — claim depășește termenul normal

### Oportunitate Cross-sell Detectată
> **SC TechRom SRL** — Companie cu prime de €10.700
> **Lipsă:** CMR și Răspundere Civilă Profesională
> **Potențial:** €2.500-€4.000/an primă nouă
> **ACȚIUNE:** Contactare imediată — companie mare fără protecție

---

## Cum funcționează tehnic?

```
                    CLOUD (existent)                     SERVER (nou)
              ┌─────────────────────┐            ┌─────────────────────┐
              │  Alex Chat (Cloud   │            │  Alex Agent SDK     │
  Brokeri ──► │  Run, Frankfurt)    │◄── API ───►│  (GCE VM, $25/lună) │
              │  - Chat AI          │            │  - Analiză automată │
              │  - 36 MCP tools     │            │  - Rapoarte HTML    │
              │  - Admin panel      │            │  - Email SMTP       │
              │  - Firestore DB     │            │  - Cron jobs 24/7   │
              └─────────────────────┘            └─────────────────────┘
```

1. **Agent SDK-ul** (pe server) apelează API-ul Alex (pe Cloud Run) pentru date live
2. **Claude Sonnet** (Anthropic AI) analizează datele și generează rapoarte
3. **SMTP** trimite rapoartele pe email brokerilor
4. Totul automat, fără intervenție umană

---

## Cât costă?

| Componentă | Lunar |
|---|---|
| Server Google Cloud (Frankfurt) | ~€23 |
| Claude AI (analiză + rapoarte) | ~€2-15 |
| **Total** | **€25-38/lună** |

**vs. Valoarea generată:**
- Cross-sell identificat: €8.600-€12.400/an potențial
- Polițe salvate de la expirare: evită pierdere clienți
- Compliance automat: evită sancțiuni ASF/BaFin
- **ROI: 20-40x**

---

## Ce urmează?

### Faza 1 (Acum — Demo)
- 5 task-uri autonome testate și funcționale
- Rapoarte HTML pe email
- Date demonstrative (6 clienți, 24 polițe)

### Faza 2 (După validare — Producție)
- Date reale (post-DPA)
- Email SMTP configurat pe domeniul firmei
- Dashboard web pentru vizualizare rapoarte
- SMS pentru alerte urgente (RCA obligatoriu)
- Integrare n8n pentru workflow-uri complexe

### Faza 3 (Autonomie completă)
- Agent care răspunde automat la emailuri de la clienți
- Generare oferte automate bazate pe profilul clientului
- Monitorizare prețuri competitori în timp real
- Rapoarte personalizate per broker/echipă
