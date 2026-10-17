import os
import sqlite3
import logging
from datetime import datetime, timedelta
from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Filter
import time

from config.config import LEVELS, lose_withdraw, min_stavka_referal

router = Router()
DB_PATH = "users.db"
user_languages = {}

def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()

    cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    user_name TEXT,
                    balance REAL DEFAULT 0.0,
                    total_turnover REAL DEFAULT 0.0,
                    deposits INTEGER DEFAULT 0,
                    withdrawals INTEGER DEFAULT 0,
                    invited_by INTEGER,
                    inviter_id INTEGER,
                    amount REAL DEFAULT 0.0,
                    is_admin INTEGER DEFAULT 0,
                    games_played INTEGER DEFAULT 0,
                    level TEXT DEFAULT 'Новичок 🐣'
                )
            """)

    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'games_played' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN games_played INTEGER DEFAULT 0")

    if 'is_admin' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        cursor.execute("UPDATE users SET is_admin = 0 WHERE is_admin IS NULL")

    if 'total_deposited' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN total_deposited REAL DEFAULT 0")

    if 'is_banned' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
        cursor.execute("UPDATE users SET is_banned = 0 WHERE is_banned IS NULL")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referral_profits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER,
            amount REAL,
            FOREIGN KEY (inviter_id) REFERENCES users(user_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_date DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS turnover (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            turnover_date DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS winnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            winning_date DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coefficients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            coefficient REAL,
            coeff_date DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # --- Provably Fair: активная пара сидов на пользователя ---
    # server_seed хранится в открытом виде только пока активен (не раскрыт публично),
    # игрок видит только server_seed_hash = sha256(salt:server_seed) до ротации.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fair_seeds (
            user_id INTEGER PRIMARY KEY,
            server_seed TEXT NOT NULL,
            server_seed_hash TEXT NOT NULL,
            client_seed TEXT NOT NULL,
            salt TEXT NOT NULL,
            nonce INTEGER DEFAULT 0,
            created_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # --- Provably Fair: архив раскрытых (отработавших) пар сидов ---
    # Как только пользователь меняет client_seed или запрашивает ротацию,
    # текущий server_seed раскрывается и переносится сюда — можно пересчитать
    # любой прошлый раунд и свериться с сохранённым в bet_history hash'ем.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fair_seeds_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            server_seed TEXT NOT NULL,
            server_seed_hash TEXT NOT NULL,
            client_seed TEXT NOT NULL,
            salt TEXT NOT NULL,
            nonce_used INTEGER,
            revealed_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # --- История ставок для профиля игрока ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bet_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game TEXT,
            bet_amount REAL,
            payout REAL,
            is_win INTEGER,
            result_text TEXT,
            server_seed_hash TEXT,
            client_seed TEXT,
            nonce INTEGER,
            created_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bet_history_user ON bet_history(user_id, id DESC)")

    # --- Заявки на вывод: требуют подтверждения администратора ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS withdraw_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            amount REAL,
            currency TEXT,
            status TEXT DEFAULT 'pending',  -- pending / approved / rejected / failed
            created_at DATETIME,
            processed_at DATETIME,
            processed_by INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_withdraw_requests_status ON withdraw_requests(status, id DESC)")

    # --- Раздача (бонус % на депозит на ограниченное время) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS giveaways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            percent REAL,
            min_deposit REAL,
            starts_at DATETIME,
            ends_at DATETIME,
            is_active INTEGER DEFAULT 1,
            created_by INTEGER
        )
    """)

    conn.commit()
    conn.close()

def add_user_if_not_exists(user_id: int, user_name: str = None, is_admin: int = 0, conn: sqlite3.Connection = None):
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        close_conn = True
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO users (user_id, user_name, balance, total_turnover, deposits, withdrawals, is_admin, games_played, level) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, user_name or "Аноним", 0.0, 0.0, 0, 0, is_admin, 0, "Новичок 🐣")
            )
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error in add_user_if_not_exists: {e}")
    finally:
        if close_conn:
            conn.close()

