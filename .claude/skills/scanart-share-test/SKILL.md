name: scanart-share-test
description: End-to-end test for the viral share loop. Auto-invoke when user says "test share", "testează viral", "test referral", "share page OK?".

# ScanArt Share Test Skill

Validates the complete viral share loop end-to-end.

## Steps

### 1. Get a real share code
```bash
curl -s "https://scanart-backend-603810013022.us-central1.run.app/api/trending?period=week&limit=1" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['share_code'])"
```

### 2. Test share page HTML
```bash
SHARE_CODE=<from step 1>
curl -s "https://scanart-backend-603810013022.us-central1.run.app/api/share/$SHARE_CODE"
```

Validate response contains:
- `og:title` meta tag
- `og:image` meta tag with valid URL
- `og:video` or video element
- CTA link with `?ref=$SHARE_CODE`
- Challenge button with `?challenge=` param

### 3. Test referral flow (via Preview tools)
1. Open share page in browser preview
2. Click CTA button
3. Verify landing page loads with `?ref=` in URL
4. Check that `scanart_ref_source` is set in localStorage
5. Check that referral banner appears

### 4. Test challenge deep-link
1. Navigate to `frontend/?challenge=warhol&ref=abcd1234`
2. Verify `window._pendingChallenge` is set to "warhol"
3. Navigate to camera
4. Verify challenge badge appears with "Challenge: Warhol Pop Art"

## Pass/Fail Criteria
- ✅ Share page renders with all OG tags
- ✅ CTA link includes `?ref={share_code}`
- ✅ Challenge button links to app with `?challenge=` + `?ref=`
- ✅ Referral banner shows on landing when `?ref=` present
- ✅ Challenge auto-selects filter on camera screen
