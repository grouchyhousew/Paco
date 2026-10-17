"""FastAPI surface for the SavanaWin Telegram Mini App."""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Annotated

from config.config import BOT_TOKEN

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import TelegramAuthError, validate_init_data
from .games import crash_point, fruit_round, new_seed
from .ledger import InsufficientFunds, init_ledger, reserve_stake, settle_stake, refund_stake, connection, get_round_by_key
from .schemas import BetRequest, CrashBetRequest, FruitBetRequest

app = FastAPI(title="SavanaWin Mini App API", version="0.2.0")

FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


class SeedRequest(BaseModel):
    client_seed: str = Field(min_length=1, max_length=128)
    nonce: int = Field(ge=0, le=10_000_000)


@app.on_event("startup")
def startup() -> None:
    init_ledger()


def current_user(x_telegram_init_data: Annotated[str | None, Header()] = None) -> dict:
    try:
        return validate_init_data(x_telegram_init_data or "", BOT_TOKEN)
    except TelegramAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def cents(amount: float) -> int:
    return int(round(amount * 100))


def fail_ledger(exc: Exception) -> None:
    if isinstance(exc, InsufficientFunds):
        raise HTTPException(status_code=409, detail="insufficient funds") from exc
    raise HTTPException(status_code=422, detail=str(exc)) from exc


def request_fingerprint(request: BetRequest) -> str:
    payload = json.dumps(request.model_dump(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def create_round(user_id: int, game: str, request: BetRequest, seed: str, commit: str, result: dict, payout_cents: int) -> str:
    round_id = uuid.uuid4().hex
    with connection() as conn:
        conn.execute(
            "INSERT INTO web_game_rounds "
            "(id,user_id,game,status,stake_cents,payout_cents,commit_hash,server_seed,client_seed,nonce,result_json,idempotency_key,request_fingerprint) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (round_id, user_id, game, "settled", cents(request.amount), payout_cents, commit, seed,
             request.client_seed, request.nonce, json.dumps(result, ensure_ascii=False), request.idempotency_key, request_fingerprint(request)),
        )
    return round_id


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="frontend build is missing")
    return FileResponse(index)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "savanawin"}


@app.get("/api/me")
def me(user: Annotated[dict, Depends(current_user)]) -> dict:
    return {"id": user["id"], "username": user.get("username"), "first_name": user.get("first_name")}


@app.get("/api/wallet")
def wallet(user: Annotated[dict, Depends(current_user)]) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user["id"],)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="user not found")
    return {"balance": round(float(row[0]), 2), "currency": "USD"}


@app.get("/api/games")
def games(user: Annotated[dict, Depends(current_user)]) -> dict:
    return {"brand": "SavanaWin", "games": [
        {"id": "crash", "name": "Crash", "status": "beta", "house_edge": 0.04},
        {"id": "fruit-fall", "name": "Fruit Fall", "status": "beta", "house_edge": 0.04},
    ]}


@app.post("/api/fairness/seed")
def fairness_seed(request: SeedRequest, user: Annotated[dict, Depends(current_user)]) -> dict:
    seed, commit = new_seed()
    return {"commit": commit, "client_seed": request.client_seed, "nonce": request.nonce,
            "note": "The server seed is revealed with the settled round."}


@app.post("/api/games/crash/play")
def crash_play(request: CrashBetRequest, user: Annotated[dict, Depends(current_user)]) -> dict:
    key = f"web:crash:{user['id']}:{request.idempotency_key}"
    existing = get_round_by_key(user["id"], "crash", key)
    if existing:
        if existing["request_fingerprint"] != request_fingerprint(request):
            raise HTTPException(status_code=409, detail="idempotency key reused with different request")
        return {"round_id": existing["id"], "commit": existing["commit_hash"], "server_seed": existing["server_seed"], "result": json.loads(existing["result_json"]), "balance_transaction": None}
    seed, commit = new_seed()
    multiplier = crash_point(seed, request.client_seed, request.nonce)
    payout = multiplier if request.auto_cashout and request.auto_cashout <= multiplier else 0.0
    try:
        reserve_stake(user["id"], "crash", cents(request.amount), key)
        result = {"crash_multiplier": multiplier, "cashout_multiplier": request.auto_cashout, "payout_multiplier": payout}
        payout_cents = cents(request.amount * payout)
        round_id = create_round(user["id"], "crash", request, seed, commit, result, payout_cents)
        settlement = settle_stake(user["id"], "crash", key, payout_cents, json.dumps(result))
    except Exception as exc:
        try:
            refund_stake(user["id"], "crash", key, "round processing failed")
        except Exception:
            pass
        fail_ledger(exc)
    with connection() as conn:
        conn.execute(
            "UPDATE web_game_rounds SET settled_at = CURRENT_TIMESTAMP WHERE id = ?",
            (round_id,),
        )
    return {"round_id": round_id, "commit": commit, "server_seed": seed, "result": result,
            "balance_transaction": settlement["id"]}


@app.post("/api/games/fruit-fall/play")
def fruit_play(request: FruitBetRequest, user: Annotated[dict, Depends(current_user)]) -> dict:
    key = f"web:fruit-fall:{user['id']}:{request.idempotency_key}"
    existing = get_round_by_key(user["id"], "fruit-fall", key)
    if existing:
        if existing["request_fingerprint"] != request_fingerprint(request):
            raise HTTPException(status_code=409, detail="idempotency key reused with different request")
        return {"round_id": existing["id"], "commit": existing["commit_hash"], "server_seed": existing["server_seed"], "result": json.loads(existing["result_json"]), "balance_transaction": None}
    seed, commit = new_seed()
    result = fruit_round(seed, request.client_seed, request.nonce, request.rows, request.cols)
    try:
        reserve_stake(user["id"], "fruit-fall", cents(request.amount), key)
        payout_cents = cents(request.amount * result["payout_multiplier"])
        round_id = create_round(user["id"], "fruit-fall", request, seed, commit, result, payout_cents)
        settlement = settle_stake(
            user["id"], "fruit-fall", key,
            payout_cents,
            json.dumps(result, ensure_ascii=False),
        )
    except Exception as exc:
        try:
            refund_stake(user["id"], "fruit-fall", key, "round processing failed")
        except Exception:
            pass
        fail_ledger(exc)
    with connection() as conn:
        conn.execute(
            "UPDATE web_game_rounds SET settled_at = CURRENT_TIMESTAMP WHERE id = ?",
            (round_id,),
        )
    return {"round_id": round_id, "commit": commit, "server_seed": seed, "result": result,
            "balance_transaction": settlement["id"]}