def get_user_data(user_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        init_db()
        cursor.execute(
            "SELECT user_id, user_name, balance, total_turnover, deposits, withdrawals, is_admin, games_played, level, "
            "total_deposited, is_banned "
            "FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        if result:
            return {
                "user_id": result[0],
                "user_name": result[1],
                "balance": result[2],
                "total_turnover": result[3],
                "deposits": result[4],
                "withdrawals": result[5],
                "is_admin": result[6],
                "games_played": result[7] or 0,
                "level": result[8],
                "total_deposited": result[9] or 0.0,
                "is_banned": bool(result[10]),
            }
        add_user_if_not_exists(user_id)
        return {
            "user_id": user_id,
            "user_name": "Аноним",
            "balance": 0.0,
            "total_turnover": 0.0,
            "deposits": 0,
            "withdrawals": 0,
            "is_admin": 0,
            "games_played": 0,
            "level": "Новичок 🐣",
            "total_deposited": 0.0,
            "is_banned": False,
        }
    except sqlite3.Error as e:
        logging.error(f"DB error in get_user_data: {e}")
        return {
            "user_id": user_id,
            "user_name": "Аноним",
            "balance": 0.0,
            "total_turnover": 0.0,
            "deposits": 0,
            "withdrawals": 0,
            "is_admin": 0,
            "games_played": 0,
            "level": "Новичок 🐣",
            "total_deposited": 0.0,
            "is_banned": False,
        }
    finally:
        conn.close()

def calculate_user_level(balance: float) -> str:
    current_level = LEVELS[0][1]
    for threshold, level_name in LEVELS:
        if balance >= threshold:
            current_level = level_name
        else:
            break
    return current_level

def update_user_balance(user_id: int, new_balance: float):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        init_db()
        new_level = calculate_user_level(new_balance)
        cursor.execute(
            "UPDATE users SET balance = ?, level = ? WHERE user_id = ?",
            (new_balance, new_level, user_id)
        )
        if cursor.rowcount == 0:
            add_user_if_not_exists(user_id)
            cursor.execute(
                "UPDATE users SET balance = ?, level = ? WHERE user_id = ?",
                (new_balance, new_level, user_id)
            )
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error in update_user_balance: {e}")
    finally:
        conn.close()

def get_user_level(user_id: int) -> str:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT level FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else "Новичок 🐣"
    except sqlite3.Error as e:
        logging.error(f"DB error in get_user_level: {e}")
        return "Новичок 🐣"
    finally:
        conn.close()

def get_user_level_by_games(games_played: int) -> str:
    current_level = "Новичок 🐣"
    for min_games, level_name in LEVELS:
        if games_played >= min_games:
            current_level = level_name
        else:
            break
    return current_level

def increment_games_played(user_id: int, conn: sqlite3.Connection = None):
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        close_conn = True
    cursor = conn.cursor()
    max_retries = 5
    retry_delay = 0.1
    for attempt in range(max_retries):
        try:
            cursor.execute("UPDATE users SET games_played = COALESCE(games_played, 0) + 1 WHERE user_id = ?", (user_id,))
            if cursor.rowcount == 0:
                add_user_if_not_exists(user_id, conn=conn)
                cursor.execute("UPDATE users SET games_played = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            break
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            logging.error(f"DB error in increment_games_played: {e}")
            raise
        except sqlite3.Error as e:
            logging.error(f"DB error in increment_games_played: {e}")
            raise
        finally:
            if close_conn:
                conn.close()

def add_game_played(user_id: int):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO games (user_id, game_date) VALUES (?, ?)",
            (user_id, datetime.now())
        )
        increment_games_played(user_id, conn)
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error in add_game_played: {e}")
    finally:
        conn.close()

def add_turnover(user_id: int, amount: float):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        init_db()
        cursor.execute(
            "INSERT INTO turnover (user_id, amount, turnover_date) VALUES (?, ?, ?)",
            (user_id, amount, datetime.now())
        )
        cursor.execute(
            "UPDATE users SET total_turnover = COALESCE(total_turnover, 0) + ? WHERE user_id = ?",
            (amount, user_id)
        )
        if cursor.rowcount == 0:
            add_user_if_not_exists(user_id)
            cursor.execute(
                "UPDATE users SET total_turnover = ? WHERE user_id = ?",
                (amount, user_id)
            )
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error in add_turnover: {e}")
    finally:
        conn.close()

def add_winning(user_id: int, amount: float):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        init_db()
        cursor.execute(
            "INSERT INTO winnings (user_id, amount, winning_date) VALUES (?, ?, ?)",
            (user_id, amount, datetime.now())
        )
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error in add_winning: {e}")
    finally:
        conn.close()

def add_coefficient(user_id: int, coefficient: float):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        init_db()
        cursor.execute(
            "INSERT INTO coefficients (user_id, coefficient, coeff_date) VALUES (?, ?, ?)",
            (user_id, coefficient, datetime.now())
        )
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"DB error in add_coefficient: {e}")
    finally:
        conn.close()

def set_inviter(ref_id: int, inviter_id: int):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET invited_by = ? WHERE user_id = ?", (inviter_id, ref_id))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error in set_inviter: {e}")
    finally:
        conn.close()

