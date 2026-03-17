name: scanart-full-style-pipeline
description: Full multi-agent pipeline for adding a new style. Auto-invoke when user says "pipeline stil", "adaugă stil complet", "full style pipeline", "stil cu QA".

# ScanArt Full Style Pipeline (Multi-Agent, Level 8)

Orchestrates 3 parallel agents to add a new style with full QA.

## Input Required
- `style_id`: snake_case identifier (e.g., "pixel_art")
- `label`: Display name (e.g., "Pixel Art")
- `emoji`: Single emoji (e.g., "👾")
- `gradient`: Two hex colors (e.g., ["#00ff88", "#0088ff"])

## Agent 1: Code Agent (runs the scanart-style skill)
Modifies all 5 files:
1. `backend/app/models/schemas.py` → StyleId enum
2. `backend/app/services/gemini_service.py` → STYLE_INSTRUCTIONS + STYLE_MOTION_SUFFIX
3. `frontend/index.html` → FILTERS array + FILTER_LOADING_MSGS
4. `frontend/sw.js` → bump version

**Key rule:** STYLE_INSTRUCTIONS must describe TECHNIQUE not MOTIF.

## Agent 2: Copy Agent (Romanian marketing copy)
Generates in parallel:
- 3 loading messages in Romanian for FILTER_LOADING_MSGS
- Challenge description text (50 chars max)
- Share text variant: "Am transformat o poză în {emoji} {label} cu ScanArt ✨"

## Agent 3: QA Agent (after deploy)
Runs after code changes are deployed:
1. Call `/api/generate` with the new style + a test image
2. Verify generation completes without error
3. Check output GIF has correct watermark
4. Screenshot the filter in the picker carousel
5. Verify share page renders correctly for the new style

## Orchestration Flow
```
┌──────────┐     ┌──────────┐
│ Code     │     │ Copy     │  ← Run in parallel
│ Agent    │     │ Agent    │
└────┬─────┘     └────┬─────┘
     │                │
     └────┬───────────┘
          │
    ┌─────▼─────┐
    │  Deploy   │  ← Sequential (needs code changes)
    │  (release │
    │   skill)  │
    └─────┬─────┘
          │
    ┌─────▼─────┐
    │ QA Agent  │  ← Sequential (needs deployed version)
    └───────────┘
```

## Report
```
Style Pipeline Complete: {emoji} {label}
- Code: 5 files modified ✅
- Copy: 3 loading msgs + challenge desc ✅
- Deploy: v{N} live ✅
- QA: generation OK, watermark OK, share page OK ✅
```
