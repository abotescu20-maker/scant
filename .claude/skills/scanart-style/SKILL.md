---
name: scanart-style
description: Add a new artistic style/filter to ScanArt. Auto-invoke when user says "adaugă stil", "add style", "new filter", "filtru nou", "mai adaugă un stil", "adaugă un filtru", "vreau stilul X".
allowed_tools: Read, Edit, Glob, Grep
---

# ScanArt New Style Skill

## Core principle: TECHNIQUE over MOTIF

Style instructions must describe HOW the medium is applied — NOT reference iconic works.

| ❌ NEVER | ✅ ALWAYS |
|----------|----------|
| "The Great Wave energy" | "variable-width ink outlines, bokashi wet-bleed gradation" |
| "Starry Night movement" | "directional impasto marks, paint ridge micro-shadows" |
| "Persistence of Memory" | "hyperrealistic precision, physical laws subtly violated" |
| "Portrait of Adele style" | "naturalistic face + flat geometric mosaic on all garments" |

## Files to modify (in order)

### 1. `backend/app/models/schemas.py`
Add to `StyleId` enum:
```python
new_style_id = "new_style_id"
```

### 2. `backend/app/services/gemini_service.py` — STYLE_INSTRUCTIONS
Add entry (50-80 words, technique vocabulary):
```python
StyleId.new_style_id: (
    "Transform using [movement/artist]'s [medium] technique. "
    "[HOW material is applied — brush direction, ink weight, dot size, carving direction]. "
    "[Color palette — specific pigment names, max 5-6 colors]. "
    "[What is ABSENT — no gradients / no shadows / no organic curves / etc.]. "
    "[Surface texture — paper grain, canvas weave, plate reflectivity]. "
    "[The defining visual tension or formal principle of this style]."
),
```

### 3. `backend/app/services/gemini_service.py` — STYLE_MOTION_SUFFIX
Add entry (intrinsic medium physics):
```python
StyleId.new_style_id: "[medium physical action — ink spreading, tessera rotating, toner degrading], "
                      "[second medium action] in a seamless loop",
```

### 4. `frontend/index.html` — FILTERS array
```js
{ id: 'new_style_id', emoji: '🎨', label: 'Style Name', grad: ['#hex1','#hex2'] },
```

### 5. `frontend/index.html` — FILTER_LOADING_MSGS
```js
new_style_id: ['Mesaj 1...', 'Mesaj 2...', 'Mesaj 3 gata!'],
```
(3 Romanian strings, progressive: in progress / almost done / done!)

### 6. `frontend/sw.js`
Bump `const CACHE = 'scanart-vXX'` to next version.

## Gradient color guidelines
- `grad` should reflect the style's dominant palette
- Use 2 hex colors: [darkest accent, lightest accent]
- Examples: Hokusai `['#0a3d6b','#c8e8f8']`, Warhol `['#ff0080','#ffff00']`

## STYLE_MOTION_SUFFIX guidelines
- Describe the PHYSICS OF THE MEDIUM animating, not the subject moving
- Good: "ink contour lines redrawing themselves" / "tessera tiles rotating fractionally"
- Bad: "waves flowing" / "figure dancing" / "clouds moving"

## After adding
Remind user to deploy both backend AND frontend (style is in both places).
