from __future__ import annotations
from pydantic import BaseModel, Field

class BetRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    client_seed: str = Field(min_length=1, max_length=128)
    nonce: int = Field(ge=0, le=10_000_000)
    amount: float = Field(gt=0, le=1000)

class CrashBetRequest(BetRequest):
    auto_cashout: float | None = Field(default=None, ge=1.01, le=1000)

class FruitBetRequest(BetRequest):
    rows: int = Field(default=6, ge=3, le=10)
    cols: int = Field(default=5, ge=3, le=8)