def count_ref(user_id: int) -> int:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users WHERE invited_by = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    except sqlite3.Error as e:
        logging.error(f"Database error in count_ref: {e}")
        return 0
    finally:
        conn.close()

def refka_cheks_money(user_id: int) -> float:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT SUM(amount) FROM referral_profits WHERE inviter_id = ?", (user_id,))
        result = cursor.fetchone()
        return round(result[0], 2) if result[0] is not None else 0.0
    except sqlite3.Error as e:
        logging.error(f"Database error in refka_cheks_money: {e}")
        return 0.0
    finally:
        conn.close()

def add_referral_profit(inviter_id: int, amount: float):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO referral_profits (inviter_id, amount) VALUES (?, ?)", (inviter_id, amount))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error in add_referral_profit: {e}")
    finally:
        conn.close()

def get_top_10_games(time_period="all_time"):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    query = """
        SELECT u.user_name, COUNT(g.id) as game_count
        FROM users u
        JOIN games g ON u.user_id = g.user_id
    """
    params = []
    if time_period == "today":
        query += " WHERE g.game_date >= ?"
        params.append(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
    elif time_period == "week":
        query += " WHERE g.game_date >= ?"
        params.append(datetime.now() - timedelta(days=7))
    elif time_period == "month":
        query += " WHERE g.game_date >= ?"
        params.append(datetime.now() - timedelta(days=30))
    query += " GROUP BY u.user_id, u.user_name ORDER BY game_count DESC LIMIT 10"
    try:
        cursor.execute(query, params)
        result = cursor.fetchall()
        return [(username or "Аноним", game_count) for username, game_count in result]
    except sqlite3.Error as e:
        logging.error(f"Database error in get_top_10_games: {e}")
        return []
    finally:
        conn.close()

def get_top_10_games_by_users(time_period: str = "all_time"):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        query = """
            SELECT user_name, games_played
            FROM users
            WHERE games_played > 0
        """
        params = []
        if time_period != "all_time":
            query += " AND EXISTS (SELECT 1 FROM games g WHERE g.user_id = users.user_id AND g.game_date >= ?)"
            if time_period == "today":
                params.append(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
            elif time_period == "week":
                params.append(datetime.now() - timedelta(days=7))
            elif time_period == "month":
                params.append(datetime.now() - timedelta(days=30))
        query += " ORDER BY games_played DESC LIMIT 10"
        cursor.execute(query, params)
        result = cursor.fetchall()
        return [(username or "Аноним", games_played) for username, games_played in result]
    except sqlite3.Error as e:
        logging.error(f"Database error in get_top_10_games_by_users: {e}")
        return []
    finally:
        conn.close()

def get_top_10_turnover(time_period="all_time"):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    query = """
        SELECT u.user_name, SUM(t.amount) as total_turnover
        FROM users u
        JOIN turnover t ON u.user_id = t.user_id
    """
    params = []
    if time_period == "today":
        query += " WHERE t.turnover_date >= ?"
        params.append(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
    elif time_period == "week":
        query += " WHERE t.turnover_date >= ?"
        params.append(datetime.now() - timedelta(days=7))
    elif time_period == "month":
        query += " WHERE t.turnover_date >= ?"
        params.append(datetime.now() - timedelta(days=30))
    query += " GROUP BY u.user_id, u.user_name ORDER BY total_turnover DESC LIMIT 10"
    try:
        cursor.execute(query, params)
        result = cursor.fetchall()
        return [(username or "Аноним", total_turnover) for username, total_turnover in result]
    except sqlite3.Error as e:
        logging.error(f"Database error in get_top_10_turnover: {e}")
        return []
    finally:
        conn.close()

def get_top_10_winnings(time_period="all_time"):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    query = """
        SELECT u.user_name, SUM(w.amount) as total_winnings
        FROM users u
        JOIN winnings w ON u.user_id = w.user_id
    """
    params = []
    if time_period == "today":
        query += " WHERE w.winning_date >= ?"
        params.append(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
    elif time_period == "week":
        query += " WHERE w.winning_date >= ?"
        params.append(datetime.now() - timedelta(days=7))
    elif time_period == "month":
        query += " WHERE w.winning_date >= ?"
        params.append(datetime.now() - timedelta(days=30))
    query += " GROUP BY u.user_id, u.user_name ORDER BY total_winnings DESC LIMIT 10"
    try:
        cursor.execute(query, params)
        result = cursor.fetchall()
        return [(username or "Аноним", total_winnings) for username, total_winnings in result]
    except sqlite3.Error as e:
        logging.error(f"Database error in get_top_10_winnings: {e}")
        return []
    finally:
        conn.close()

def get_top_10_coefficient(time_period="all_time"):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    query = """
        SELECT u.user_name, MAX(c.coefficient) as max_coefficient
        FROM users u
        JOIN coefficients c ON u.user_id = c.user_id
    """
    params = []
    if time_period == "today":
        query += " WHERE c.coeff_date >= ?"
        params.append(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
    elif time_period == "week":
        query += " WHERE c.coeff_date >= ?"
        params.append(datetime.now() - timedelta(days=7))
    elif time_period == "month":
        query += " WHERE c.coeff_date >= ?"
        params.append(datetime.now() - timedelta(days=30))
    query += " GROUP BY u.user_id, u.user_name ORDER BY max_coefficient DESC LIMIT 10"
    try:
        cursor.execute(query, params)
        result = cursor.fetchall()
        return [(username or "Аноним", max_coefficient) for username, max_coefficient in result]
    except sqlite3.Error as e:
        logging.error(f"Database error in get_top_10_coefficient: {e}")
        return []
    finally:
        conn.close()

def is_user_registered(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone() is not None
        return exists
    except sqlite3.Error as e:
        logging.error(f"Database error in is_user_registered: {e}")
        return False
    finally:
        conn.close()

def is_admin(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] == 1 if result else False
    except sqlite3.Error as e:
        logging.error(f"Database error in is_admin: {e}")
        return False
    finally:
        conn.close()

def set_admin(user_id: int, is_admin: int) -> bool:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO users (user_id, user_name, is_admin, deposits, balance) VALUES (?, ?, ?, 0, 0)",
                (user_id, "Unknown", is_admin)
            )
        else:
            cursor.execute("UPDATE users SET is_admin = ? WHERE user_id = ?", (is_admin, user_id))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Database error in set_admin: {e}")
        return False
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Provably Fair + история ставок
# ---------------------------------------------------------------------------

def log_bet_history(user_id: int, game: str, bet_amount: float, payout: float,
                     is_win: bool, result_text: str, server_seed_hash: str = None,
                     client_seed: str = None, nonce: int = None) -> int | None:
    """Пишет один раунд в историю ставок игрока. Возвращает id вставленной записи
    (используется, например, чтобы потом ссылаться на неё из кнопки 'Честность')."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    row_id = None
    try:
        cursor.execute("""
            INSERT INTO bet_history
                (user_id, game, bet_amount, payout, is_win, result_text,
                 server_seed_hash, client_seed, nonce, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, game, bet_amount, payout, 1 if is_win else 0, result_text,
            server_seed_hash, client_seed, nonce, datetime.now()
        ))
        conn.commit()
        row_id = cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Database error in log_bet_history: {e}")
    finally:
        conn.close()

    # Реферальная программа: если проигравший был кем-то приглашён — инвайтер получает
    # lose_withdraw% от суммы ставки на СВОЙ игровой баланс (не прямой перевод в CryptoBot —
    # это безопаснее и укладывается в общую схему: любой вывод в любом случае идёт
    # через подтверждение админом, см. submit_withdraw_for_approval).
    if row_id is not None and not is_win and bet_amount >= min_stavka_referal:
        try:
            conn2 = sqlite3.connect(DB_PATH, timeout=10)
            cursor2 = conn2.cursor()
            cursor2.execute("SELECT invited_by FROM users WHERE user_id = ?", (user_id,))
            row = cursor2.fetchone()
            inviter_id = row[0] if row else None
            conn2.close()

            if inviter_id:
                profit = round(bet_amount * lose_withdraw / 100, 2)
                if profit > 0:
                    conn3 = sqlite3.connect(DB_PATH, timeout=10)
                    cursor3 = conn3.cursor()
                    cursor3.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (profit, inviter_id))
                    conn3.commit()
                    conn3.close()
                    add_referral_profit(inviter_id, profit)
        except sqlite3.Error as e:
            logging.error(f"Database error while crediting referral profit: {e}")

    return row_id


def get_bet_history_row(row_id: int, user_id: int | None = None) -> dict | None:
    """Return one history row, optionally scoped to its owner."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        query = """
            SELECT game, bet_amount, payout, is_win, result_text,
                   server_seed_hash, client_seed, created_at
            FROM bet_history WHERE id = ?
        """
        params = [row_id]
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        cursor.execute(query, params)
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "game": row[0], "bet_amount": row[1], "payout": row[2], "is_win": bool(row[3]),
            "result_text": row[4], "hash": row[5], "reveal": row[6], "created_at": row[7],
        }
    except sqlite3.Error as e:
        logging.error(f"Database error in get_bet_history_row: {e}")
        return None
    finally:
        conn.close()


def get_bet_history(user_id: int, limit: int = 10) -> list:
    """Последние N раундов пользователя, самые свежие первыми."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT game, bet_amount, payout, is_win, result_text,
                   server_seed_hash, client_seed, nonce, created_at
            FROM bet_history
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, limit))
        rows = cursor.fetchall()
        return [
            {
                "game": r[0], "bet_amount": r[1], "payout": r[2], "is_win": bool(r[3]),
                "result_text": r[4], "server_seed_hash": r[5], "client_seed": r[6],
                "nonce": r[7], "created_at": r[8],
            }
            for r in rows
        ]
    except sqlite3.Error as e:
        logging.error(f"Database error in get_bet_history: {e}")
        return []
    finally:
        conn.close()


def get_active_fair_seed(user_id: int) -> dict | None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT server_seed, server_seed_hash, client_seed, salt, nonce
            FROM fair_seeds WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "server_seed": row[0], "server_seed_hash": row[1],
            "client_seed": row[2], "salt": row[3], "nonce": row[4],
        }
    except sqlite3.Error as e:
        logging.error(f"Database error in get_active_fair_seed: {e}")
        return None
    finally:
        conn.close()


