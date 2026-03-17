name: scanart-visual-qa
description: Visual QA for ScanArt frontend. Auto-invoke when user says "visual test", "screenshot test", "verifică UI", "check layout", "QA frontend", "arată cum arată".

# ScanArt Visual QA Skill

Uses MCP Preview tools to screenshot and validate all screens.

## Setup
1. Ensure `.claude/launch.json` has a "frontend" server config serving `frontend/` on port 8765
2. Call `preview_start` with name "frontend"

## Screens to validate

### 1. Landing Screen
- Screenshot at load
- Check: hero text visible, challenge banner, CTA button, filter chips
- If streak ≥ 2: streak badge should show
- If `?ref=` in URL: referral banner should appear

### 2. Camera Screen
- Navigate to camera (click CTA or eval `goToCamera()`)
- Screenshot after camera starts
- Check: video feed area, filter picker at bottom, mode toggle (Animat/Cinemagraph), back button
- If `?challenge=` was in URL: challenge badge should show on camera

### 3. Filter Picker
- Screenshot the filter carousel
- Check: all 30 filters visible on scroll, each has emoji + label + gradient background
- Verify active filter has selection ring

### 4. Trending Page
- Navigate to trending (eval `goToTrending()`)
- Screenshot grid
- Check: items load (not empty), rank badges (#1, #2, #3), period tabs

### 5. Share Page
- Open a real share URL in preview: `{backend_url}/api/share/{known_share_code}`
- Screenshot
- Check: video/GIF plays, OG meta present, CTA button, challenge button

## Report Format
For each screen:
- ✅ / ⚠️ / ❌ status
- Screenshot (already captured)
- Issues found (if any)
- Suggested fixes

## Tools Used
- `preview_start` — start local server
- `preview_screenshot` — capture each screen
- `preview_eval` — navigate between screens, simulate URL params
- `preview_snapshot` — accessibility tree for element verification
