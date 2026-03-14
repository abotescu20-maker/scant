# Alex Agent SDK — Asistentul Autonom de Asigurări

## Ce este Alex Agent SDK?

Alex Agent SDK este un sistem de inteligență artificială care lucrează **automat, 24/7**, fără intervenție umană. Analizează portofoliul de asigurări, detectează riscuri, identifică oportunități și trimite rapoarte profesionale pe email.

**Nou:** Integrări complete cu agentul local (acces la computere și portale), cloud storage (Google Drive + SharePoint) și automatizări n8n.

---

## Ce face în fiecare zi?

### Dimineața (7:30) — Briefing Matinal
Alex trimite un email cu rezumatul zilei:
- Câte polițe sunt active, câte expiră, câte daune sunt deschise
- Ce trebuie făcut AZI (apeluri urgente, documente de trimis)
- Prioritizare automată: RCA obligatoriu mereu primul
- **Status agent local:** dacă agentul de pe desktop e conectat

### De două ori pe zi (8:00 + 14:00) — Monitorizare Reînnoire
- Scanează TOATE polițele din portofoliu
- Alertează brokerul când o poliță se apropie de expirare
- RCA = prioritate maximă (amendă ASF dacă expiră)
- Include: nume client, telefon, email, ce poliță, câte zile mai sunt
- **n8n:** trimite SMS automat pentru RCA-urile care expiră în < 7 zile

### De două ori pe zi (8:15 + 14:15) — Sincronizare Agent Local
- Verifică agentul de pe desktopul brokerului (CEDAM, portale asigurători)
- Dispatch automat verificări RCA prin portalul CEDAM
- Screenshot-uri din portalele Allianz/PAID/Omniasig
- Raport cu rezultatele verificărilor desktop

### Vineri (17:00) — Follow-up Daune
- Verifică toate dosarele de daună deschise
- Flaggează cele întârziate (>14 zile fără răspuns)
- Sugerează acțiuni: "Sună asigurătorul", "Solicită documente"
- Raportează valoarea totală a daunelor în curs
- **n8n:** creează task în CRM pentru daunele depășite

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

### Seara (18:00) — Upload Rapoarte în Cloud
- Încarcă automat toate rapoartele zilei în **Google Cloud Storage** (GCS)
- Linkuri publice HTTPS gata de trimis clienților
- Arhivare automată a tuturor documentelor generate
- Opțional: SharePoint (Microsoft 365) pentru organizații cu M365

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
    DESKTOP BROKER               CLOUD (existent)                 SERVER (nou)
┌─────────────────┐       ┌─────────────────────┐        ┌─────────────────────┐
│ alex-local-agent│       │  Alex Chat (Cloud   │        │  Alex Agent SDK     │
│                 │       │  Run, Frankfurt)    │        │  (GCE VM, €25/lună) │
│ • CEDAM (RCA)   │◄─────►│                     │◄──────►│                     │
│ • PAID portal   │ poll  │  • Chat AI          │  API   │  • 7 task-uri auto  │
│ • Allianz       │       │  • 36 MCP tools     │        │  • Claude Sonnet    │
│ • Excel         │       │  • Admin panel      │        │  • Email SMTP       │
│ • Computer Use  │       │  • Firestore DB     │        │  • Cron jobs 24/7   │
│ • Playwright    │       │  • GCS Upload        │        │  • n8n webhooks     │
└─────────────────┘       │  • SharePoint API   │        │  • Cloud upload     │
                          └─────────────────────┘        └──────────┬──────────┘
                                                                    │ webhook
                                                         ┌──────────▼──────────┐
                                                         │  n8n Workflows      │
                                                         │  • SMS alerting     │
                                                         │  • CRM updates      │
                                                         │  • Slack/Teams      │
                                                         │  • Calendar         │
                                                         └─────────────────────┘
