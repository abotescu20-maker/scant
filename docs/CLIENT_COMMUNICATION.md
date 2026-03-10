# Alex — Ghid Comunicare Client
## Ce ii spui clientului despre Alex si cum se integreaza

---

## 1. Pentru Intalnirea Initiala de Demo

### Ce este Alex

Alex este un asistent AI construit special pentru operatiunile de brokeraj de asigurari. Se conecteaza direct la baza de date cu clienti, catalogul de produse si registrul de polite. Angajatii interactioneaza cu el in limbaj natural — in romana, engleza sau germana.

Alex nu este un produs generic. Este o platforma agentiva pe care am construit-o bazat pe prospectia noastra despre nevoile unui birou de brokeraj — si pe care o personalizam impreuna cu echipa clientului.

### Ce poate face Alex in pilot

| Domeniu | Ce Face | Exemplu |
|---------|---------|---------|
| **Clienti** | Cauta, creeaza, actualizeaza, sterge profil complet | "Gaseste-l pe Popescu Ion" |
| **Produse** | Cauta, compara side-by-side | "Ce optiuni RCA avem?" |
| **Oferte** | Genereaza documente profesionale | "Fa oferta pentru CLI001 cu Allianz RCA" |
| **Reinnoiri** | Dashboard cu polite care expira | "Ce expira saptamana asta?" |
| **Daune** | Inregistreaza si urmareste | "Maria Popescu a avut un accident azi" |
| **Rapoarte** | ASF (RO) si BaFin (DE) lunare | "Genereaza raportul ASF pentru martie" |
| **Email** | Trimite oferte direct pe email | "Trimite oferta pe email" |
| **Documente** | Citeste si extrage date din scanari | Upload PDF/foto → date automat |
| **Analiza** | Cross-sell, estimare prima, compliance | "Ce produse ii lipsesc lui CLI001?" |
| **Web** | Verifica RCA, navigheza site-uri | "Verifica RCA pentru B123ABC" |
| **Desktop** | Automatizeaza aplicatii locale | "Deschide Excel si scrie..." |

### Ce vede clientul in demo

- 6 clienti demonstrativi cu profile realiste
- 10 produse de asigurare de la 7 asiguratori (RO + DE)
- 8 polite active cu diverse date de expirare
- Toate functiile complet operationale cu date sintetice
- Preturile din demo sunt demonstrative si nu reflecta piata reala

---

## 2. Cum Lucram Impreuna — Cele Doua Faze

### Faza 1 — Pilot MVP: 30 de Zile de Onboarding si Validare

Am construit o platforma agentiva functionala bazata pe prospectia noastra despre nevoile unui birou de brokeraj de asigurari. Faza 1 este un **pilot structurat de 30 de zile** — angajatii folosesc sistemul, noi il rafinam impreuna si identificam exact ce trebuie construit in Faza 2.

**Ce este construit si disponibil pentru pilot:**
- Interfata chat Chainlit in browser — fara instalare pentru angajati
- Claude Sonnet (Anthropic) ca motor AI
- 24 tool-uri broker: gestionare clienti, cautare si comparare produse, generare oferte, dashboard reinnoiri, inregistrare si urmarire daune, rapoarte ASF/BaFin, procesare documente cu Vision AI, automatizare web, automatizare desktop
- MCP server provizoriu cu date demo sintetice
- Admin panel cu control granular per angajat (RBAC)
- Agent local pentru automatizare desktop si intranet
- Deployment pe Google Cloud Run (Frankfurt, conform GDPR)

**Ce se intampla in cele 30 de zile:**
- Fiecare angajat lucreaza cu sistemul pe taskuri zilnice reale — cu date sintetice
- Sesiuni de feedback saptamanale: ce functioneaza, ce nu, ce lipseste
- Ajustam tool-urile, prompts-urile si workflow-urile pe baza feedbackului
- La finalul celor 30 de zile avem o imagine clara si validata despre ce exact se construieste in Faza 2

