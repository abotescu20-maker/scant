"""Premium calculator tools — estimate insurance premiums based on risk factors."""
import sqlite3
from pathlib import Path
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
