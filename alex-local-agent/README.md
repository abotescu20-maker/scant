# Alex Local Agent

Agentul local care rulează pe calculatorul angajatului și permite lui Alex să controleze aplicații web și desktop fără API.

---

## Instalare în 3 pași

### Pas 1: Instalare dependințe

```bash
pip install -r requirements.txt
playwright install chromium
```

### Pas 2: Configurare

```bash
python main.py configure
```

Se va cere:
- **Alex URL** — adresa serverului Alex (primită de la administrator)
- **API Key** — cheia ta personală (primită de la administrator)
- **Gemini API Key** — pentru automatizare aplicații desktop (opțional)

### Pas 3: Pornire

```bash
python main.py start
```

Agentul rulează în background și primește comenzi de la Alex automat.

---

## Comenzi disponibile

```bash
python main.py start          # pornește agentul
python main.py configure      # reconfiguarare
python main.py status         # afișează starea și connectorii disponibili
python main.py test cedam B123ABC   # testează verificarea RCA
python main.py test web https://google.com  # testează browser automation
```

---

## Ce poate face

### Browser Automation (orice site web)
- Deschide URL-uri în browser
- Extrage date din tabele web
- Completează formulare web
- Face screenshot

### Desktop Automation (aplicații Windows/Mac)
- Controlează orice aplicație desktop
- Citește ecranul cu Gemini Vision
- Dă click, tastează, navighează în orice aplicație
- Nu necesită API — controlează interfața direct

### Connectors specifici
- **CEDAM** — verificare RCA în timp real
- Mai multe în curând: Allianz Portal, Generali Portal, PAID Pool

---

## Connectors disponibili

| Connector | Descriere | Cerințe |
|-----------|-----------|---------|
| `cedam` | Verificare RCA via portal CEDAM/ASF | Playwright |
| `web_generic` | Orice site web | Playwright |
| `desktop_generic` | Orice aplicație desktop | PyAutoGUI + Gemini API |
| `anthropic_computer_use` | Control AI avansat via Claude | Anthropic API key |

---

## Adăugare connector nou

1. Creați fișierul `connectors/connector_<nume>.py`
2. Implementați `BaseConnector` (metodele: `login`, `extract`, `fill_form`, `screenshot`)
3. Adăugați în `registry.py`
4. Gata — Alex poate folosi conectorul imediat

---

## Securitate

- Agentul se autentifică cu API key-ul personal
- Tot traficul e criptat (HTTPS)
- Parolele aplicațiilor NU sunt stocate local — sunt trimise doar pentru sesiunea curentă
- Agentul rulează doar când e pornit explicit — nu e persistent în background automat

---

## Cerințe sistem

- Python 3.10+
- Windows 10+, macOS 12+, sau Linux cu display
- 500 MB spațiu liber (pentru Playwright Chromium)
- Conexiune internet (pentru comunicare cu Alex și Gemini)
