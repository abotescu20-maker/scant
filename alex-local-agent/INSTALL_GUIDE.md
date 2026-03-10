# Alex Agent — Ghid Instalare pentru Angajați

Agentul local Alex rulează în fundal pe calculatorul tău și permite lui Alex (AI-ul) să efectueze
automatizări web direct din conversație.

---

## 📥 Opțiunea A — Executabil (Recomandat, fără Python)

### Windows

1. **Descarcă** `AlexAgent.exe` (primit de la administrator)
2. **Dublu-click** pe `AlexAgent.exe`
3. Se deschide automat **Notepad** cu fișierul de configurare
4. **Completează** API Key-ul primit de la administrator:
   ```json
   {
     "alex_url": "https://insurance-broker-alex-603810013022.europe-west3.run.app",
     "api_key": "CHEIA_TA_API_AICI",
     ...
   }
   ```
5. **Salvează** și închide Notepad
6. **Rulează din nou** `AlexAgent.exe`
7. Apare **iconița verde** în bara de sistem (dreapta jos, lângă ceas) ✅
8. Gata! Alex poate acum automatiza în browser-ul tău.

### Mac

1. **Descarcă** `AlexAgent.zip` (primit de la administrator)
2. **Dezarhivează** → obții `AlexAgent.app`
3. **Click dreapta** → **Open** (prima dată, pentru a ocoli Gatekeeper)
4. Se deschide automat **TextEdit** cu fișierul de configurare
5. **Completează** API Key-ul și salvează
6. **Rulează din nou** `AlexAgent.app`
7. Apare **iconița verde** în bara de meniu (dreapta sus) ✅

---

## 💻 Opțiunea B — Python (pentru cei cu Python instalat)

### Instalare rapidă (3 pași)

```bash
# 1. Instalează dependențele
pip install -r requirements.txt

# 2. Instalează Chromium pentru browser automation
playwright install chromium

# 3. Configurează
python main.py configure
```

### Pornire

```bash
python main.py start
```

Sau cu GUI (system tray):
```bash
python agent_app.py
```

---

## ⚙️ Configurare

Fișierul de configurare se află la:
- **Windows:** `C:\Users\NumeleTau\.alex-agent\config.json`
- **Mac/Linux:** `~/.alex-agent/config.json`

```json
{
  "alex_url": "https://insurance-broker-alex-603810013022.europe-west3.run.app",
  "api_key": "CHEIA_TA_API_AICI",
  "poll_interval": 3,
  "headless_browser": true,
  "gemini_api_key": "",
  "anthropic_api_key": ""
}
```

| Câmp | Descriere |
|------|-----------|
| `alex_url` | URL-ul serverului Alex (nu schimba) |
| `api_key` | Cheia ta API (primită de la administrator) |
| `poll_interval` | Cât de des verifică task-uri (secunde, default 3) |
| `headless_browser` | `true` = browser invizibil, `false` = browser vizibil |
| `gemini_api_key` | (Opțional) pentru automatizare desktop avansată |

---

## 🟢 Cum știi că funcționează?

1. **Iconița verde** apare în bara de sistem / meniu
2. În Alex Chat, scrie: *"verifică dacă agentul e online"*
3. Alex răspunde: *"Agentul local este online și gata."*

---

## ❓ Probleme frecvente

**Iconița nu apare:**
- Windows: verifică bara de sistem extinsă (click pe `^` lângă ceas)
- Mac: iconița apare în bara de meniu (sus dreapta)
- Dacă tot nu apare, rulează din terminal: `AlexAgent.exe headless`

**"API key not set":**
- Deschide fișierul config și completează `api_key`
- Adresează-te administratorului pentru a primi cheia

**Browser-ul nu pornește:**
- Rulează: `playwright install chromium` (o singură dată)
- Sau reinstalează executabilul (include Chromium)

**Agent offline după repornirea calculatorului:**
- Windows: adaugă `AlexAgent.exe` la Startup (Win+R → `shell:startup`)
- Mac: System Preferences → General → Login Items → adaugă `AlexAgent.app`

---

## 📋 Comenzi utile (opțional)

```bash
python main.py status     # vezi starea agentului și conectorii disponibili
python main.py test cedam B123ABC   # testează verificarea RCA direct
python agent_app.py configure       # reconfigurazione interactivă
```

---

## 🔒 Securitate și confidențialitate

- Agentul **nu trimite parole sau date personale** la server
- Toată comunicarea este **HTTPS criptată**
- Agentul execută doar task-uri venite de la Alex (serverul tău intern)
- **Nu accesează** niciun site fără instrucțiune explicită din Alex Chat
- Log-urile se salvează local: `~/.alex-agent/agent.log`

---

*Pentru probleme tehnice, contactează administratorul de sistem.*