def upsert_fair_seed(user_id: int, server_seed: str, server_seed_hash: str,
                      client_seed: str, salt: str, nonce: int = 0):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO fair_seeds (user_id, server_seed, server_seed_hash, client_seed, salt, nonce, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                server_seed=excluded.server_seed,
                server_seed_hash=excluded.server_seed_hash,
                client_seed=excluded.client_seed,
                salt=excluded.salt,
                nonce=excluded.nonce,
                created_at=excluded.created_at
        """, (user_id, server_seed, server_seed_hash, client_seed, salt, nonce, datetime.now()))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error in upsert_fair_seed: {e}")
    finally:
        conn.close()


def increment_fair_nonce(user_id: int) -> int:
    """Увеличивает nonce после каждого раунда, возвращает значение ДО инкремента (использованное в раунде)."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nonce FROM fair_seeds WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        used_nonce = row[0] if row else 0
        cursor.execute("UPDATE fair_seeds SET nonce = nonce + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return used_nonce
    except sqlite3.Error as e:
        logging.error(f"Database error in increment_fair_nonce: {e}")
        return 0
    finally:
        conn.close()


def archive_fair_seed(user_id: int, seed: dict):
    """Переносит текущую (уже раскрытую) пару сидов в историю перед ротацией."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO fair_seeds_history
                (user_id, server_seed, server_seed_hash, client_seed, salt, nonce_used, revealed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, seed["server_seed"], seed["server_seed_hash"],
            seed["client_seed"], seed["salt"], seed["nonce"], datetime.now()
        ))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error in archive_fair_seed: {e}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Заявки на вывод (требуют подтверждения администратора)
# ---------------------------------------------------------------------------

def get_all_admin_ids() -> list:
    """user_id всех, у кого is_admin=1 — рассылать уведомления о заявках на вывод."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM users WHERE is_admin = 1")
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Database error in get_all_admin_ids: {e}")
        return []
    finally:
        conn.close()


def create_withdraw_request(user_id: int, user_name: str, amount: float, currency: str = "USDT") -> int | None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO withdraw_requests (user_id, user_name, amount, currency, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (user_id, user_name, amount, currency, datetime.now()))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Database error in create_withdraw_request: {e}")
        return None
    finally:
        conn.close()


def get_withdraw_request(request_id: int) -> dict | None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, user_id, user_name, amount, currency, status, created_at, processed_at, processed_by
            FROM withdraw_requests WHERE id = ?
        """, (request_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0], "user_id": row[1], "user_name": row[2], "amount": row[3],
            "currency": row[4], "status": row[5], "created_at": row[6],
            "processed_at": row[7], "processed_by": row[8],
        }
    except sqlite3.Error as e:
        logging.error(f"Database error in get_withdraw_request: {e}")
        return None
    finally:
        conn.close()


def set_withdraw_request_status(request_id: int, status: str, processed_by: int = None) -> bool:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE withdraw_requests SET status = ?, processed_at = ?, processed_by = ?
            WHERE id = ?
        """, (status, datetime.now(), processed_by, request_id))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Database error in set_withdraw_request_status: {e}")
        return False
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Раздача (бонус % на депозит)
# ---------------------------------------------------------------------------

