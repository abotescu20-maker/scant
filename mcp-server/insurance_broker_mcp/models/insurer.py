from pydantic import BaseModel, Field
from typing import Optional


class Insurer(BaseModel):
    id: str
    name: str
    country: str = "RO"
    products: list[str] = []
    rating: str = "A"
    broker_contact: Optional[str] = None


class InsuranceProduct(BaseModel):
    id: str
    insurer_id: str
    insurer_name: str
    product_type: str
    annual_premium: float
    currency: str = "RON"
    insured_sum: Optional[float] = None
    deductible: Optional[str] = None
    coverage_summary: str = ""
    exclusions: Optional[str] = None
    rating: str = "A"
