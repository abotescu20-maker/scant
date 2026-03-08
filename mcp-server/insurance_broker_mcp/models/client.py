from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import Optional
from datetime import datetime


class ClientBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(..., description="Full name or company name", min_length=2)
    id_number: Optional[str] = Field(None, description="CNP (individuals) or CUI (companies) or DE Steuernummer")
    phone: str = Field(..., description="Phone number e.g. '+40721234567' or '+4915112345678'")
    email: Optional[str] = Field(None, description="Email address")
    address: Optional[str] = Field(None, description="Full address")
    client_type: str = Field(default="individual", description="'individual' or 'company'")
    country: str = Field(default="RO", description="Country code: RO or DE")
    source: Optional[str] = Field(None, description="Lead source: referral, website, walk-in, phone")
    notes: Optional[str] = Field(None, description="Broker notes about the client")


class ClientCreate(ClientBase):
    pass


class Client(ClientBase):
    id: str
    created_at: str
    active_policies_count: int = 0
    total_premium_eur: float = 0.0
