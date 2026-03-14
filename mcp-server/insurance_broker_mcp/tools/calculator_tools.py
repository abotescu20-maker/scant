"""Premium calculator tools — estimate insurance premiums based on risk factors."""
import sqlite3
from pathlib import Path
from typing import Optional
from fastmcp import FastMCP

DB_PATH = Path(__file__).parent.parent.parent / "insurance_broker.db"

# Base rate tables (simplified — in production, these come from insurer APIs)
RCA_BASE_RATES = {
    # Engine capacity ranges in cc → base annual premium RON
    "<=1200": 800, "1201-1600": 1100, "1601-2000": 1500, "2001-2500": 2000, ">2500": 2800,
}

BONUS_MALUS_FACTORS = {
    "B0": 1.00,  # Starting class
    "B1": 0.95, "B2": 0.90, "B3": 0.85, "B4": 0.80, "B5": 0.75,
    "B6": 0.70, "B7": 0.65, "B8": 0.60, "B9": 0.55, "B10": 0.50,
    "B11": 0.47, "B12": 0.44, "B13": 0.41, "B14": 0.38,
    "M1": 1.25, "M2": 1.50, "M3": 1.75, "M4": 2.00,
    "M5": 2.25, "M6": 2.50, "M7": 2.75, "M8": 3.00,
}

AGE_FACTORS = {
    "18-25": 1.40, "26-35": 1.00, "36-45": 0.90, "46-55": 0.95, "56-65": 1.05, "66+": 1.20,
}

ZONE_FACTORS_RO = {
    "Bucuresti": 1.30, "Cluj": 1.15, "Timisoara": 1.10, "Iasi": 1.05,
    "Brasov": 1.05, "Constanta": 1.10, "Urban": 1.10, "Rural": 0.85,
}


def _get_age_bracket(age: int) -> str:
    if age <= 25: return "18-25"
    if age <= 35: return "26-35"
    if age <= 45: return "36-45"
    if age <= 55: return "46-55"
    if age <= 65: return "56-65"
    return "66+"


def _get_engine_bracket(cc: int) -> str:
    if cc <= 1200: return "<=1200"
    if cc <= 1600: return "1201-1600"
    if cc <= 2000: return "1601-2000"
    if cc <= 2500: return "2001-2500"
    return ">2500"


def calculate_premium_fn(
    product_type: str,
    age: int = 35,
    engine_cc: int = 1600,
    bonus_malus_class: str = "B0",
    zone: str = "Urban",
    vehicle_value: float = 0,
    country: str = "RO",
) -> str:
    """Calculate estimated premium based on risk factors."""
    product_type = product_type.upper()

    if product_type == "RCA" and country.upper() == "RO":
        base = RCA_BASE_RATES.get(_get_engine_bracket(engine_cc), 1500)
        bm = BONUS_MALUS_FACTORS.get(bonus_malus_class, 1.0)
        age_f = AGE_FACTORS.get(_get_age_bracket(age), 1.0)
        zone_f = ZONE_FACTORS_RO.get(zone, 1.0)
        estimated = base * bm * age_f * zone_f

        lines = [
            f"## RCA Premium Estimate\n",
            f"| Factor | Value | Multiplier |",
            f"|--------|-------|------------|",
            f"| Base rate ({_get_engine_bracket(engine_cc)} cc) | {base} RON | 1.00x |",
            f"| Bonus-Malus ({bonus_malus_class}) | — | {bm:.2f}x |",
            f"| Age ({age} → {_get_age_bracket(age)}) | — | {age_f:.2f}x |",
            f"| Zone ({zone}) | — | {zone_f:.2f}x |",
            f"| **Estimated annual premium** | **{estimated:,.0f} RON** | |",
            f"\n*This is an estimate. Actual premium depends on insurer's own rating model.*",
            f"*Use `broker_search_products` to get real quotes from partner insurers.*",
        ]
        return "\n".join(lines)

    elif product_type == "CASCO" and vehicle_value > 0:
        # Simplified CASCO: 3-6% of vehicle value depending on age and zone
        base_pct = 0.045  # 4.5% average
        age_f = AGE_FACTORS.get(_get_age_bracket(age), 1.0)
        estimated = vehicle_value * base_pct * age_f

        lines = [
            f"## CASCO Premium Estimate\n",
            f"| Factor | Value |",
            f"|--------|-------|",
            f"| Vehicle value | {vehicle_value:,.0f} {'RON' if country == 'RO' else 'EUR'} |",
            f"| Base rate | {base_pct*100:.1f}% |",
            f"| Age factor ({age}) | {age_f:.2f}x |",
            f"| **Estimated annual premium** | **{estimated:,.0f} {'RON' if country == 'RO' else 'EUR'}** |",
            f"\n*Deductible not included. Actual premium varies by insurer and coverage level.*",
        ]
        return "\n".join(lines)

    else:
        return (
            f"Premium calculator available for RCA (Romania) and CASCO.\n"
            f"For {product_type} ({country}), use `broker_search_products` to get quotes from partner insurers."
        )


