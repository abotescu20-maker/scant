# Alex — Asistentul AI pentru Brokeri de Asigurari

## Ce este Alex?

Alex este un asistent AI care ajuta angajatii din brokerii de asigurari sa lucreze mai rapid. In loc sa cauti manual in baza de date, in Excel sau in dosare, ii spui lui Alex ce vrei si el face treaba.

Functioneaza ca un chat — scrii ce vrei in limba romana, engleza sau germana, iar Alex raspunde si face actiunea.

## Cum pornesc aplicatia?

1. Deschide browser-ul (Chrome, Firefox, Edge)
2. Acceseaza adresa data de administrator (ex: `https://alex.firma-ta.ro`)
3. Incepe sa scrii — nu ai nevoie de training special

## Ce pot face cu Alex?

### Clienti
- **"Cauta-l pe Popescu Ion"** — gaseste clientul instant
- **"Adauga client nou: Maria Dobre, 0722111222"** — il creeaza in baza de date
- **"Ce polite are CLI001?"** — iti arata tot portofoliul clientului

### Produse si Oferte
- **"Ce produse RCA avem?"** — iti arata toate produsele RCA de la toti asiguratorii
- **"Compara produsele P001 si P002"** — tabel comparativ instant
- **"Fa oferta pentru Popescu cu Allianz RCA"** — genereaza PDF profesional
- **"Trimite oferta pe email"** — oferta ajunge la client direct din chat

### Reinnoiri
- **"Ce polite expira luna asta?"** — dashboard cu tot ce trebuie reinnoit
- **"Ce RCA-uri expira in 7 zile?"** — urgent, clientii risca amenda

### Daune
- **"Inregistreaza dauna: Popescu, accident auto 5 martie"** — dosar deschis
- **"Care e statusul daunei CLM001?"** — urmarire instant

### Rapoarte
- **"Fa raportul ASF pentru luna martie"** — raport complet generat automat
- **"Fa raportul BaFin pentru martie"** — la fel, pentru piata germana
- **"Verifica RCA-ul lui Popescu"** — valabil sau expirat?

### Analize (NOI)
- **"Ce produse ii lipsesc lui CLI001?"** — cross-sell: analizeaza ce are si ce nu are clientul, si sugereaza
- **"Cat ar costa un RCA pentru un Logan 1.6, sofer de 30 ani, Bucuresti, clasa B5?"** — calculator estimativ prima
- **"Verifica dosarul lui CLI001"** — compliance check: scor 0-100, ce documente lipsesc, ce polite expira

### Documente
- **Upload orice document** (polita, contract, CI) — Alex il citeste automat, extrage datele, creeaza clientul si propune oferta

## Sfaturi rapide

1. **Scrie natural** — nu trebuie comenzi speciale. "Fa oferta" merge la fel de bine ca "broker_create_offer"
2. **Alex raspunde in limba ta** — scrii in romana, raspunde in romana. Scrii in germana, raspunde in germana
3. **Dupa oferta** — spune "trimite pe email" si gata, clientul o primeste
4. **Dimineata** — incepe cu "ce polite expira saptamana asta?" ca sa nu pierzi reinnoiri
5. **Daca nu stii ce sa faci** — intreaba-l pe Alex: "ce ar trebui sa fac pentru clientul X?"

## Automatizari (n8n)

Administratorul poate configura:
- **Email automat** cand o polita expira in 7 zile
- **Rapoarte ASF/BaFin** generate automat pe 1 ale lunii
- **Alerte** pentru daune nerezolvate mai vechi de 14 zile
- **Cautare clienti** din alte sisteme (integrare CRM)

Acestea merg in fundal — angajatii nu trebuie sa faca nimic.

## Securitate

- Datele clientilor raman in baza de date a brokerului — NU pleaca pe internet
- CNP-uri si numere de CI NU apar niciodata in raspunsurile lui Alex
- Fiecare angajat are cont propriu cu parola
- Administratorul vede cine a facut ce (audit log)
- Conform GDPR

## Cine a facut Alex?

Dezvoltat de **Horeca Automation SRL**.

Pentru intrebari tehnice sau suport: contacteaza administratorul.
