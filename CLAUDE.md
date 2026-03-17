# ScanArt — AI Art PWA

## Stack
- **Frontend:** Vanilla JS + CSS (single file: `frontend/index.html`) + `sw.js`
- **Backend:** FastAPI Python 3.12 (`backend/app/`)
- **AI:** Gemini 2.0 Flash (prompt generation), Imagen 3 Fast (free GIF), Veo 3 (paid MP4)
- **Storage:** Firestore (`creations`, `referrals` collections), GCS buckets
- **Deploy:** Cloud Run (backend) + GCS static hosting (frontend)
- **Current version:** v17 (sw.js cache name `scanart-v17`)

## Architecture

```
backend/app/
  api/generate.py      — ALL endpoints: generate, status, share, history, trending, storycard
  services/
    gemini_service.py  — STYLE_INSTRUCTIONS (30 styles), prompt generation via Gemini Vision
    hf_service.py      — free tier: Imagen 3 Fast + NumPy GIF animation (misleading name, no HuggingFace)
    veo_service.py     — paid tier: Veo 3 video generation (standard 4s, premium 8s)
    db_service.py      — Firestore CRUD: creations, referrals, trending
    storage_service.py — GCS upload: video + thumbnail
    share_service.py   — Story card 1080×1920 JPEG generation
  models/schemas.py    — StyleId enum (30 entries), QualityTier, AnimationMode, request/response models
  config.py            — all env vars (GCP project, bucket names, API keys)

frontend/
  index.html           — entire SPA: CSS + HTML + JS inline (~2600 lines)
  sw.js                — service worker (cache version = 'scanart-vXX')
  manifest.json        — PWA manifest

deploy/
  cloudbuild.yaml      — Cloud Build config
  setup.sh             — GCP initial setup script
```

## GCP Resources
- **Project ID:** `gen-lang-client-0167987852`
- **Backend URL:** `https://scanart-backend-603810013022.us-central1.run.app`
- **Frontend URL:** `https://storage.googleapis.com/scanart-frontend-1772986018/index.html`
- **GCS buckets:** `scanart-frontend-1772986018` (static), `scanart-results-1772986018` (media)
- **Container registry:** `gcr.io/gen-lang-client-0167987852/scanart-backend:vXX`

## Deploy workflow

```bash
# Backend — replace vXX with current version:
gcloud builds submit backend/ --tag gcr.io/gen-lang-client-0167987852/scanart-backend:vXX --quiet
gcloud run deploy scanart-backend --image=gcr.io/gen-lang-client-0167987852/scanart-backend:vXX --region=us-central1 --platform=managed --allow-unauthenticated --memory=1Gi --cpu=2 --concurrency=10 --timeout=300 --set-env-vars=GOOGLE_CLOUD_PROJECT=gen-lang-client-0167987852,GCS_BUCKET_NAME=scanart-results --quiet

# Frontend:
gsutil -m rsync -r -d frontend/ gs://scanart-frontend-1772986018
```

## Adding a new artistic style (5 files to edit)
1. `backend/app/models/schemas.py` → add to `StyleId` enum
2. `backend/app/services/gemini_service.py` → add to `STYLE_INSTRUCTIONS` (50-80 words, **technique vocabulary, NOT iconic works**)
3. `backend/app/services/gemini_service.py` → add to `STYLE_MOTION_SUFFIX` (intrinsic medium physics, not subject motion)
4. `frontend/index.html` → add to `FILTERS` array: `{ id, emoji, label, grad: ['#hex','#hex'] }`
5. `frontend/index.html` → add to `FILTER_LOADING_MSGS`: 3 Romanian strings
6. `frontend/sw.js` → bump cache version
7. Deploy both backend + frontend

## Key code patterns

### Job system (in-memory, backend)
```python
_jobs: dict[str, dict] = {}
# Structure: { status: 'queued'|'processing'|'done'|'error', progress: 0-100, result: {...}, error: str }
# BackgroundTask runs _run_generation_pipeline(job_id, ...)
```

### Session (anonymous, frontend)
```js
let sessionId = localStorage.getItem('scanart_session') || crypto.randomUUID();
localStorage.setItem('scanart_session', sessionId);
```

### Firestore creations document
```
creation_id, session_id, style_id, quality, prompt, video_url, thumbnail_url, share_code, created_at
```

### GIF watermark (free tier)
Text `"ScanArt.app"` bottom-right on every frame via PIL ImageDraw. White text + dark shadow.

## Coding conventions
- All frontend JS/CSS is inline in `index.html` — **no bundler, no npm, no build step**
- Python: async FastAPI, `BackgroundTasks` for generation jobs
- `StyleId.hokusai` not `"hokusai"` when referencing styles in Python
- Screens toggle via `showScreen(screenId)` + `.hidden` CSS class
- Share codes: 8-char hex (from `uuid.uuid4().hex[:8]`)

## Gotchas ⚠️
- `sw.js` **MUST be bumped on every deploy** — otherwise users get stale frontend
- `gcloud builds submit` must use `--quiet` flag or it prompts interactively
- GCS env var `GCS_BUCKET_NAME=scanart-results` (WITHOUT the `-1772986018` suffix)
- GCS rsync target IS `scanart-frontend-1772986018` (WITH suffix)
- Veo 3 model name: `"veo-3.0-generate-preview"` (not veo-2)
- `hf_service.py` is misnamed — it uses **Imagen 3 Fast + NumPy**, NOT HuggingFace
- `STYLE_INSTRUCTIONS`: describe **TECHNIQUE** not iconic works (no "Great Wave", no "Starry Night")
- Never use `--config deploy/cloudbuild.yaml` locally — uses `$COMMIT_SHA` which is empty
- `gcloud run deploy` must be a **single line** (no `\` line continuations — they break)

## Viral loop mechanics (v17)
- Share URL includes `?ref={share_code}` → tracked in `referrals` Firestore collection
- `?challenge={style_id}` deep-link → pre-selects filter on camera screen
- Streak: `localStorage['scanart_streak']` + `localStorage['scanart_last_active_date']`
- Share copy: "Am creat [{emoji} {label}] cu ScanArt ✨ → {url}?ref={code}"
- Share page: challenge button "🎯 Poți face asta în alt stil? →" opens challenge deep-link
