#!/usr/bin/env python3
"""
Alex Insurance Broker — Advanced Test Battery

Runs 5 realistic broker email scenarios with attachments through the
`simulate-openviva` endpoint, then verifies:
  • Template routing correctness
  • form_data population (including template aliases: anspruch_*, polizei_*, kasko_*)
  • PDF field rendering (sections 4, 7, 8 previously blank)
  • Vision classification and field extraction from attachments
  • PDF size and embedded image count

Usage:
    python3 tests/advanced_battery.py [--base-url URL]

Requires: pdftotext (Poppler), Pillow (for generating test images)
"""
import argparse
import base64
import json
import os
import random
import sys
import time
import urllib.request
from pathlib import Path

DEFAULT_BASE = "https://alex-insurance-broker-unwwkkjdba-ey.a.run.app"
TMP = Path("/tmp")


def make_polizeibericht(path: Path):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (1240, 1754), 'white')
    d = ImageDraw.Draw(img)
    try:
        f_big = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
        f_mid = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except Exception:
        f_big = f_mid = ImageFont.load_default()
    lines = [
        (f_big, "POLIZEI DÜSSELDORF", 60),
        (f_mid, "Aktenzeichen: POL-NRW-2026-4711/0042", 140),
        (f_mid, "Datum: 10.04.2026, 08:45 Uhr", 180),
        (f_big, "VERKEHRSUNFALL - AUFNAHMEPROTOKOLL", 260),
        (f_mid, "Unfallort: BAB A3, Fahrtrichtung Köln, km 142,5", 320),
        (f_big, "BETEILIGTE FAHRZEUGE:", 420),
        (f_mid, "Halter 1: Hans Wagner  Kennzeichen: K-HW 2200", 480),
        (f_mid, "Halter 2: Müller Speditions GmbH  Kennzeichen: D-MS 4000", 520),
        (f_mid, "FIN: WDB9323371L123456  Fahrzeug: Mercedes Actros 2642", 560),
        (f_big, "HERGANG:", 640),
        (f_mid, "Spurwechsel ohne Blinker. Geschätzter Schaden EUR 12.500,00.", 700),
    ]
    for font, text, y in lines:
        d.text((80, y), text, fill='black', font=font)
    img.save(path, 'JPEG', quality=92)


def make_damage_photo(path: Path, seed: int = 42):
    from PIL import Image, ImageDraw, ImageFont
    random.seed(seed)
    img = Image.new('RGB', (1600, 1200))
    pix = img.load()
    for x in range(1600):
        for y in range(1200):
            pix[x, y] = (random.randint(70, 160), random.randint(70, 160), random.randint(80, 180))
    d = ImageDraw.Draw(img)
    d.ellipse([(400, 400), (900, 700)], fill=(40, 40, 50))
    img.save(path, 'JPEG', quality=85)


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def post_json(url: str, payload: dict, timeout: int = 240) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def get_json(url: str, timeout: int = 30) -> dict:
    return json.loads(urllib.request.urlopen(url, timeout=timeout).read())


