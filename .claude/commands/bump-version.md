# Bump ScanArt version

Increment the ScanArt version number across all relevant files.

## Steps

1. Ask for new version if not provided (e.g., "v17" → "v18")
2. In `frontend/sw.js`: change `const CACHE = 'scanart-vOLD'` to `const CACHE = 'scanart-vNEW'`
3. In `CLAUDE.md`: update "Current version: vOLD" to "Current version: vNEW"
4. Confirm both changes and show diff
5. Do NOT deploy — just bump the files

## Note
This command only bumps the version. Use /deploy to actually deploy.
