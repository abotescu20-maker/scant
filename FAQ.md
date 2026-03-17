# ScanArt — FAQ & Ghid de Utilizare

## Ce este ScanArt?

ScanArt este o aplicație web PWA (Progressive Web App) care transformă orice fotografie făcută cu camera telefonului într-o operă de artă animată, folosind AI. Utilizatorul poate edita complet promptul artistic generat de AI și regenera cu orice modificare dorește.

**URL:** https://storage.googleapis.com/scanart-frontend-1772986018/index.html
**Backend API:** https://scanart-backend-603810013022.us-central1.run.app

---

## Cum funcționează fluxul de bază?

1. Apasă **📷 Începe să Creezi** pe ecranul principal
2. Selectează un **filtru artistic** din galeria de jos (implicit: Warhol)
3. Alege **modul de animație**: Animat sau Cinemagraph
4. Apasă **butonul shutter** (cercul alb de jos)
5. Așteaptă generarea (~30-60 sec pentru tier Gratuit)
6. Vizualizezi rezultatul animat cu before/after reveal
7. Din **Studio** poți edita promptul și regenera

---

## Filtrele disponibile (10 stiluri artistice)

| Filtru | Emoji | Stil | Animație specifică |
|--------|-------|------|--------------------|
| **Warhol** | 🎭 | Pop Art CMYK, silkscreen | Color grid flash |
| **Hokusai** | 🌊 | Ukiyo-e, gravură japoneză | Valuri ondulante |
| **Klimt** | ✨ | Art Nouveau, aur și mozaic | Shimmer auriu |
| **Ghibli** | 🌿 | Acuarelă animată, Studio Ghibli | Legănare delicată |
| **Banksy** | 🖤 | Street art, stencil negru-alb | Spray drip |
| **Dalí** | 🔮 | Suprarealism, topire | Warp ondulant |
| **Van Gogh** | 🌻 | Impasto, pensulă groasă | Swirl spiralat |
| **Baroque** | 🕯️ | Clar-obscur, Caravaggio | Flicker lumânare |
| **Mondrian** | 🟦 | Geometric, De Stijl | Puls grid |
| **Mucha** | 🌹 | Art Nouveau floral, Mucha | Sway floral |

**Animație inteligentă per subiect:**
- **Față detectată** → MediaPipe FaceMesh → clipit realist (ochi)
- **Plantă/floare** → legănare în vânt (scipy warp)
- **Animal** → respirație + mișcare organică
- **Mâncare** → glow puls cald
- **Obiect generic** → animație vizuală per stil

---

## Modurile de animație

### 🎬 Animat (Life)
Animație naturală bazată pe subiectul detectat + stilul ales. 24 frame-uri, loop infinit.

### 🎞️ Cinemagraph
Fond static cu un singur element în mișcare (mascare Gaussian blur). Efect cinematografic elegant.

**Viteză animație** (doar tier Gratuit, din Studio):
- **Rapid** — 40ms/frame
- **Normal** — 60ms/frame (default)
- **Lent** — 100ms/frame

---

## Nivelurile de calitate

| Tier | Preț | Motor | Durata | Format |
|------|------|-------|--------|--------|
| 🎨 **Gratuit** | $0 | Imagen 3 + animație custom Python | GIF 400×400px, 24fr | .gif |
| ⚡ **Standard** | ~$0.60 | Google Veo 3 Fast | 4 secunde | .mp4 |
| 👑 **Premium** | ~$4 | Google Veo 3 Full HD | 8 secunde | .mp4 |

> **Notă:** Standard și Premium folosesc Veo 3 pe Vertex AI și necesită configurare de billing activă pe proiect.

---

## Studio Panel — Editare Prompt

Accesibil din butonul **✏️ Studio** de pe ecranul de rezultat.

### Prompt Chips (colorate per categorie)
Promptul generat de Gemini este parsat automat în cipuri editabile:

| Culoare | Categorie | Exemplu |
|---------|-----------|---------|
| 🟣 Violet | **Subiect** | "Man with short brown hair" |
| 🔵 Cyan | **Artist** | "reimagined as Andy Warhol silkscreen" |
| 🟡 Auriu | **Tehnică** | "impasto brushstrokes" |
| 🩷 Roz | **Atmosferă** | "bold flat colors, CMYK separation" |

**Cum editezi:** Tap pe orice cip → tastezi direct → buton **🔄 Regenerează**

### Inspire Me ✨
Apasă **Inspire Me** → Gemini generează 3 variante creative ale aceluiași subiect (expresii, unghiuri, atmosfere diferite). Tap pe o variantă → se completează automat în chipuri → se regenerează.

### Surprise 🎲
Adaugă aleator un cuvânt din dicționarul de mood/tehnici (ex: "ethereal glow", "neon accents") la promptul existent.

### Remixuri Rapide (pe ecranul result)
5 butoane de transformare rapidă fără a deschide Studio:

| Remix | Ce face |
|-------|---------|
| 🌙 **Noir** | Adaugă umbră adâncă, fundal negru, chiaroscuro |
| 🔥 **Dramatic** | Contrast extrem, fulgere cinematice |
| 🌸 **Dreamy** | Bokeh soft, culori pastel, ceață eterică |
| ⚡ **Cyber** | Lumini neon RGB, glitch holografic |
| 👑 **Golden** | Aur 24k, amber cald, patină antică |

---

## Galeria Mea

Accesibilă din butonul 🗂️ (camera screen, dreapta jos) sau din orice ecran.

- Grid **2 coloane** cu toate creațiile sesiunii
- Tap pe o creație → se deschide în result + Studio
- **Long-press** (600ms, mobil) → confirmare ștergere

