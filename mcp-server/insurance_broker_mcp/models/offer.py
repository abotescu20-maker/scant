from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class OfferCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    client_id: str
    product_ids: list[str] = Field(..., min_length=1, max_length=10)
    language: str = Field(default="en", description="Output language: en, ro, de")
    valid_days: int = Field(default=30, ge=1, le=90, description="Offer validity in days")
    notes: Optional[str] = Field(None, max_length=500, description="Custom broker notes")
    format: str = Field(default="pdf", description="Output format: pdf, text")


class Offer(BaseModel):
    id: str
    client_id: str
    created_at: str
    valid_until: str
    status: str = "sent"
    file_path: Optional[str] = None
    products_count: int = 0
