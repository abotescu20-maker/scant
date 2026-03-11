# Alex — Asistentul AI pentru Brokeri de Asigurari

## Ce este Alex?

Alex este un asistent AI care ajuta angajatii din brokerii de asigurari sa lucreze mai rapid. In loc sa cauti manual in baza de date, in Excel sau in dosare, ii spui lui Alex ce vrei si el face treaba.

Functioneaza ca un chat — scrii ce vrei in limba romana, engleza sau germana, iar Alex raspunde si face actiunea.

**Live demo**: https://insurance-broker-alex-603810013022.europe-west3.run.app

---

## Ce pot face cu Alex?

### Clienti
- **"Cauta-l pe Popescu Ion"** — gaseste clientul instant
- **"Adauga client nou: Maria Dobre, 0722111222"** — il creeaza in baza de date
- **"Ce polite are CLI001?"** — iti arata tot portofoliul clientului
- **"Corecteaza emailul lui Ionescu la andrei@gmail.com"** — editare directa

### Produse si Oferte
- **"Ce produse RCA avem?"** — toate produsele disponibile de la toti asiguratorii
- **"Compara produsele P001 si P002"** — tabel comparativ instant
- **"Fa oferta pentru Popescu cu Allianz RCA"** — genereaza PDF profesional
- **"Trimite oferta pe email"** — oferta ajunge la client direct din chat
- Export: **PDF, XLSX, DOCX** descarcabil direct din chat

### Reinnoiri
- **"Ce polite expira luna asta?"** — dashboard cu tot ce trebuie reinnoit
- **"Ce RCA-uri expira in 7 zile?"** — urgent, clientii risca amenda

### Daune
- **"Inregistreaza dauna: Popescu, accident auto 5 martie"** — dosar deschis
- **"Care e statusul daunei CLM001?"** — urmarire instant

### Rapoarte & Compliance
- **"Fa raportul ASF pentru luna martie"** — raport complet generat automat
- **"Fa raportul BaFin pentru martie"** — piata germana
- **"Verifica dosarul lui CLI001"** — scor compliance 0-100, documente lipsa

### Analize
- **"Ce produse ii lipsesc lui CLI001?"** — cross-sell automat cu bundle recomandat
- **"Cat costa RCA pentru Logan 1.6, sofer 30 ani, clasa B5, Bucuresti?"** — calculator estimativ
- **"Salveaza conversatia asta despre Ionescu"** — istoricul se leaga de client

### Documente
- **Upload orice document** (polita, contract, CI, constatare amiabila) — Alex il citeste automat, extrage datele, creeaza clientul si propune oferta

### Automatizare Browser
- **"Verifica numarul B-123-ABC pe CEDAM"** — verificare RCA in timp real, direct din chat

---

## Istoric Conversatii

Conversatiile cu Alex se salveaza automat si se organizeaza pe numele clientului:

1. Dupa login → dashboard direct (fara meniuri blocante)
2. Daca ai conversatii salvate → apare butonul **"📁 Conversation history by client"**
3. Click → lista clientilor cu conversatii → selectezi clientul → selectezi conversatia → continui de unde ai ramas

---

## Sfaturi rapide

1. **Scrie natural** — "Fa oferta" merge la fel de bine ca orice comanda tehnica
2. **Alex raspunde in limba ta** — romana, engleza sau germana
3. **Dupa oferta** — spune "trimite pe email" si gata
4. **Dimineata** — "ce polite expira saptamana asta?" ca sa nu pierzi reinnoiri
5. **Salvezi o conversatie** — "salveaza conversatia asta despre Ionescu"

---

## Automatizari (API + n8n)

Administratorul poate configura workflow-uri automate:
- **Email zilnic reinnoiri** — `/api/renewals` → n8n → email catre brokeri cu lista urgenta
- **Rapoarte ASF/BaFin** — generate automat pe 1 ale lunii
- **Alerte daune** — `/api/claims/open` → notificare pentru dosare vechi de >14 zile
- **Dashboard extern** — `/api/dashboard` → integrare in alt sistem

---

## Securitate

- Datele clientilor raman in baza de date a brokerului
- CNP-uri si numere de CI NU apar niciodata in raspunsuri
- Fiecare angajat are cont propriu cu parola
- Audit log complet (cine a facut ce si cand)
- Conform GDPR

---

## Dezvoltat de

**Horeca Automation SRL**

Pentru intrebari tehnice sau suport: contacteaza administratorul.