MVP-ul este fundatia — nu plafonul.

---

### Faza 2 — Implementare Completa: Construita pe Procesele Reale

Dupa validarea MVP cu echipa interna de test, construim sistemul de productie de la zero — pe procesele reale ale clientului, nu pe prospectia noastra.

**Ce include Faza 2:**
- **Mapare procese completa** cu echipa interna — sesiuni cu fiecare angajat, fiecare flux documentat
- **MCP server dedicat** construit pe baza maparii reale — conectat la sistemele lor reale (CRM, baze de date, email, portale asiguratori)
- **Skills custom per rol** — Alex-ul fiecarui angajat configurat pe taskurile si responsabilitatile lui specifice
- **Migrare date reale** — toti clientii, produsele, politele si preturile importate si configurate de broker
- **Training individualizat** — fiecare angajat instruit pe fluxurile lor reale cu date reale
- **Migrare pe VM dedicat pe Google Cloud** — din Cloud Run (prototipare) pe un VM securizat cu baza de date persistenta, performanta constanta si cost predictibil

---

## 3. Cum se Integreaza Alex cu Sistemele Existente

### Arhitectura de Integrare

```
Browser Angajat
    ↓ HTTPS
Google Cloud Run (Frankfurt, EU) — Faza MVP
→ VM dedicat Google Cloud (Frankfurt) — Faza Productie
    ├── Alex Chat (Chainlit) — interfata web
    ├── Claude Sonnet (Anthropic) — motorul AI
    ├── 24 Tool-uri Broker — conectate la date
    ├── Admin Panel — management utilizatori
    ├── Agent Local — automatizare desktop/intranet
    └── REST API — pentru automatizari n8n
         ↓
    SQLite (demo) → PostgreSQL (VM productie)
    ├── Clienti (importati din CRM)
    ├── Polite (importate/sincronizate)
    ├── Produse (cataloage asiguratori)
    ├── Oferte (generate de Alex)
    └── Daune (inregistrate de brokeri)
```

### Ce API-uri sunt Necesare (Faza 2)

| Sistem | Ce Trebuie | Cine Furnizeaza | Cand |
|--------|-----------|-----------------|------|
| Baza de date clienti (CRM) | Acces read la inregistrari clienti | Echipa IT a clientului | Faza 2 |
| Cataloage produse asiguratori | Liste preturi sau acces API | Manageri relatie asiguratori | Faza 2 |
| Server email | Credentiale SMTP | Echipa IT a clientului | Faza 2 |
| Stocare documente | Acces read la polite scanate | Echipa IT a clientului | Faza 2 |
| CEDAM (verificare RCA) | Cheie API | Inregistrare ASF | Faza 2 / Faza viitoare |

### Ce Trebuie Furnizat de Client

**Faza 1 — MVP (inainte de semnarea contractului)**

In Faza 1 lucram exclusiv cu date sintetice. Nu avem nevoie de date reale ale clientilor.

Cerem doar:
1. **Lista angajatilor** care vor participa la pilot (nume, email, rol) — pentru a crea conturi de test
2. **Logo-ul companiei** pentru a personaliza interfata demo (PNG/SVG) — optional
3. **Lista asiguratori parteneri** (nume, tari) — pentru a configura produsele demo relevante

> **GDPR:** In Faza 1 nu procesam date cu caracter personal ale clientilor brokerului. Toate datele sunt sintetice.

---

**Faza 2 — Productie (dupa semnarea contractului si a DPA)**

Dupa ce este semnat contractul de prestari servicii si Data Processing Agreement (DPA):

1. **Export CSV/Excel** cu un esantion reprezentativ de clienti (minim 20-50 inregistrari) pentru validarea importului — **anonim sau pseudoanonimizat** daca este posibil in aceasta etapa
2. **Export complet** al bazei de clienti dupa validarea procesului de import
3. **Lista asiguratori parteneri** cu coduri broker si date contact
4. **Credentiale server email** (SMTP host, port, user, parola)
5. **Cerinte specifice** de personalizare sau workflow-uri custom