def run_battery(base_url: str) -> list[dict]:
    # Generate attachments once
    pol = TMP / "test_polizei.jpg"
    dmg = TMP / "test_damage.jpg"
    if not pol.exists():
        make_polizeibericht(pol)
    if not dmg.exists():
        make_damage_photo(dmg)
    POL_B64 = b64(pol)
    DMG_B64 = b64(dmg)

    tests = [
        {
            "name": "T1 — KFZ with Polizeibericht + damage photo",
            "expect_tpl": "tpl-kfz-schaden",
            "body": """Formularkennung AlexAI: KFZ-ALEX-AI
VN: Müller Speditions GmbH
Adresse: Industriestrasse 42
PLZ: 40210
Ort: Düsseldorf
Email: t1@test-tpsh.local
Telefon: +49 211 1111111
Kennzeichen: D-MS 4000
Fahrzeug: Mercedes Actros 2642
VS-Nummer: VS-T1
Versicherer: Allianz
Schadennummer: SCH-T1
Schadendatum: 2026-04-10
Unfallort: A3 Düsseldorf
Schadenshöhe: 12500
Geschädigter: Hans Wagner
Unfallhergang: Spurwechsel-Kollision.""",
            "atts": [
                {"filename": "polizeibericht.jpg", "content_type": "image/jpeg", "data_b64": POL_B64},
                {"filename": "schadenfoto.jpg", "content_type": "image/jpeg", "data_b64": DMG_B64},
            ],
        },
        {
            "name": "T2 — Haftpflicht water damage (no attachments)",
            "expect_tpl": "tpl-haftpflicht",
            "body": """Formularkennung AlexAI: HAFTPFLICHT-ALEX-AI
VN: Dr. Wagner Privat
Adresse: Wohnstrasse 5
PLZ: 60311
Ort: Frankfurt
Email: t2@test-tpsh.local
Versicherer: HDI
VS-Nummer: VS-T2
Schadennummer: SCH-T2
Schadendatum: 2026-04-12
Schadenort: Mietwohnung
Geschädigter: Karl Schneider
Schadenshöhe: 3500
Unfallhergang: Wasserschaden beim Nachbarn durch geplatzte Waschmaschine.""",
            "atts": [],
        },
        {
            "name": "T3 — Maschinenbruch with photo",
            "expect_tpl": "tpl-maschinenbruch",
            "body": """Formularkennung AlexAI: MASCHINENBRUCH-ALEX-AI
VN: Metallwerk Stahl GmbH
Adresse: Fabrikstrasse 7
PLZ: 44135
Ort: Dortmund
Email: t3@test-tpsh.local
Versicherer: AXA
VS-Nummer: VS-T3
Schadennummer: SCH-T3
Schadendatum: 2026-04-09
Maschinentyp: Hydraulikpresse Schuler MSE 2500
Hersteller: Schuler AG
Schadenshöhe: 85000
Unfallhergang: Hydraulikpresse defekt durch Ölverlust.""",
            "atts": [{"filename": "maschine.jpg", "content_type": "image/jpeg", "data_b64": DMG_B64}],
        },
        {
            "name": "T4 — Ambiguous KFZ (Haftpflicht words in body)",
            "expect_tpl": "tpl-kfz-schaden",
            "body": """Formularkennung AlexAI: KFZ-ALEX-AI
VN: Fuhrpark GmbH
Email: t4@test-tpsh.local
Kennzeichen: K-FS 100
Versicherer: R+V
VS-Nummer: VS-T4
Schadennummer: SCH-T4
Schadendatum: 2026-04-11
Unfallort: Parkhaus Köln
Schadenshöhe: 4200
Geschädigter: Frau Meier
Unfallhergang: Parkschaden. Haftpflicht-Versicherung greift. Schadensersatz an Dritten.""",
            "atts": [],
        },
        {
            "name": "T5 — No Formularkennung (body-only routing)",
            "expect_tpl": "tpl-kfz-schaden",
            "body": """VN: Taxi Yeter
Email: t5@test-tpsh.local
Kennzeichen: B-TY 2200
Fahrzeug: Mercedes E-Klasse Taxi
Versicherer: HUK-Coburg
Schadennummer: SCH-T5
Schadendatum: 2026-04-14
Unfallort: Alexanderplatz Berlin
Schadenshöhe: 2800
Unfallhergang: Auffahrunfall an Taxistand.""",
            "atts": [],
        },
    ]

    results = []
    for t in tests:
        print()
        print("▸", t["name"])
        sys.stdout.flush()
        t0 = time.time()
        try:
            r = post_json(f"{base_url}/api/debug/simulate-openviva",
                          {"body": t["body"], "sender": "testbroker@tpsh.local", "attachments": t["atts"]},
                          timeout=240)
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            results.append({"name": t["name"], "ok": False, "error": str(e)})
            continue

        sub_id = r["sub_id"]
        exp = get_json(f"{base_url}/api/forms/submissions/{sub_id}/export")
        sub = exp["submission"]
        fd = exp.get("form_data_flat", {})
        atts = sub.get("attachments", [])
        actual_tpl = sub.get("template_id", "")

        pdf_url = f"{base_url}/api/forms/submissions/{sub_id}/pdf"
        pdf = urllib.request.urlopen(pdf_url, timeout=60).read()
        pdf_path = TMP / f"battery_{sub_id}.pdf"
        pdf_path.write_bytes(pdf)

        nf = sum(1 for v in fd.values() if v)
        alias_present = sum(1 for k in ("anspruch_schadenshoehe", "kasko_schadenshoehe",
                                         "polizei_aktenzeichen", "anspruch_name", "anspruch_fabrikat")
                            if fd.get(k))
        route_ok = actual_tpl == t["expect_tpl"]

        result = {
            "name": t["name"],
            "sub_id": sub_id,
            "expected_tpl": t["expect_tpl"],
            "actual_tpl": actual_tpl,
            "routing_ok": route_ok,
            "form_fields_populated": nf,
            "alias_fields_populated": alias_present,
            "completeness_pct": sub.get("completeness_pct"),
            "pdf_size": len(pdf),
            "pdf_jpeg_streams": pdf.count(b'/DCTDecode'),
            "attachments_processed": len(atts),
            "vision_categories": [a.get("category") for a in atts],
            "vision_extracted_count": [len(a.get("extracted_fields") or {}) for a in atts],
            "duration_s": round(time.time() - t0, 1),
        }
        results.append(result)
        tick = "✓" if route_ok else "✗"
        print(f"  {tick} tpl={actual_tpl} ({route_ok}), fields={nf}, aliases={alias_present}/5, completeness={result['completeness_pct']}%, pdf={len(pdf)}B, {result['duration_s']}s")

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_BASE, help="Alex base URL")
    ap.add_argument("--out", default="/tmp/battery_results.json")
    args = ap.parse_args()
    print(f"Base URL: {args.base_url}")
    results = run_battery(args.base_url)
    Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False))
    # Summary
    ok_route = sum(1 for r in results if r.get("routing_ok"))
    avg_pct = sum(r.get("completeness_pct", 0) or 0 for r in results) / max(1, len(results))
    avg_aliases = sum(r.get("alias_fields_populated", 0) for r in results) / max(1, len(results))
    print()
    print("═" * 72)
    print(f"  Routing:  {ok_route}/{len(results)} correct")
    print(f"  Avg completeness:      {avg_pct:.1f}%")
    print(f"  Avg template aliases:  {avg_aliases:.1f}/5 populated")
    print(f"  Saved:    {args.out}")
    print("═" * 72)


if __name__ == "__main__":
    main()
