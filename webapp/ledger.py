"""Transactional SQLite wallet primitives for the Mini App migration.

Balances remain compatible with the legacy users table, but all new web bets
must use idempotency keys and a single transaction. Production should migrate
this ledger to PostgreSQL before enabling high-volume real-money play.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "users.db"


class LedgerError(RuntimeError):
    pass


class InsufficientFunds(LedgerError):
    pass


@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_ledger() -> None:
    with connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS web_wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            game TEXT NOT NULL,
            amount_cents INTEGER NOT NULL,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            metadata TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_web_wallet_user
            ON web_wallet_transactions(user_id, id DESC);
        CREATE TABLE IF NOT EXISTS web_game_rounds (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            game TEXT NOT NULL,
            status TEXT NOT NULL,
            stake_cents INTEGER NOT NULL,
            payout_cents INTEGER NOT NULL DEFAULT 0,
            commit_hash TEXT NOT NULL,
            server_seed TEXT NOT NULL,
            client_seed TEXT NOT NULL,
            nonce INTEGER NOT NULL,
            result_json TEXT,
            idempotency_key TEXT,
            request_fingerprint TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            settled_at DATETIME
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_web_round_nonce
            ON web_game_rounds(user_id, game, nonce);
        """)
        # Keep existing installations compatible with the new idempotency fields.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(web_game_rounds)")}
        if "idempotency_key" not in columns:
            conn.execute("ALTER TABLE web_game_rounds ADD COLUMN idempotency_key TEXT")
        if "request_fingerprint" not in columns:
            conn.execute("ALTER TABLE web_game_rounds ADD COLUMN request_fingerprint TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_web_round_key ON web_game_rounds(user_id, game, idempotency_key)")


def reserve_stake(user_id: int, game: str, amount_cents: int, key: str, metadata: str = "") -> dict:
    if amount_cents <= 0 or len(key) < 8:
        raise LedgerError("invalid stake or idempotency key")
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT * FROM web_wallet_transactions WHERE idempotency_key = ?", (key,)
        ).fetchone()
        if existing:
            if existing["user_id"] != user_id or existing["game"] != game:
                raise LedgerError("idempotency key belongs to another operation")
            if abs(int(existing["amount_cents"])) != amount_cents:
                raise LedgerError("idempotency key reused with different stake")
            return dict(existing)
        row = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            raise LedgerError("user not found")
        current_cents = int(round(float(row[0]) * 100))
        if current_cents < amount_cents:
            raise InsufficientFunds("insufficient funds")
        new_cents = current_cents - amount_cents
        conn.execute("UPDATE users SET balance = ?, level = level WHERE user_id = ?", (new_cents / 100, user_id))
        conn.execute(
            "INSERT INTO web_wallet_transactions "
            "(idempotency_key,user_id,game,amount_cents,kind,status,metadata) VALUES (?,?,?,?,?,?,?)",
            (key, user_id, game, -amount_cents, "stake", "reserved", metadata),
        )
        return dict(conn.execute("SELECT * FROM web_wallet_transactions WHERE idempotency_key = ?", (key,)).fetchone())


def settle_stake(user_id: int, game: str, key: str, payout_cents: int, metadata: str = "") -> dict:
    if payout_cents < 0:
        raise LedgerError("invalid payout")
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        stake = conn.execute(
            "SELECT * FROM web_wallet_transactions WHERE idempotency_key = ? AND user_id = ? AND game = ?",
            (key, user_id, game),
        ).fetchone()
        if not stake:
            raise LedgerError("stake not found")
        if stake["status"] == "settled":
            return dict(stake)
        if stake["status"] != "reserved":
            raise LedgerError("stake is not settleable")
        row = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
        current_cents = int(round(float(row[0]) * 100))
        conn.execute("UPDATE users SET balance = ? WHERE user_id = ?", ((current_cents + payout_cents) / 100, user_id))
        conn.execute(
            "UPDATE web_wallet_transactions SET status = 'settled', metadata = ? WHERE idempotency_key = ?",
            (metadata, key),
        )
        return dict(conn.execute("SELECT * FROM web_wallet_transactions WHERE idempotency_key = ?", (key,)).fetchone())


def get_round_by_key(user_id: int, game: str, key: str) -> dict | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM web_game_rounds WHERE user_id = ? AND game = ? AND idempotency_key = ?",
            (user_id, game, key),
        ).fetchone()
    return dict(row) if row else None


def refund_stake(user_id: int, game: str, key: str, metadata: str = "") -> dict:
    """Return a reserved stake exactly once after a failed round write/settlement."""
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        stake = conn.execute(
            "SELECT * FROM web_wallet_transactions WHERE idempotency_key = ? AND user_id = ? AND game = ?",
            (key, user_id, game),
        ).fetchone()
        if not stake:
            raise LedgerError("stake not found")
        if stake["status"] == "refunded":
            return dict(stake)
        if stake["status"] != "reserved":
            raise LedgerError("stake is not refundable")
        row = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            raise LedgerError("user not found")
        current_cents = int(round(float(row[0]) * 100))
        conn.execute(
            "UPDATE users SET balance = ? WHERE user_id = ?",
            ((current_cents + abs(int(stake["amount_cents"]))) / 100, user_id),
        )
        conn.execute(
            "UPDATE web_wallet_transactions SET status = 'refunded', metadata = ? WHERE idempotency_key = ?",
            (metadata, key),
        )
        return dict(conn.execute("SELECT * FROM web_wallet_transactions WHERE idempotency_key = ?", (key,)).fetchone())