> **GDPR:** Importul datelor reale se face exclusiv dupa semnarea DPA. Noi actionam ca **data processor** — clientul ramane **data controller**. Toate datele sunt stocate pe infrastructura clientului (VM Google Cloud Frankfurt, UE).

---

## 4. Diferente Demo vs Productie

| Aspect | Demo (Faza 1 MVP) | Productie (Faza 2) |
|--------|-------------------|--------------------|
| **Date** | 6 clienti sintetici | Toti clientii reali din CRM |
| **Produse** | 10 produse demonstrative | Cataloage reale per asigurator partener |
| **Baza de date** | SQLite (fisier local) | PostgreSQL (VM GCP dedicat, Frankfurt) |
| **Email** | Nu trimite (SMTP neconfigurat) | Trimite efectiv pe email-ul clientului |
| **Verificare RCA** | Doar in baza locala | API CEDAM (cand disponibil) |
| **Autentificare** | Fara login obligatoriu | Login per angajat + control acces (RBAC) |
| **Hosting** | Cloud Run (prototipare) | VM dedicat Google Cloud (Frankfurt, GDPR) |
| **Branding** | Generic "Demo Broker" | Numele si logo-ul companiei |
| **Backup** | Nu | Backup zilnic automat (30 zile retentie) |
| **Audit** | Minimal | Log complet: cine a facut ce, cand |
| **SLA** | Fara | 99.5% uptime garantat |
| **MCP server** | Provizoriu (date demo) | Dedicat (construit pe procesele reale) |

---

## 5. Timeline: MVP → Productie

### Saptamana 1-2: Mapare Procese (Faza 2 incepe)
- Sesiuni individuale cu fiecare angajat — mapare workflow-uri reale
- Documentare completa: intake clienti, reinnoiri, daune, raportare
- Identificare integrari necesare (CRM, email, portale asiguratori)
- Export date clienti din sistemul actual

### Saptamana 3-4: Constructie MCP Server Dedicat
- Constructie MCP server pe baza maparii reale
- Import clienti reali in sistem
- Configurare produse per asigurator partener (preturi reale)
- Setup integrare email (SMTP)
- Configurare VM dedicat Google Cloud

### Saptamana 5-6: Training si Testare
- Sesiuni training individualizate per angajat (1-2 ore)
- Operare paralela: Alex + tool-urile existente timp de 1 saptamana
- Colectare feedback si ajustari
- Testare completa pe date reale

### Saptamana 7: Go-Live pe VM Productie
- Migrare din Cloud Run pe VM securizat Google Cloud
- Monitorizare intensiva prima saptamana
- Suport prioritar 30 de zile
- Apeluri review saptamanale

---

## 6. Automatizari n8n — Endpointuri API

Alex expune endpointuri REST pentru automatizarea workflow-urilor externe via n8n:

| Endpoint | Scop | Exemplu n8n Workflow |
|----------|------|---------------------|
| `GET /api/renewals?days=45` | Polite care expira in N zile | Cron zilnic → reminder email clienti |
| `GET /api/reports/asf?month=3&year=2026` | Raport ASF lunar | Cron pe 1 ale lunii → email compliance |
| `GET /api/reports/bafin?month=3&year=2026` | Raport BaFin lunar | Cron pe 1 ale lunii → email compliance |
| `GET /api/claims/overdue?days=14` | Daune nerezolvate > N zile | Cron saptamanal → alerta manager |
| `GET /api/clients/search?q=Popescu` | Cautare clienti | Lookup din alte aplicatii |

**Toate raspund JSON** si pot fi integrate in orice tool de automatizare (n8n, Zapier, Make, custom scripts).

---

## 7. Intrebari Frecvente ale Clientului

### "Datele noastre sunt in siguranta?"