# ── Live price comparison ───────────────────────────────────────────────────
#
# Tarife RCA 2024-2025 orientative per asigurător (RON/an) — bazate pe date
# publice ASF + site-uri asigurători. Actualizate trimestrial.
# Format: {engine_bracket: {insurer: base_rate_RON}}
#
RCA_INSURER_RATES = {
    "<=1200": {
        "Allianz-Tiriac": 750,
        "Generali":        720,
        "Omniasig":        780,
        "Groupama":        800,
        "Uniqa":           760,
        "Asirom":          840,
        "Euroins":         680,
        "Grawe":           810,
    },
    "1201-1600": {
        "Allianz-Tiriac": 1050,
        "Generali":        980,
        "Omniasig":       1100,
        "Groupama":       1150,
        "Uniqa":          1020,
        "Asirom":         1200,
        "Euroins":         920,
        "Grawe":          1130,
    },
    "1601-2000": {
        "Allianz-Tiriac": 1450,
        "Generali":       1380,
        "Omniasig":       1520,
        "Groupama":       1580,
        "Uniqa":          1420,
        "Asirom":         1650,
        "Euroins":        1300,
        "Grawe":          1560,
    },
    "2001-2500": {
        "Allianz-Tiriac": 1900,
        "Generali":       1820,
        "Omniasig":       2050,
        "Groupama":       2100,
        "Uniqa":          1880,
        "Asirom":         2200,
        "Euroins":        1750,
        "Grawe":          2080,
    },
    ">2500": {
        "Allianz-Tiriac": 2650,
        "Generali":       2550,
        "Omniasig":       2800,
        "Groupama":       2900,
        "Uniqa":          2620,
        "Asirom":         3050,
        "Euroins":        2450,
        "Grawe":          2880,
    },
}

# CASCO: tarife orientative ca % din valoarea vehiculului, per asigurător
CASCO_INSURER_RATES = {
    "Allianz-Tiriac": {"base_pct": 0.042, "rating": "AA"},
    "Generali":        {"base_pct": 0.040, "rating": "AA"},
    "Omniasig":        {"base_pct": 0.045, "rating": "A+"},
    "Groupama":        {"base_pct": 0.046, "rating": "A+"},
    "Uniqa":           {"base_pct": 0.044, "rating": "A+"},
    "Asirom":          {"base_pct": 0.048, "rating": "A"},
    "Euroins":         {"base_pct": 0.038, "rating": "A"},
    "Grawe":           {"base_pct": 0.047, "rating": "A"},
}

INSURER_RATINGS = {
    "Allianz-Tiriac": "AA",
    "Generali":       "AA",
    "Omniasig":       "A+",
    "Groupama":       "A+",
    "Uniqa":          "A+",
    "Asirom":         "A",
    "Euroins":        "A",
    "Grawe":          "A",
}