```

### Flux de date:

1. **Agent SDK** (pe server) apelează API-ul Alex (pe Cloud Run) pentru date live
2. **Claude Sonnet** (Anthropic AI) analizează datele și generează rapoarte
3. **Agent local** (pe desktopul brokerului) verifică portalele asigurătorilor
4. **Google Cloud Storage** primește automat rapoartele generate (linkuri publice HTTPS)
5. **n8n** primește evenimente și declanșează acțiuni (SMS, CRM, Slack)
6. **SMTP** trimite rapoartele pe email brokerilor
7. Totul automat, fără intervenție umană

---

## Integrări Disponibile

### Agent Local (Desktop)
Agentul local rulează pe computerul brokerului și poate:
- **CEDAM** — verificare RCA pe baza numărului de înmatriculare
- **PAID portal** — acces la portalul de despăgubiri
- **Allianz** — portal asigurător
- **Playwright** — automatizare browser generic
- **Computer Use** (Anthropic) — operare completă a desktopului

### Cloud Storage
- **Google Cloud Storage (GCS)** — upload automat rapoarte, linkuri publice HTTPS ✅
  - Bucket: `alex-broker-reports` | Region: europe-west3 (Frankfurt)
  - URL rapoarte: `https://storage.googleapis.com/alex-broker-reports/2026-03-14/`
- **SharePoint** — integrare Microsoft 365 (necesită cont organizațional cu admin consent)

### Automatizare n8n
Evenimentele generate automat:

| Eveniment | Când se întâmplă | Ce poate face n8n |
|-----------|------------------|-------------------|
| `renewal-urgent` | RCA expiră în < 7 zile | Trimite SMS brokerului |
| `claim-overdue` | Daună deschisă > 14 zile | Creează task în CRM |
| `compliance-due` | Raport lunar gata | Notifică management |
| `cross-sell-found` | Oportunitate detectată | Adaugă în pipeline vânzări |
| `reports-uploaded` | Rapoarte încărcate în cloud | Trimite link pe Slack |
| `task-failed` | Eroare la orice task | Alertă DevOps |

---

## Cât costă?

| Componentă | Lunar |
|---|---|
| Server Google Cloud (Frankfurt) | ~€23 |
| Claude AI (analiză + rapoarte) | ~€2-15 |
| Google Cloud Storage (GCS) | ~€0.02/GB |
| SharePoint API | Gratuit (inclus în M365) |
| n8n (self-hosted) | Gratuit |
| **Total** | **€25-38/lună** |

**vs. Valoarea generată:**
- Cross-sell identificat: €8.600-€12.400/an potențial
- Polițe salvate de la expirare: evită pierdere clienți
- Compliance automat: evită sancțiuni ASF/BaFin
- Verificări RCA automate: economie timp 2-3h/zi
- Rapoarte cloud: accesibile oricând, de oriunde
- **ROI: 20-40x**

---

## Ce urmează?

### Faza 1 (Acum — Demo) ✅
- ✅ 5 task-uri autonome testate și funcționale
- ✅ 2 task-uri integrare (local agent + cloud upload)
- ✅ n8n webhook pe toate evenimentele
- ✅ Rapoarte HTML pe email
- ✅ Date demonstrative (6 clienți, 24 polițe)
- ✅ Google Cloud Storage funcțional (6/6 rapoarte uploadate)
- ✅ Agent local funcțional (navigate + screenshot confirmate)

### Faza 2 (După validare — Producție)
- Date reale (post-DPA)
- Email SMTP configurat pe domeniul firmei
- Dashboard web pentru vizualizare rapoarte
- SMS pentru alerte urgente (RCA obligatoriu)
- n8n workflows configurate (Twilio, HubSpot, Slack)
- Microsoft OneDrive/SharePoint (necesită cont organizațional cu admin consent)

### Faza 3 (Autonomie completă)
- Agent care răspunde automat la emailuri de la clienți
- Generare oferte automate bazate pe profilul clientului
- Monitorizare prețuri competitori în timp real
- Rapoarte personalizate per broker/echipă
- Multi-agent: orchestrator coordonează mai mulți agenți locali
