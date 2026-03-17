# Test ScanArt backend

Quick smoke test of the live backend API.

## Steps

Run these curl tests against the production backend:

```bash
# 1. Health check
curl https://scanart-backend-603810013022.us-central1.run.app/health

# 2. Tiers endpoint
curl https://scanart-backend-603810013022.us-central1.run.app/api/tiers

# 3. Trending endpoint
curl "https://scanart-backend-603810013022.us-central1.run.app/api/trending?period=week&limit=5"

# 4. Share page (test with known share code, or "test123" for fallback)
curl -L https://scanart-backend-603810013022.us-central1.run.app/api/share/test123 | head -50
```

## Expected results
- Health: `{"status": "ok"}`
- Tiers: JSON with free/standard/premium data
- Trending: JSON array (may be empty)
- Share: HTML page with fullscreen video layout

Report any 5xx errors or timeouts.