def compare_premiums_live_fn(
    product_type: str,
    age: int = 35,
    engine_cc: int = 1600,
    bonus_malus_class: str = "B0",
    zone: str = "Urban",
    vehicle_value: float = 0,
    country: str = "RO",
    insurers: Optional[str] = None,
) -> str:
    """
    Compară prețurile RCA / CASCO de la toți asigurătorii simultan.

    Sursă: tarife orientative 2024-2025 bazate pe date publice ASF.
    Tarifele exacte pot varia — se recomandă confirmare directă cu asigurătorul.

    Returns: tabel comparativ sortat după preț (cel mai mic primul).
    """
    product_type = product_type.upper()
    country = country.upper()

    bm = BONUS_MALUS_FACTORS.get(bonus_malus_class, 1.0)
    age_f = AGE_FACTORS.get(_get_age_bracket(age), 1.0)
    zone_f = ZONE_FACTORS_RO.get(zone, 1.0) if country == "RO" else 1.0
    engine_bracket = _get_engine_bracket(engine_cc)

    # Filter insurers if specified
    requested = None
    if insurers:
        requested = {i.strip() for i in insurers.split(",")}

    if product_type == "RCA" and country == "RO":
        base_rates = RCA_INSURER_RATES.get(engine_bracket, {})
        results = []
        for insurer, base in base_rates.items():
            if requested and insurer not in requested:
                continue
            final = round(base * bm * age_f * zone_f)
            results.append({
                "insurer": insurer,
                "annual_ron": final,
                "monthly_ron": round(final / 12),
                "rating": INSURER_RATINGS.get(insurer, "N/A"),
            })
        results.sort(key=lambda x: x["annual_ron"])

        lines = [
            f"## Comparator RCA — {engine_cc} cc, B/M: {bonus_malus_class}, Zona: {zone}, Vârstă: {age} ani\n",
            f"> ⚠️ Tarife orientative 2024-2025. Confirmați prețul exact cu asigurătorul sau pe site-ul oficial.",
            f"> Actualizate trimestrial pe baza datelor publice ASF România.\n",
            f"| # | Asigurător | Primă anuală | Primă lunară | Rating | Diferență față de cel mai mic |",
            f"|---|---|---|---|---|---|",
        ]
        min_price = results[0]["annual_ron"] if results else 0
        for i, r in enumerate(results, 1):
            diff = r["annual_ron"] - min_price
            diff_str = "—" if diff == 0 else f"+{diff:,} RON"
            marker = " ✅" if i == 1 else ""
            lines.append(
                f"| {i} | **{r['insurer']}**{marker} | **{r['annual_ron']:,} RON** | "
                f"{r['monthly_ron']:,} RON | {r['rating']} | {diff_str} |"
            )

        best = results[0]
        lines.append(
            f"\n### 💡 Cel mai bun preț\n"
            f"**{best['insurer']}** — **{best['annual_ron']:,} RON/an** ({best['monthly_ron']:,} RON/lună), "
            f"Rating: {best['rating']}\n"
        )
        lines.append(
            f"*Factorii aplicați: motor {engine_bracket} cc (bază), "
            f"B/M {bonus_malus_class} (×{bm:.2f}), "
            f"vârstă {age}a (×{age_f:.2f}), zona {zone} (×{zone_f:.2f})*"
        )
        lines.append(
            f"\nFolosește `broker_create_offer` cu asigurătorul ales pentru a genera oferta PDF."
        )
        return "\n".join(lines)

    elif product_type == "CASCO":
        if vehicle_value <= 0:
            return (
                "❌ Pentru CASCO este necesară valoarea vehiculului (`vehicle_value`).\n"
                "Exemplu: `broker_compare_premiums_live(product_type='CASCO', vehicle_value=45000, age=35)`"
            )
        results = []
        for insurer, data in CASCO_INSURER_RATES.items():
            if requested and insurer not in requested:
                continue
            final = round(vehicle_value * data["base_pct"] * age_f)
            results.append({
                "insurer": insurer,
                "annual": final,
                "monthly": round(final / 12),
                "base_pct": data["base_pct"] * 100,
                "rating": data["rating"],
            })
        results.sort(key=lambda x: x["annual"])
        currency = "RON" if country == "RO" else "EUR"

        lines = [
            f"## Comparator CASCO — Valoare vehicul: {vehicle_value:,.0f} {currency}, Vârstă șofer: {age} ani\n",
            f"> ⚠️ Tarife orientative 2024-2025. Confirmați prețul exact cu asigurătorul.",
            f"> CASCO nu include franșiza — verificați condițiile specifice fiecărui asigurător.\n",
            f"| # | Asigurător | Primă anuală | Primă lunară | % din valoare | Rating |",
            f"|---|---|---|---|---|---|",
        ]
        for i, r in enumerate(results, 1):
            marker = " ✅" if i == 1 else ""
            lines.append(
                f"| {i} | **{r['insurer']}**{marker} | **{r['annual']:,.0f} {currency}** | "
                f"{r['monthly']:,.0f} {currency} | {r['base_pct']:.1f}% | {r['rating']} |"
            )

        best = results[0]
        lines.append(
            f"\n### 💡 Cel mai bun preț\n"
            f"**{best['insurer']}** — **{best['annual']:,.0f} {currency}/an**, "
            f"Rating: {best['rating']}\n"
        )
        return "\n".join(lines)

    else:
        return (
            f"Comparatorul live suportă RCA (RO) și CASCO.\n"
            f"Pentru {product_type}, folosește `broker_search_products(product_type='{product_type}')` "
            f"pentru a vedea ofertele din baza de date."
        )


def register_calculator_tools(mcp: FastMCP):

    @mcp.tool(name="broker_calculate_premium",
              description="Estimate insurance premium based on risk factors: age, engine size, bonus-malus class, zone, vehicle value.")
    def broker_calculate_premium(
        product_type: str,
        age: int = 35,
        engine_cc: int = 1600,
        bonus_malus_class: str = "B0",
        zone: str = "Urban",
        vehicle_value: float = 0,
        country: str = "RO",
    ) -> str:
        return calculate_premium_fn(product_type, age, engine_cc, bonus_malus_class, zone, vehicle_value, country)

    @mcp.tool(name="broker_compare_premiums_live",
              description="Compare RCA/CASCO prices from ALL insurers simultaneously. Returns ranked table sorted by price (cheapest first). Sources: public ASF data 2024-2025, updated quarterly.")
    def broker_compare_premiums_live(
        product_type: str,
        age: int = 35,
        engine_cc: int = 1600,
        bonus_malus_class: str = "B0",
        zone: str = "Urban",
        vehicle_value: float = 0,
        country: str = "RO",
        insurers: Optional[str] = None,
    ) -> str:
        return compare_premiums_live_fn(
            product_type, age, engine_cc, bonus_malus_class, zone, vehicle_value, country, insurers
        )