- Toate datele stau pe servere Google Cloud in Frankfurt (UE)
- Datele nu parasesc Uniunea Europeana
- Conform GDPR Articolul 6 — baza legala pentru procesare documentata
- Semnam Data Processing Agreement (DPA) ca procesator de date
- CNP-urile si numerele de identificare nu sunt niciodata afisate in raspunsuri
- Audit log complet: cine a accesat ce, cand

### "Ce se intampla daca AI-ul greseste?"

Alex este un tool de suport decizional, nu un decision-maker autonom:
- Toate ofertele necesita review uman inainte de trimitere
- Daunele sunt inregistrate dar brokerul verifica inainte de a le trimite la asigurator
- Rapoartele ASF/BaFin sunt draft-uri — compliance officer-ul aproba si trimite oficial
- Alex marcheaza explicit output-urile ca AI-generated si recomanda verificare

### "Pot angajatii diferiti sa aiba accese diferite?"

Da — Admin Panel-ul ofera control granular:
- **Superadmin (MSP):** acces complet, gestioneaza toate companiile si utilizatorii
- **Company Admin:** gestioneaza utilizatorii si permisiunile din compania sa
- **Broker (Agent):** acces doar la tool-urile aprobate de manager

Exemplu: Brokerii juniori pot cauta clienti si polite, dar nu pot crea oferte sau inregistra daune pana cand managerul le activeaza permisiunea.

### "Ce se intampla daca serviciul AI e indisponibil?"

- Alex afiseaza un mesaj de eroare clar in chat
- Interfata Chainlit ramane accesibila
- Toate documentele generate anterior raman disponibile
- Nicio data nu se pierde
- Monitorizarea noastra alerteaza in 5 minute de orice outage

### "Cat costa pe luna?"

Preturile sunt disponibile la cerere. Contactati-ne pentru o oferta personalizata in functie de numarul de angajati si necesitatile specifice.

### "Putem personaliza rapoartele?"

Da — template-urile de oferte si rapoarte se personalizeaza in Faza 2:
- Logo-ul companiei in PDF-uri
- Text custom in header/footer
- Campuri aditionale specifice fluxului companiei
- Limba implicita per angajat

### "Se poate conecta la CRM-ul nostru?"

Da — in Faza 2 construim MCP server-ul dedicat cu conectori custom:
- REST API (orice CRM cu acces API)
- Import CSV/Excel periodic
- Conectare directa la baza de date (PostgreSQL, MySQL, MSSQL)
- Integrari standard: Salesforce, HubSpot, Zoho CRM

### "Este un produs gata sau il construiti de la zero?"

Nici una, nici alta. Am construit deja o platforma agentiva functionala bazata pe prospectia noastra (Faza 1 — MVP). In Faza 2, mapam procesele reale ale companiei impreuna cu echipa interna si construim MCP server-ul dedicat pe baza acestei mapari — nu pe ipoteze. Rezultatul este un sistem care reflecta modul real in care lucreaza compania, nu un tool generic adaptat.

---

## 8. Rezumat — Ce ii Spui Clientului

> **Propozitia de valoare in 30 de secunde:**
>
> "Alex este un asistent AI care inlocuieste munca manuala din brokeraj. Angajatii tai vorbesc cu el ca si cum ar vorbi cu un coleg — in romana, engleza sau germana. Alex cauta clienti, compara produse, genereaza oferte profesionale, urmareste reinnoiri, inregistreaza daune si face rapoartele ASF si BaFin — totul din conversatie.
>
> Nu este un produs off-the-shelf. Am construit deja o platforma agentiva functionala bazata pe prospectia noastra despre nevoile unui birou de brokeraj. Propunem un pilot structurat de 30 de zile — angajatii tai lucreaza cu sistemul pe taskuri zilnice reale, ne spun ce functioneaza si ce lipseste, iar noi rafinam impreuna. Dupa cei 30 de zile stim exact ce trebuie construit in versiunea finala — pe procesele voastre reale, nu pe ipotezele noastre. Datele raman pe serverul vostru in Frankfurt, in UE."

---

*Document actualizat: Martie 2026 | Alex Insurance Broker AI v2.1*
