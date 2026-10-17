"""Deterministic, server-authoritative demo engines for Mini App games.

These functions return outcomes only; money settlement belongs in the API/domain
transaction layer. The frontend must never calculate payouts.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import secrets
from collections.abc import Callable

FRUITS = ("🍋", "🍒", "🍇", "🍉", "🥝", "🔔", "💎")
FRUIT_PAYOUTS = {
    3: {"🍋": 1.5, "🍒": 2.0, "🍇": 2.5, "🍉": 3.0, "🥝": 4.0, "🔔": 6.0, "💎": 12.0},
    4: {"🍋": 3.0, "🍒": 4.0, "🍇": 5.0, "🍉": 7.0, "🥝": 10.0, "🔔": 15.0, "💎": 25.0},
    5: {"🍋": 8.0, "🍒": 10.0, "🍇": 12.0, "🍉": 15.0, "🥝": 20.0, "🔔": 30.0, "💎": 50.0},
}
MAX_FRUIT_MULTIPLIER = 50.0
MAX_FRUIT_CASCADES = 32


def _digest(server_seed: str, client_seed: str, nonce: int) -> bytes:
    message = f"{client_seed}:{nonce}".encode()
    return hmac.new(server_seed.encode(), message, hashlib.sha256).digest()


def _fruit_draw(server_seed: str, client_seed: str, nonce: int, draw_index: int) -> str:
    """Draw one deterministic symbol from a unique HMAC message."""
    if draw_index < 0:
        raise ValueError("draw_index must be non-negative")
    message = f"{client_seed}:{nonce}:fruit-fall:{draw_index}".encode()
    digest = hmac.new(server_seed.encode(), message, hashlib.sha256).digest()
    return FRUITS[int.from_bytes(digest[:8], "big") % len(FRUITS)]


def crash_point(server_seed: str, client_seed: str, nonce: int, house_edge: float = 0.04) -> float:
    """Return a deterministic crash multiplier with a documented edge."""
    if not 0 <= house_edge < 1:
        raise ValueError("house_edge must be between 0 and 1")
    value = int.from_bytes(_digest(server_seed, client_seed, nonce)[:8], "big")
    u = (value + 1) / (2**64)
    return max(1.0, math.floor((1 - house_edge) / (1 - u) * 100) / 100)


def _find_row_matches(grid: list[list[str]]) -> list[dict]:
    matches = []
    for row_index, row in enumerate(grid):
        for symbol in sorted(set(row), key=FRUITS.index):
            cells = [column for column, current in enumerate(row) if current == symbol]
            count = min(len(cells), 5)
            if count >= 3:
                matches.append({
                    "row": row_index,
                    "symbol": symbol,
                    "cells": [[row_index, column] for column in cells],
                    "count": count,
                    "payout_multiplier": FRUIT_PAYOUTS[count][symbol],
                })
    return matches


def _resolve_fruit_cascades(
    initial_grid: list[list[str]],
    symbol_draw: Callable[[], str],
    max_cascades: int = MAX_FRUIT_CASCADES,
) -> dict:
    if max_cascades < 1:
        raise ValueError("max_cascades must be positive")
    rows = len(initial_grid)
    cols = len(initial_grid[0]) if rows else 0
    grid = [row[:] for row in initial_grid]
    cascades = []
    total = 0.0

    for index in range(max_cascades):
        before = [row[:] for row in grid]
        matches = _find_row_matches(before)
        if not matches:
            break
        removed = sorted({tuple(cell) for match in matches for cell in match["cells"]})
        removed_set = set(removed)
        step_payout = sum(match["payout_multiplier"] for match in matches)
        after = [[None for _ in range(cols)] for _ in range(rows)]
        spawned = []
        for column in range(cols):
            survivors = [before[row][column] for row in range(rows) if (row, column) not in removed_set]
            refill_count = rows - len(survivors)
            refills = [symbol_draw() for _ in range(refill_count)]
            spawned.extend(
                {"row": row, "column": column, "symbol": symbol}
                for row, symbol in zip(range(refill_count), refills)
            )
            values = refills + survivors
            for row, symbol in enumerate(values):
                after[row][column] = symbol
        total += step_payout
        cascades.append({
            "index": index,
            "grid_before": before,
            "matches": matches,
            "removed": [[row, column] for row, column in removed],
            "spawned": spawned,
            "grid_after": after,
            "payout_multiplier": round(step_payout, 2),
        })
        grid = after

    limit_reached = len(cascades) >= max_cascades and bool(_find_row_matches(grid))
    return {
        "cascades": cascades,
        "final_grid": grid,
        "total_payout_multiplier": min(round(total, 2), MAX_FRUIT_MULTIPLIER),
        "cascade_limit_reached": limit_reached,
    }


def fruit_round(server_seed: str, client_seed: str, nonce: int, rows: int = 6, cols: int = 5) -> dict:
    """Produce a deterministic Fruit Fall grid and bounded cascade sequence."""
    if rows < 3 or rows > 10 or cols < 3 or cols > 8:
        raise ValueError("grid dimensions are outside the supported range")
    draw_index = 0

    def draw() -> str:
        nonlocal draw_index
        symbol = _fruit_draw(server_seed, client_seed, nonce, draw_index)
        draw_index += 1
        return symbol

    initial_grid = [[draw() for _ in range(cols)] for _ in range(rows)]
    resolved = _resolve_fruit_cascades(initial_grid, draw)
    payout_multiplier = resolved["total_payout_multiplier"]
    return {
        "version": 3,
        "rows": rows,
        "cols": cols,
        "grid": initial_grid,
        "initial_grid": initial_grid,
        "matches": resolved["cascades"][0]["matches"] if resolved["cascades"] else [],
        "cascades": resolved["cascades"],
        "cascade_count": len(resolved["cascades"]),
        "cascade_limit_reached": resolved["cascade_limit_reached"],
        "total_payout_multiplier": payout_multiplier,
        "payout_multiplier": payout_multiplier,
    }


def simulate_fruit_rtp(
    rounds: int = 100_000,
    server_seed: str = "rtp-simulation",
    client_seed: str = "rtp",
    nonce_start: int = 0,
    rows: int = 6,
    cols: int = 5,
) -> dict:
    """Run a deterministic offline RTP diagnostic; never use as live state."""
    if rounds < 1 or nonce_start < 0:
        raise ValueError("rounds must be positive and nonce_start non-negative")
    total = 0.0
    hits = 0
    cascaded = 0
    maximum = 0.0
    for nonce in range(nonce_start, nonce_start + rounds):
        result = fruit_round(server_seed, client_seed, nonce, rows, cols)
        multiplier = result["payout_multiplier"]
        total += multiplier
        maximum = max(maximum, multiplier)
        hits += multiplier > 0
        cascaded += result["cascade_count"] > 1
    return {
        "rounds": rounds,
        "total_stake_units": float(rounds),
        "total_return_units": round(total, 2),
        "rtp": round(total / rounds, 6),
        "hit_rate": round(hits / rounds, 6),
        "mean_multiplier": round(total / rounds, 6),
        "max_multiplier": maximum,
        "cascade_rate": round(cascaded / rounds, 6),
        "paytable_version": 2,
    }


def new_seed() -> tuple[str, str]:
    seed = secrets.token_hex(32)
    return seed, hashlib.sha256(seed.encode()).hexdigest()
