# Alex — Ghid Comunicare Client
## Ce ii spui clientului despre Alex si cum se integreaza

---

## 1. Pentru Intalnirea Initiala de Demo

### Ce este Alex

Alex este un asistent AI construit special pentru operatiunile de brokeraj de asigurari. Se conecteaza direct la baza de date cu clienti, catalogul de produse si registrul de polite. Angajatii interactioneaza cu el in limbaj natural — in romana, engleza sau germana.

### Ce poate face Alex astazi

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

---

## 2. Cum se Integreaza Alex cu Sistemele Existente

### Arhitectura de Integrare

```
Browser Angajat
    ↓ HTTPS
Google Cloud Run (Frankfurt, EU)
    ├── Alex Chat (Chainlit) — interfata web
    ├── Claude Sonnet (Anthropic) — motorul AI
    ├── 24 Tool-uri Broker — conectate la date
    ├── Admin Panel — management utilizatori
    ├── Agent Local — automatizare desktop/intranet
    └── REST API — pentru automatizari n8n
         ↓
    PostgreSQL (Cloud SQL EU)
    ├── Clienti (importati din CRM)
    ├── Polite (importate/sincronizate)
    ├── Produse (cataloage asiguratori)
    ├── Oferte (generate de Alex)
    └── Daune (inregistrate de brokeri)
```

### Ce API-uri sunt Necesare

| Sistem | Ce Trebuie | Cine Furnizeaza | Cand |
|--------|-----------|-----------------|------|
| Baza de date clienti (CRM) | Acces read la inregistrari clienti | Echipa IT a clientului | Faza 2 (Saptamana 2) |
| Cataloage produse asiguratori | Liste preturi sau acces API | Manageri relatie asiguratori | Faza 2 (Saptamana 2) |
| Server email | Credentiale SMTP | Echipa IT a clientului | Faza 3 (Saptamana 3) |
| Stocare documente | Acces read la polite scanate | Echipa IT a clientului | Faza 3 |
| CEDAM (verificare RCA) | Cheie API | Inregistrare ASF | Faza viitoare |

### Ce Trebuie Furnizat de Client

1. **Export CSV/Excel** al bazei de date curente de clienti (nume, telefon, email, adresa, tip client)
2. **Lista asiguratori parteneri** cu coduri broker si date contact
3. **Credentiale server email** (SMTP host, port, user, parola)
4. **Lista angajatilor** care vor folosi Alex (nume, email, rol)
5. **Logo-ul companiei** pentru oferte branded (PNG/SVG)
6. **Cerinte specifice** de personalizare sau workflow-uri custom

---

## 3. Diferente Demo vs Productie

| Aspect | Demo Mode | Productie |
|--------|-----------|-----------|
| **Date** | 6 clienti sintetici | Toti clientii reali din CRM |
| **Produse** | 10 produse demonstrative | Cataloage reale per asigurator partener |
| **Baza de date** | SQLite (fisier local) | PostgreSQL (Cloud SQL EU, Frankfurt) |
| **Email** | Nu trimite (SMTP neconfigurat) | Trimite efectiv pe email-ul clientului |
| **Verificare RCA** | Doar in baza locala | API CEDAM (cand disponibil) |
| **Autentificare** | Fara login obligatoriu | Login per angajat + control acces (RBAC) |
| **Hosting** | Local sau server demo partajat | Cloud Run dedicat (Frankfurt, GDPR) |
| **Branding** | Generic "Demo Broker" | Numele si logo-ul companiei |
| **Backup** | Nu | Backup zilnic automat (30 zile retentie) |
| **Audit** | Minimal | Log complet: cine a facut ce, cand |
| **SLA** | Fara | 99.5% uptime garantat |

---

## 4. Timeline Migrare Demo → Productie

### Saptamana 1-2: Discovery si Setup
- Mapare workflow-uri curente cu fiecare angajat
- Provisionare infrastructura cloud (GCP Frankfurt)
- Export date clienti din CRM-ul curent
- Provisionare baza de date PostgreSQL

### Saptamana 3-4: Constructie si Configurare
- Import date reale clienti in Alex
- Configurare produse per asigurator partener
- Setup integrare email (SMTP)
- Creare conturi angajati cu permisiuni corespunzatoare
- Configurare n8n workflows (reminder-e reinnoiri, rapoarte lunare)

### Saptamana 5-6: Training si Testare
- Sesiuni training individuale per angajat (1-2 ore)
- Operare paralela: Alex + tool-urile existente timp de 1 saptamana
- Colectare feedback si ajustari
- Testare completa pe date reale

### Saptamana 7: Go-Live
- Switch la productie
- Monitorizare intensiva prima saptamana
- Suport prioritar 30 de zile
- Apeluri review saptamanale

---

## 5. Automatizari n8n — Endpointuri API

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

## 6. Intrebari Frecvente ale Clientului

### "Datele noastre sunt in siguranta?"

- Toate datele stau pe servere Google Cloud in Frankfurt (europe-west3)
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

Da — template-urile de oferte si rapoarte se personalizeaza in Faza 3:
- Logo-ul companiei in PDF-uri
- Text custom in header/footer
- Campuri aditionale specifice fluxului companiei
- Limba implicita per angajat

### "Se poate conecta la CRM-ul nostru?"

Da — in Faza 2 construim conectori custom:
- REST API (orice CRM cu acces API)
- Import CSV/Excel periodic
- Conectare directa la baza de date (PostgreSQL, MySQL, MSSQL)
- Integrari standard: Salesforce, HubSpot, Zoho CRM

---

## 7. Rezumat — Ce ii Spui Clientului

> **Propozitia de valoare in 30 de secunde:**
>
> "Alex este un asistent AI care inlocuieste munca manuala din brokeraj. Angajatii tai vorbesc cu el ca si cum ar vorbi cu un coleg — in romana, engleza sau germana. Alex cauta clienti, compara produse, genereaza oferte profesionale, urmareste reinnoiri, inregistreaza daune si face rapoartele ASF si BaFin — totul din conversatie. Datele raman pe serverul tau in Frankfurt. E gata de folosit azi cu date demo, si in 6 saptamani e pe datele voastre reale."

---

*Document actualizat: Martie 2026 | Alex Insurance Broker AI v2.0*