> **Notă:** Galeria este per-sesiune (localStorage `scanart_session_id`). Ștergând cookies/storage, istoricul se pierde.

---

## Share & Descărcare

### 📥 Descarcă
Descarcă GIF-ul sau video-ul local pe dispozitiv.

### 📱 Story
Generează un JPEG **1080×1920px** (format Instagram Stories 9:16) cu:
- Imaginea artistică centrată cu colțuri rotunjite
- Gradient negru jos
- Numele filtrului + primele 120 caractere din prompt
- Watermark "Made with ScanArt"

Dacă browserul suportă `navigator.share` (mobil) → deschide sheet-ul nativ de share. Altfel se descarcă automat.

### 🔗 Share Code
Fiecare creație are un cod de 8 caractere (ex: `2d71af5a`) vizibil în tab-ul **Detalii** din Studio. (Funcționalitate de share link în dezvoltare.)

---

## API Endpoints principale

| Method | Endpoint | Descriere |
|--------|----------|-----------|
| POST | `/api/generate` | Pornește generare nouă (multipart/form-data) |
| GET | `/api/status/{job_id}` | Polling status job (progress 0-100, result) |
| POST | `/api/regenerate` | Regenerare cu prompt personalizat (JSON) |
| POST | `/api/inspire` | Generează 3 variante de prompt (Gemini) |
| POST | `/api/storycard` | Generează JPEG 9:16 pentru Stories |
| GET | `/api/history/{session_id}` | Istoricul creațiilor sesiunii |
| DELETE | `/api/creation/{creation_id}` | Șterge o creație (verificare session_id) |
| GET | `/api/tiers` | Listă tier-uri disponibile |
| GET | `/api/media?url=...` | Proxy media pentru CORS bypass |

---

## Parametrii generării (POST /api/generate)

```
image         : fișier JPEG/PNG (multipart)
style_id      : warhol | hokusai | klimt | ghibli | banksy | dali | vangogh | baroque | mondrian | mucha
quality       : free | standard | premium  (default: standard)
session_id    : string UUID (generat în browser)
animation_mode: life | cinemagraph  (default: life)
frame_delay   : 20-200 ms  (default: 60, doar pentru free)
```

---

## Stack tehnic

### Frontend
- Vanilla JS + CSS, ~1000 linii, single HTML file
- PWA cu Service Worker (`scanart-v11`)
- MediaDevices API pentru cameră
- Hosted pe **Google Cloud Storage** (bucket public)

### Backend
- **FastAPI** (Python 3.12) pe **Cloud Run** (2 CPU, 2GB RAM, timeout 300s)
- **Imagen 3** via Vertex AI (generare imagine artistică, tier free)
- **Gemini 2.0 Flash** via Vertex AI (prompt artistic + variante Inspire Me)
- **Veo 3** via Vertex AI (video generation, tier standard/premium)
- **MediaPipe FaceMesh** (detecție ochi pentru animație clipit)
- **Pillow + NumPy + SciPy** (procesare imagine, animație GIF)
- **OpenCV Headless** (transformări imagine)
- **Firestore** (storage creații per sesiune)
- **Cloud Storage** (GIF-uri, thumbnailuri, video-uri)
- **Cloud Build** (CI/CD Docker build)

### Proiect GCP
- **Project ID:** `gen-lang-client-0167987852`
- **Region:** `us-central1`
- **Cloud Run service:** `scanart-backend`
- **GCS buckets:** `scanart-frontend-1772986018` (frontend), `scanart-results-1772986018` (media)

---

## Întrebări frecvente

**Cât durează generarea?**
- Tier Gratuit: 30-90 secunde (Imagen 3 + animație Python)
- Standard: 2-5 minute (Veo 3 Fast)
- Premium: 5-10 minute (Veo 3 Full HD)

**Se pierd creațiile dacă închid browserul?**
Nu, sunt salvate în Firestore și pot fi accesate din Galerie pe același dispozitiv (aceeași sesiune). Dacă ștergi datele browserului, sesiunea se resetează.

**Pot edita promptul după generare?**
Da, aceasta este funcția distinctivă a ScanArt. Din **Studio → Prompt Chips** poți modifica orice categorie (subiect, artist, tehnică, atmosferă) și apăsa **Regenerează**.

**Ce înseamnă Cinemagraph vs Animat?**
- **Animat**: întreaga imagine are mișcare (swirl, clipit, legănare etc.)
- **Cinemagraph**: fondul e static, doar un element mic se mișcă — efect mai subtil și cinematic.

**Funcționează pe desktop?**
Da, dar este optimizat pentru mobil (fullscreen camera, touch gestures). Pe desktop camera laptop-ului se activează.

**Pot instala ca aplicație?**
Da, este PWA. Pe Safari (iOS): Share → Add to Home Screen. Pe Chrome (Android): meniul browser → Install App.

**De ce thumbnailurile din galerie nu arată opera finală?**
Known issue — thumbnailul curent este din poza capturată brut. Fix în curs de implementare (primul frame din GIF artistic).

---

## Scurtături și gesturi

| Acțiune | Cum |
|---------|-----|
| Schimbă camera față/spate | 🔄 buton dreapta sus pe ecranul cameră |
| Selectează filtru | Tap pe cercul filtrului |
| Schimbă animație | Toggle Animat / Cinemagraph sus |
| Schimbă calitate | Tap badge-ul 🎨 Gratuit (stânga jos) |
| Deschide galeria | 🗂️ buton dreapta jos pe cameră |
| Ștergere din galerie | Long-press 600ms pe item (mobil) |
| Copiază promptul | Tab Detalii → Copiază Promptul |
| Editează un cip | Tap pe cip → tastează inline |

---

*Ultima actualizare: martie 2026 — versiunea scanart-v11*