def create_giveaway(percent: float, min_deposit: float, duration_minutes: int, admin_id: int) -> int | None:
    """Деактивирует любую текущую активную раздачу и запускает новую."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE giveaways SET is_active = 0 WHERE is_active = 1")
        now = datetime.now()
        ends_at = now + timedelta(minutes=duration_minutes)
        cursor.execute("""
            INSERT INTO giveaways (percent, min_deposit, starts_at, ends_at, is_active, created_by)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (percent, min_deposit, now, ends_at, admin_id))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Database error in create_giveaway: {e}")
        return None
    finally:
        conn.close()


def get_active_giveaway() -> dict | None:
    """Активная раздача прямо сейчас (учитывая время окончания), иначе None."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, percent, min_deposit, starts_at, ends_at
            FROM giveaways WHERE is_active = 1
            ORDER BY id DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if not row:
            return None
        ends_at = datetime.fromisoformat(row[4]) if isinstance(row[4], str) else row[4]
        if datetime.now() > ends_at:
            cursor.execute("UPDATE giveaways SET is_active = 0 WHERE id = ?", (row[0],))
            conn.commit()
            return None
        return {
            "id": row[0], "percent": row[1], "min_deposit": row[2],
            "starts_at": row[3], "ends_at": row[4],
        }
    except sqlite3.Error as e:
        logging.error(f"Database error in get_active_giveaway: {e}")
        return None
    finally:
        conn.close()


def stop_giveaway() -> bool:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE giveaways SET is_active = 0 WHERE is_active = 1")
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Database error in stop_giveaway: {e}")
        return False
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Блокировка пользователей
# ---------------------------------------------------------------------------

def set_user_banned(user_id: int, banned: bool) -> bool:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if banned else 0, user_id))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Database error in set_user_banned: {e}")
        return False
    finally:
        conn.close()


def is_user_banned(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return bool(row[0]) if row else False
    except sqlite3.Error as e:
        logging.error(f"Database error in is_user_banned: {e}")
        return False
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Детальная статистика игрока (для карточки заявки на вывод у админа)
# ---------------------------------------------------------------------------

def get_withdraw_user_summary(user_id: int) -> dict:
    """Компактная статистика игрока для показа админу при рассмотрении вывода."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT deposits, total_deposited, withdrawals, games_played,
                   total_turnover, level, is_banned, invited_by
            FROM users WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            return {}
        cursor.execute("SELECT COUNT(*) FROM bet_history WHERE user_id = ? AND is_win = 1", (user_id,))
        wins = cursor.fetchone()[0] or 0
        return {
            "deposits_count": row[0] or 0,
            "total_deposited": row[1] or 0.0,
            "withdrawals_count": row[2] or 0,
            "games_played": row[3] or 0,
            "total_turnover": row[4] or 0.0,
            "level": row[5],
            "is_banned": bool(row[6]),
            "invited_by": row[7],
            "wins": wins,
        }
    except sqlite3.Error as e:
        logging.error(f"Database error in get_withdraw_user_summary: {e}")
        return {}
    finally:
        conn.close()
