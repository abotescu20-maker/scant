name: scanart-analytics
description: Run ScanArt analytics queries. Auto-invoke when user says "analytics", "statistici", "stats", "câte creații", "care stiluri", "referral data", "cât de viral".

# ScanArt Analytics Skill

Fetches aggregated analytics from the admin API endpoint.

## Usage

Call the admin stats endpoint:
```bash
curl -s "https://scanart-backend-603810013022.us-central1.run.app/api/admin/stats?key=$ADMIN_API_KEY&days=7"
```

## Available queries (via `days` param)

- `days=1` — last 24h snapshot
- `days=7` — weekly summary (default)
- `days=30` — monthly summary
- `days=365` — yearly summary

## Response format
```json
{
  "period_days": 7,
  "total_creations": 142,
  "style_breakdown": {"ghibli": 45, "warhol": 23, "hokusai": 18, ...},
  "quality_breakdown": {"free": 120, "standard": 15, "premium": 7},
  "referral_count": 12,
  "generated_at": "2026-03-17T..."
}
```

## What to report

Present data in a clear table format:
1. **Total creations** in period
2. **Top 5 styles** by usage (with % of total)
3. **Least used styles** (bottom 5) — candidates for promotion
4. **Referral conversion** — referrals / total as %
5. **Tier distribution** — free vs standard vs premium %
6. **Insight** — one actionable suggestion (e.g., "Promote Byzantine in next challenge — low usage but styles with similar aesthetic have high referral rates")

## Prerequisites
- `ADMIN_API_KEY` env var must be set on Cloud Run
- Endpoint: `GET /api/admin/stats?key=X&days=N`
