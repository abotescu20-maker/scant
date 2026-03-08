from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from typing import Optional


class PolicyType(str, Enum):
    RCA = "RCA"                          # Mandatory motor TPL (Romania)
    CASCO = "CASCO"                      # Comprehensive motor
    PAD = "PAD"                          # Mandatory home (disaster zones, Romania)
    HOME = "HOME"                        # Optional home/property
    LIFE = "LIFE"                        # Life insurance
    HEALTH = "HEALTH"                    # Health insurance
    CMR = "CMR"                          # Road freight liability
    LIABILITY = "LIABILITY"              # General / professional liability
    KFZ = "KFZ"                          # German motor (Kfz-Haftpflicht)
    GEBAEUDE = "GEBAEUDE"                # German building insurance
    BERUFSUNFAEHIGKEIT = "BERUFSUNFAEHIGKEIT"  # Disability (Germany)
    TRANSPORT = "TRANSPORT"              # Cargo / transport


class PolicyStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"
    SUSPENDED = "suspended"


class PolicyBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    client_id: str = Field(..., description="Client UUID")
    policy_type: PolicyType
    insurer: str = Field(..., description="Insurer name e.g. 'Allianz-Tiriac'")
    policy_number: str = Field(..., description="Policy number")
    start_date: str = Field(..., description="Policy start date YYYY-MM-DD")
    end_date: str = Field(..., description="Policy end date YYYY-MM-DD")
    annual_premium: float = Field(..., description="Annual premium amount", ge=0)
    insured_sum: Optional[float] = Field(None, description="Insured sum")
    currency: str = Field(default="RON", description="Currency: RON, EUR")
    installments: int = Field(default=1, description="Number of installments", ge=1, le=12)
    broker_commission_pct: Optional[float] = Field(None, description="Broker commission %")


class PolicyCreate(PolicyBase):
    pass


class Policy(PolicyBase):
    id: str
    status: PolicyStatus
    days_to_expiry: Optional[int] = None
    broker_commission_eur: Optional[float] = None
