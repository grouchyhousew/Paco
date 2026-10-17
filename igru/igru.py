# igru.py
import json
import random
import asyncio
import logging
import sqlite3
import time
import traceback
import os
import functools
from collections import defaultdict

from aiogram import Bot
from aiogram.filters import state
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, User, InlineKeyboardMarkup, InlineKeyboardButton
from config.config import *
from database.database import *
from igru.igru_logi import *
from games.keyboard import *


# ---------------------------------------------------------------------------
# Per-user lock. Без него параллельный запуск двух игр одним пользователем
# (например, двойной тап по кнопке) читает один и тот же старый баланс и
# может привести к двойному списанию/уходу в минус, т.к. между чтением
# баланса и его записью проходит несколько секунд (анимации/sleep).
# Лок сериализует все игры конкретного user_id в рамках процесса бота.
# ---------------------------------------------------------------------------
_user_game_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def with_user_lock(func):
    """Гарантирует, что один и тот же пользователь не может играть в
    несколько игр одновременно (устраняет гонку по балансу)."""
    @functools.wraps(func)
    async def wrapper(bot, user_id, *args, **kwargs):
        lock = _user_game_locks[user_id]
        async with lock:
            return await func(bot, user_id, *args, **kwargs)
    return wrapper


_GAME_NAME_BY_EMOJI = {
    "❣️": "hearts", "🎰": "slots", "🎲": "dice", "🎯": "darts",
    "⚽️": "football", "🏀": "basketball", "🎳": "bowling",
    "🔢": "even_odd/guess", "✂️": "rps", "🔫": "russian_roulette",
}


async def send_result_dm(bot: Bot, user: User, user_id: int, bet: float, winnings: float, is_win: bool, game_emoji: str):
    """
    Send compact result DM to the user after the result was posted in the channel.
    Заодно пишет раунд в историю ставок игрока (профиль → «История ставок»).
    """
    try:
        log_bet_history(
            user_id,
            _GAME_NAME_BY_EMOJI.get(game_emoji, game_emoji),
            bet, winnings, is_win,
            f"{game_emoji} {'выигрыш' if is_win else 'проигрыш'}",
            # Эти игры используют встроенный Telegram-дайс — сама случайность
            # генерируется на серверах Telegram, а не нашим seed'ом, поэтому
            # commit-hash тут не пишем (см. отдельно games с локальным RNG,
            # например «Мины», где подключена полная provably fair схема).
            None, None, None
        )
    except Exception as e:
        logging.error(f"Failed to log bet history for user {user_id}: {e}")
    try:
        username = f"@{user.username}" if getattr(user, "username", None) else (getattr(user, "full_name", "Аноним"))
        if is_win and (winnings is not None) and (winnings > 0):
            text = f"[🎉] {username} вы забрали свой выигрыш!\n\n💸 Ставка - ${bet:.2f} \n✅ Выигрыш - ${winnings:.2f}"
        else:
            text = f"{username} проигрыш ${bet:.2f} 💰 в игре {game_emoji}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰Наш бот", url="https://t.me/WinRemboBot")]])
        await bot.send_message(chat_id=user_id, text=text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to send result DM to user {user_id}: {e}")

@with_user_lock
async def play_hearts(
        bot: Bot,
        user_id: int,
        user: User,
        bet: float,
        chat_id: int,
        choice: str,
):
    user_data = get_user_data(user_id)
    user_balance = user_data.get("balance", 0)
    user_name = user_data.get("user_name") or user.full_name or "Аноним"
    user_level = get_user_level(user_id)

    logging.debug(f"play_hearts called for user_id={user_id}, bet={bet}, choice={choice}, balance={user_balance}")

    # Проверка суммы ставки
    if bet < 0.1 or bet > 200:
        logging.debug(f"Invalid bet amount for user_id={user_id}: {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ Сумма ставки должна быть от $0.1 до $200.", parse_mode="HTML")
        return "Неверная сумма ставки", user_balance, 0, "none"

    # Проверка баланса
    if user_balance < bet:
        logging.debug(f"Insufficient balance for user_id={user_id}: {user_balance} < {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ У вас недостаточно денег для ставки!", parse_mode="HTML")
        return "Недостаточно средств", user_balance, 0, "none"

    # Проверка выбора
    if choice not in ["red", "blue"]:
        logging.debug(f"Invalid choice for user_id={user_id}: {choice}")
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Неверный выбор. Выберите 'Красное' или 'Синее' сердце.",
            parse_mode="HTML"
        )
        return "Неверный выбор", user_balance, 0, "none"

    max_retries = 5
    retry_delay = 0.1

    try:
        # Логируем оборот
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging turnover for user_id={user_id}, amount={bet}")
                add_turnover(user_id, bet)
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_hearts (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, "none"
            except sqlite3.Error as e:
                logging.error(f"Database error in play_hearts (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, "none"

        # Отправляем начальное сообщение
        choice_display = {"red": "❤️ Красное", "blue": "💙 Синее"}
        initial_caption = (
            f"❣️ <b>Игра: Сердца</b>\n\n"
            f"🎯 Выбор: {choice_display.get(choice, 'Неизвестно')}\n"
            f"💸 Сумма: ${bet:.2f}\n"
            f"⤷ Коэффициент: x{HEARTS_MULTIPLIER:.1f}\n"
            f"⭐️ Потенциал:\n"
            f"⤷ ${bet:.2f} x {HEARTS_MULTIPLIER:.1f} ➤ ${round(bet * HEARTS_MULTIPLIER, 2):.2f}"
        )
        try:
            username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
            announcement = (
                f"🎉 Новая ставка в канале!\n<blockquote>🎮 Информация о ставке:\n┣ Ставка \n┣ 🥷🏻 Игрок: {username}\n┣ 🎰 Исход: {choice_display.get(choice, 'Неизвестно')} ❣️\n┗ 💸 Сумма: ${bet:.2f}</blockquote>\n@WinRemboBot"
            )
        except Exception as e:
            logging.error(f'Failed build announcement: {e}')
            announcement = initial_caption
        await bot.send_message(chat_id=CHANNEL_ID, text=announcement, parse_mode='HTML')
        await bot.send_message(chat_id=user_id, text="✅ Ставка принята! Бросаем...")
        await asyncio.sleep(1)

        # Определяем результат (50/50 шанс)
        result = random.choice(["red", "blue"])
        is_win = result == choice

        # Отправляем анимацию сердца
        heart_emoji = "❤️" if result == "red" else "💙"
        await bot.send_message(chat_id=CHANNEL_ID, text=f" {heart_emoji}", parse_mode="HTML")
        await asyncio.sleep(1)

        # Рассчитываем выигрыш
        multiplier = HEARTS_MULTIPLIER if is_win else 0.0
        winnings = round(bet * multiplier, 2) if is_win else 0
        new_balance = round(user_balance - bet + winnings, 2)

        # Обновляем базу данных
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging game play for user_id={user_id}")
                add_game_played(user_id)
                logging.debug(f"Logging coefficient for user_id={user_id}, coefficient={multiplier}")
                add_coefficient(user_id, multiplier)
                if winnings > 0:
                    logging.debug(f"Logging win for user_id={user_id}, winnings={winnings}")
                    add_winning(user_id, winnings)
                update_user_balance(user_id, new_balance)
                logging.debug(f"Updated balance for user_id={user_id}, new_balance={new_balance}")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_hearts for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, "none"
            except sqlite3.Error as e:
                logging.error(f"Database error in play_hearts for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, "none"

        # Отправляем результат в канал
        username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰Наш бот", url="https://t.me/WinRemboBot")]])
        if is_win:
            channel_text = f"[🎉] {username} вы забрали свой выигрыш!\n\n💸 Ставка - ${bet:.2f} \n✅ Выигрыш - ${winnings:.2f}"
        else:
            channel_text = f"{username} проигрыш ${bet:.2f} 💰 в игре ❣️"
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_text, reply_markup=kb, parse_mode="HTML")

        # Отправляем DM
        await send_result_dm(bot, user, user_id, bet, winnings, is_win, "❣️")

        await send_hearts_log(bot, user_id=user_id, user=user, bet=bet, win=is_win, choice=choice, result=result, winnings=winnings)

        return channel_text, new_balance, winnings, result

    except Exception as e:
        logging.error(f"Unexpected error in play_hearts for user_id={user_id}: {e}")
        await bot.send_message(chat_id=CHANNEL_ID, text="❌ Произошла ошибка. Попробуйте позже.", parse_mode="HTML")
        return "Ошибка", user_balance, 0, "none"



@with_user_lock
async def play_slots(
        bot: Bot,
        user_id: int,
        user: User,
        bet: float,
        chat_id: int,
):
    user_data = get_user_data(user_id)
    user_balance = user_data.get("balance", 0)
    user_name = user_data.get("user_name") or "Аноним"
    user_level = get_user_level(user_id)

    logging.debug(f"play_slots called for user_id={user_id}, bet={bet}, balance={user_balance}")

    if bet < 0.1 or bet > 200:
        logging.debug(f"Invalid bet amount for user_id={user_id}: {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ Сумма ставки должна быть от $0.1 до $200.")
        return "Неверная сумма ставки", user_balance, 0

    if user_balance < bet:
        logging.debug(f"Insufficient balance for user_id={user_id}: {user_balance} < {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ У вас недостаточно денег для ставки!")
        return "❌ У вас недостаточно денег для ставки!", user_balance, 0

    max_retries = 5
    retry_delay = 0.1
    try:
        # Log turnover
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging turnover for user_id={user_id}, amount={bet}")
                add_turnover(user_id, bet)
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_slots (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0
            except sqlite3.Error as e:
                logging.error(f"Database error in play_slots (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0

        initial_caption = (
            f"🎰 <b>Игра: Слоты</b>\n\n"
            f"💸 Ставка: ${bet:.2f}\n"
            f"🔄 Крутим барабаны..."
        )
        try:
            username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
            announcement = (
                f"🎉 Новая ставка в канале!\n<blockquote>🎮 Информация о ставке:\n┣ Ставка \n┣ 🥷🏻 Игрок: {username}\n┣ 🎰 Исход: 🎰\n┗ 💸 Сумма: ${bet:.2f}\n</blockquote>@WinRemboBot"
            )
        except Exception as e:
            logging.error(f'Failed build announcement: {e}')
            announcement = initial_caption
        await bot.send_message(chat_id=CHANNEL_ID, text=announcement, parse_mode='HTML')
        await bot.send_message(chat_id=user_id, text="✅ Ставка принята! Бросаем...")

        # Send slot machine animation
        dice = await bot.send_dice(chat_id=user_id, emoji="🎰")
        await asyncio.sleep(4)  # Wait for animation to complete
        
        # Get the dice result (1-64 for slot machine)
        dice_value = dice.dice.value

        # Telegram кодирует три барабана слот-машины числом 1..64 как
        # три независимых "цифры" по основанию 4 (реальная механика
        # официальной анимации 🎰, а не произвольные офсеты):
        #   reel0 = (value-1) % 4
        #   reel1 = ((value-1) // 4) % 4
        #   reel2 = ((value-1) // 16) % 4
        # Это гарантирует, что то, что видно в анимации (три одинаковых
        # символа при джекпоте и т.п.), совпадает с тем, что мы считаем
        # выигрышем — а не всегда разные символы, как было раньше.
        slot_symbols = ["BAR", "🍇", "🍋", "7️⃣"]  # порядок как в реальном Telegram slot
        idx0 = (dice_value - 1) % 4
        idx1 = ((dice_value - 1) // 4) % 4
        idx2 = ((dice_value - 1) // 16) % 4
        symbol1 = slot_symbols[idx0]
        symbol2 = slot_symbols[idx1]
        symbol3 = slot_symbols[idx2]

        # Define winning combinations and multipliers (только полное совпадение
        # трёх одинаковых символов — так это работает у настоящего Telegram-слота)
        SLOTS_COMBINATIONS = {
            ("7️⃣", "7️⃣", "7️⃣"): 10.0,  # Jackpot
            ("BAR", "BAR", "BAR"): 5.0,
            ("🍋", "🍋", "🍋"): 3.0,
            ("🍇", "🍇", "🍇"): 1.5,
        }

        combination = (symbol1, symbol2, symbol3)
        multiplier = SLOTS_COMBINATIONS.get(combination, 0.0)

        winnings = round(bet * multiplier, 2)
        new_balance = round(user_balance - bet + winnings, 2)
        is_win = winnings > 0

        # Update database
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging game play for user_id={user_id}")
                add_game_played(user_id)
                logging.debug(f"Logging coefficient for user_id={user_id}, coefficient={multiplier}")
                add_coefficient(user_id, multiplier)
                if winnings > 0:
                    logging.debug(f"Logging win for user_id={user_id}, winnings={winnings}")
                    add_winning(user_id, winnings)
                update_user_balance(user_id, new_balance)
                logging.debug(f"Updated balance for user_id={user_id}, new_balance={new_balance}")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_slots for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0
            except sqlite3.Error as e:
                logging.error(f"Database error in play_slots for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0

        # Отправляем результат в канал
        username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰Наш бот", url="https://t.me/WinRemboBot")]])
        if is_win:
            channel_text = f"[🎉] {username} вы забрали свой выигрыш!\n\n💸 Ставка - ${bet:.2f} \n✅ Выигрыш - ${winnings:.2f}"
        else:
            channel_text = f"{username} проигрыш ${bet:.2f} 💰 в игре 🎰"
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_text, reply_markup=kb, parse_mode="HTML")

        # Отправляем DM
        await send_result_dm(bot, user, user_id, bet, winnings, is_win, "🎰")

        return channel_text, new_balance, winnings

    except Exception as e:
        logging.error(f"Error in play_slots: {e}\n{traceback.format_exc()}")
        await bot.send_message(chat_id=CHANNEL_ID, text="❌ Произошла ошибка. Попробуйте позже.")
        return "Ошибка", user_balance, 0


@with_user_lock
async def play_dice(
        bot: Bot,
        user_id: int,
        user: User,
        bet: float,
        chat_id: int,
        choice: str,
):
    user_data = get_user_data(user_id)
    user_balance = user_data.get("balance", 0)
    user_name = user_data.get("user_name") or user.full_name or "Аноним"
    user_level = get_user_level(user_id)

    logging.debug(f"play_dice called for user_id={user_id}, bet={bet}, choice={choice}, balance={user_balance}")

    if bet < 0.1 or bet > 200:
        logging.debug(f"Invalid bet amount for user_id={user_id}: {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ Сумма ставки должна быть от $0.1 до $200.", parse_mode="HTML")
        return "Неверная сумма ставки", user_balance, 0, 0

    if user_balance < bet:
        logging.debug(f"Insufficient balance for user_id={user_id}: {user_balance} < {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ У вас недостаточно денег для ставки!", parse_mode="HTML")
        return "Недостаточно средств", user_balance, 0, 0

    if choice not in ["more", "less"]:
        logging.debug(f"Invalid choice for user_id={user_id}: {choice}")
        await bot.send_message(chat_id=chat_id, text="❌ Неверный выбор. Выберите 'Больше' или 'Меньше'.", parse_mode="HTML")
        return "Неверный выбор", user_balance, 0, 0

    max_retries = 5
    retry_delay = 0.1
    try:
        # Log turnover
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging turnover for user_id={user_id}, amount={bet}")
                add_turnover(user_id, bet)
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_dice (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, 0
            except sqlite3.Error as e:
                logging.error(f"Database error in play_dice (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, 0

        choice_display = {"more": "🔼 Больше", "less": "🔽 Меньше"}
        initial_caption = (
            f"Ставка в игре «Больше/Меньше»\n\n"
            f"♥️ Ставка: {choice_display[choice]}\n"
            f"💸 Сумма: ${bet:.2f}\n"
            f"⤷ Коэффициент: x{DICE_WIN_MULTIPLIER:.1f}\n"
            f"⭐️ Потенциал:\n"
            f"⤷ ${bet:.2f} x {DICE_WIN_MULTIPLIER:.1f} ➤ ${round(bet * DICE_WIN_MULTIPLIER, 2):.2f}"
        )
        try:
            username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
            announcement = (
                f"🎉 Новая ставка в канале!\n<blockquote>🎮 Информация о ставке:\n┣ Ставка \n┣ 🥷🏻 Игрок: {username}\n┣ 🎰 Исход: {choice_display[choice]} 🎲\n┗ 💸 Сумма: ${bet:.2f}\n</blockquote>@WinRemboBot"
            )
        except Exception as e:
            logging.error(f'Failed build announcement: {e}')
            announcement = initial_caption
        await bot.send_message(chat_id=CHANNEL_ID, text=announcement, parse_mode='HTML')
        await bot.send_message(chat_id=user_id, text="✅ Ставка принята! Бросаем...")

        dice = await bot.send_dice(chat_id=user_id, emoji="🎲")
        await asyncio.sleep(4)
        result = dice.dice.value

        is_win = (choice == "more" and result in [4, 5, 6]) or (choice == "less" and result in [1, 2, 3])
        multiplier = DICE_WIN_MULTIPLIER if is_win else 0.0
        winnings = round(bet * multiplier, 2) if is_win else 0
        new_balance = round(user_balance - bet + winnings, 2)

        # Update database
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging game play for user_id={user_id}")
                add_game_played(user_id)
                logging.debug(f"Logging coefficient for user_id={user_id}, coefficient={multiplier}")
                add_coefficient(user_id, multiplier)
                if winnings > 0:
                    logging.debug(f"Logging win for user_id={user_id}, winnings={winnings}")
                    add_winning(user_id, winnings)
                update_user_balance(user_id, new_balance)
                logging.debug(f"Updated balance for user_id={user_id}, new_balance={new_balance}")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_dice for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, 0
            except sqlite3.Error as e:
                logging.error(f"Database error in play_dice for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, 0

        # Отправляем результат в канал
        username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰Наш бот", url="https://t.me/WinRemboBot")]])
        if is_win:
            channel_text = f"[🎉] {username} вы забрали свой выигрыш!\n\n💸 Ставка - ${bet:.2f} \n✅ Выигрыш - ${winnings:.2f}"
        else:
            channel_text = f"{username} проигрыш ${bet:.2f} 💰 в игре 🎲"
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_text, reply_markup=kb, parse_mode="HTML")

        # Отправляем DM
        await send_result_dm(bot, user, user_id, bet, winnings, is_win, "🎲")

        return channel_text, new_balance, winnings, result

    except Exception as e:
        logging.error(f"Unexpected error in play_dice for user_id={user_id}: {e}")
        await bot.send_message(chat_id=CHANNEL_ID, text="❌ Произошла ошибка. Попробуйте позже.", parse_mode="HTML")
        return "Ошибка", user_balance, 0, 0


@with_user_lock
async def play_darts(
        bot: Bot,
        user_id: int,
        user: User,
        bet: float,
        chat_id: int,
        choice: str,
):
    user_data = get_user_data(user_id)
    user_balance = user_data.get("balance", 0)
    user_name = user_data.get("user_name") or "Аноним"
    user_level = get_user_level(user_id)

    logging.debug(f"play_darts called for user_id={user_id}, bet={bet}, choice={choice}, balance={user_balance}")

    if bet < 0.1 or bet > 200:
        logging.debug(f"Invalid bet amount for user_id={user_id}: {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ Сумма ставки должна быть от $0.1 до $200.")
        return "Неверная сумма ставки", user_balance, 0, "none"

    if user_balance < bet:
        logging.debug(f"Insufficient balance for user_id={user_id}: {user_balance} < {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ У вас недостаточно денег для ставки!")
        return "❌ У вас недостаточно денег для ставки!", user_balance, 0, "none"

    if choice not in ["red", "white", "center"]:
        logging.debug(f"Invalid choice for user_id={user_id}: {choice}")
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Неверный выбор. Выберите 'Красное', 'Белое' или 'Центер'.",
        )
        return "Неверный выбор", user_balance, 0, "none"

    max_retries = 5
    retry_delay = 0.1
    try:
        # Log turnover
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging turnover for user_id={user_id}, amount={bet}")
                add_turnover(user_id, bet)
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_darts (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, "none"
            except sqlite3.Error as e:
                logging.error(f"Database error in play_darts (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, "none"

        result_display = {"red": "🔴 Красное", "white": "⚪️ Белое", "center": "🍎 Центер", "miss": "❌ Мимо"}
        choice_display = result_display.get(choice, "Неизвестно")
        multiplier = DARTS_MULTIPLIERS.get(choice, 0.0)
        potential = round(bet * multiplier, 2) if multiplier > 0 else 0

        initial_caption = (
            f"Ставка в игре «Дартс»\n\n"
            f"🎯 Ставка: {choice_display}\n"
            f"💸 Сумма: ${bet:.2f}\n"
            f"⤷ Коэффициент: x{multiplier}\n"
            f"⭐️ Потенциал:\n"
            f"⤷ ${bet:.2f} x {multiplier} ➤ ${potential:.2f}"
        )
        try:
            username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
            announcement = (
                f"🎉 Новая ставка в канале!\n<blockquote>🎮 Информация о ставке:\n┣ Ставка \n┣ 🥷🏻 Игрок: {username}\n┣ 🎰 Исход: {choice_display} 🎯\n┗ 💸 Сумма: ${bet:.2f}\n</blockquote>@WinRemboBot"
            )
        except Exception as e:
            logging.error(f'Failed build announcement: {e}')
            announcement = initial_caption
        await bot.send_message(chat_id=CHANNEL_ID, text=announcement, parse_mode='HTML')
        await bot.send_message(chat_id=user_id, text="✅ Ставка принята! Бросаем...")

        dart = await bot.send_dice(chat_id=user_id, emoji="🎯")
        await asyncio.sleep(4)
        dart_value = dart.dice.value
        
        # Маппинг значений дартса
        outcomes = {
            4: "red",    # Внешнее красное кольцо
            2: "red",    # Внешнее красное кольцо (другой сектор)
            5: "white",  # Внешнее белое кольцо
            3: "white",  # Внешнее белое кольцо (другой сектор)
            6: "center", # Яблочко
            1: "miss"    # Промах
        }
        result = outcomes.get(dart_value, "miss")

        is_win = result == choice and choice != "miss"
        winnings = round(bet * multiplier, 2) if is_win else 0
        new_balance = round(user_balance - bet + winnings, 2)

        # Update database
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging game play for user_id={user_id}")
                add_game_played(user_id)
                logging.debug(f"Logging coefficient for user_id={user_id}, coefficient={multiplier if is_win else 0.0}")
                add_coefficient(user_id, multiplier if is_win else 0.0)
                if winnings > 0:
                    logging.debug(f"Logging win for user_id={user_id}, winnings={winnings}")
                    add_winning(user_id, winnings)
                update_user_balance(user_id, new_balance)
                logging.debug(f"Updated balance for user_id={user_id}, new_balance={new_balance}")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_darts for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, "none"
            except sqlite3.Error as e:
                logging.error(f"Database error in play_darts for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, "none"

        # Отправляем результат в канал
        username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰Наш бот", url="https://t.me/WinRemboBot")]])
        if is_win:
            channel_text = f"[🎉] {username} вы забрали свой выигрыш!\n\n💸 Ставка - ${bet:.2f} \n✅ Выигрыш - ${winnings:.2f}"
        else:
            channel_text = f"{username} проигрыш ${bet:.2f} 💰 в игре 🎯"
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_text, reply_markup=kb, parse_mode="HTML")

        # Отправляем DM
        await send_result_dm(bot, user, user_id, bet, winnings, is_win, "🎯")

        await send_darts_log(bot, user_id=user_id, user=user, bet=bet, win=is_win, result=result, winnings=winnings)

        return channel_text, new_balance, winnings, result

    except Exception as e:
        logging.error(f"Unexpected error in play_darts for user_id={user_id}: {e}")
        await bot.send_message(chat_id=CHANNEL_ID, text="❌ Произошла ошибка. Попробуйте позже.")
        return "Ошибка", user_balance, 0, "none"


@with_user_lock
async def play_football(
        bot: Bot,
        user_id: int,
        user: User,
        bet: float,
        chat_id: int,
        choice: str,
):
    user_data = get_user_data(user_id)
    user_balance = user_data.get("balance", 0)
    user_name = user_data.get("user_name") or "Аноним"
    user_level = get_user_level(user_id)

    logging.debug(f"play_football called for user_id={user_id}, bet={bet}, choice={choice}, balance={user_balance}")

    if bet < 0.1 or bet > 200:
        logging.debug(f"Invalid bet amount for user_id={user_id}: {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ Сумма ставки должна быть от $0.1 до $200.")
        return "Неверная сумма ставки", user_balance, 0, "none"

    if user_balance < bet:
        logging.debug(f"Insufficient balance for user_id={user_id}: {user_balance} < {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ У вас недостаточно денег для ставки!")
        return "❌ У вас недостаточно денег для ставки!", user_balance, 0, "none"

    max_retries = 5
    retry_delay = 0.1
    try:
        # Log turnover
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging turnover for user_id={user_id}, amount={bet}")
                add_turnover(user_id, bet)
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_football (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, "none"
            except sqlite3.Error as e:
                logging.error(f"Database error in play_football (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, "none"

        result_display = {"goal": "✅ Гол", "miss": "💨 Мимо"}
        choice_display = result_display.get(choice, "Неизвестно")
        multiplier = FOOTBALL_MULTIPLIERS.get(choice, 0.0)
        potential = round(bet * multiplier, 2) if multiplier > 0 else 0

        initial_caption = (
            f"Ставка в игре «Футбол»\n\n"
            f"⚽️ Ставка: {choice_display}\n"
            f"💸 Сумма: ${bet:.2f}\n"
            f"⤷ Коэффициент: x{multiplier}\n"
            f"⭐️ Потенциал:\n"
            f"⤷ ${bet:.2f} x {multiplier} ➤ ${potential:.2f}"
        )
        try:
            username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
            announcement = (
                f"🎉 Новая ставка в канале!\n<blockquote>🎮 Информация о ставке:\n┣ Ставка \n┣ 🥷🏻 Игрок: {username}\n┣ 🎰 Исход: {choice_display} ⚽️\n┗ 💸 Сумма: ${bet:.2f}\n</blockquote>@WinRemboBot"
            )
        except Exception as e:
            logging.error(f'Failed build announcement: {e}')
            announcement = initial_caption
        await bot.send_message(chat_id=CHANNEL_ID, text=announcement, parse_mode='HTML')
        await bot.send_message(chat_id=user_id, text="✅ Ставка принята! Бросаем...")

        football = await bot.send_dice(chat_id=user_id, emoji="⚽️")
        await asyncio.sleep(4)
        football_value = football.dice.value
        
        # Маппинг значений футбола
        outcomes = {
            1: "miss",  # Далеко от ворот
            2: "miss",  # Мимо ворот
            3: "goal",  # Гол
            4: "goal",  # Гол (другой вариант)
            5: "goal",  # Гол (еще вариант)
            6: "miss"   # Вратарь поймал
        }
        result = outcomes.get(football_value, "miss")

        is_win = result == choice
        winnings = round(bet * multiplier, 2) if is_win else 0
        new_balance = round(user_balance - bet + winnings, 2)

        # Update database
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging game play for user_id={user_id}")
                add_game_played(user_id)
                logging.debug(f"Logging coefficient for user_id={user_id}, coefficient={multiplier if is_win else 0.0}")
                add_coefficient(user_id, multiplier if is_win else 0.0)
                if winnings > 0:
                    logging.debug(f"Logging win for user_id={user_id}, winnings={winnings}")
                    add_winning(user_id, winnings)
                update_user_balance(user_id, new_balance)
                logging.debug(f"Updated balance for user_id={user_id}, new_balance={new_balance}")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_football for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, "none"
            except sqlite3.Error as e:
                logging.error(f"Database error in play_football for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, "none"

        # Отправляем результат в канал
        username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰Наш бот", url="https://t.me/WinRemboBot")]])
        if is_win:
            channel_text = f"[🎉] {username} вы забрали свой выигрыш!\n\n💸 Ставка - ${bet:.2f} \n✅ Выигрыш - ${winnings:.2f}"
        else:
            channel_text = f"{username} проигрыш ${bet:.2f} 💰 в игре ⚽️"
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_text, reply_markup=kb, parse_mode="HTML")

        # Отправляем DM
        await send_result_dm(bot, user, user_id, bet, winnings, is_win, "⚽️")

        await send_football_log(bot, user_id=user_id, user=user, bet=bet, win=is_win, result=result, dice_value=football_value, winnings=winnings)

        return channel_text, new_balance, winnings, result

    except Exception as e:
        logging.error(f"Unexpected error in play_football for user_id={user_id}: {e}")
        await bot.send_message(chat_id=CHANNEL_ID, text="❌ Произошла ошибка. Попробуйте позже.")
        return "Ошибка", user_balance, 0, "none"


@with_user_lock
async def play_basketball(
        bot: Bot,
        user_id: int,
        user: User,
        bet: float,
        chat_id: int,
        choice: str,
):
    user_data = get_user_data(user_id)
    user_balance = user_data.get("balance", 0)
    user_name = user_data.get("user_name") or "Аноним"
    user_level = get_user_level(user_id)

    logging.debug(f"play_basketball called for user_id={user_id}, bet={bet}, choice={choice}, balance={user_balance}")

    if bet < 0.1 or bet > 200:
        logging.debug(f"Invalid bet amount for user_id={user_id}: {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ Сумма ставки должна быть от $0.1 до $200.")
        return "Неверная сумма ставки", user_balance, 0, "none"

    if user_balance < bet:
        logging.debug(f"Insufficient balance for user_id={user_id}: {user_balance} < {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ У вас недостаточно денег для ставки!")
        return "❌ У вас недостаточно денег для ставки!", user_balance, 0, "none"

    max_retries = 5
    retry_delay = 0.1
    try:
        # Log turnover
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging turnover for user_id={user_id}, amount={bet}")
                add_turnover(user_id, bet)
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_basketball (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, "none"
            except sqlite3.Error as e:
                logging.error(f"Database error in play_basketball (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, "none"

        result_display = {"goal": "✅ Гол", "miss": "💨 Мимо"}
        choice_display = result_display.get(choice, "Неизвестно")
        multiplier = BASKETBALL_MULTIPLIERS.get(choice, 0.0)
        potential = round(bet * multiplier, 2) if multiplier > 0 else 0

        initial_caption = (
            f"Ставка в игре «Баскетбол»\n\n"
            f"🏀 Ставка: {choice_display}\n"
            f"💸 Сумма: ${bet:.2f}\n"
            f"⤷ Коэффициент: x{multiplier}\n"
            f"⭐️ Потенциал:\n"
            f"⤷ ${bet:.2f} x {multiplier} ➤ ${potential:.2f}"
        )
        try:
            username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
            announcement = (
                f"🎉 Новая ставка в канале!\n<blockquote>🎮 Информация о ставке:\n┣ Ставка \n┣ 🥷🏻 Игрок: {username}\n┣ 🎰 Исход: {choice_display} 🏀\n┗ 💸 Сумма: ${bet:.2f}\n</blockquote>@WinRemboBot"
            )
        except Exception as e:
            logging.error(f'Failed build announcement: {e}')
            announcement = initial_caption
        await bot.send_message(chat_id=CHANNEL_ID, text=announcement, parse_mode='HTML')
        await bot.send_message(chat_id=user_id, text="✅ Ставка принята! Бросаем...")

        basketball = await bot.send_dice(chat_id=user_id, emoji="🏀")
        await asyncio.sleep(4)
        basketball_value = basketball.dice.value
        
        # Маппинг значений баскетбола
        outcomes = {
            1: "miss",  # Мимо
            2: "miss",  # Мимо
            3: "miss",  # Мимо
            4: "goal",  # Гол
            5: "goal"   # Гол
        }
        result = outcomes.get(basketball_value, "miss")

        is_win = result == choice
        winnings = round(bet * multiplier, 2) if is_win else 0
        new_balance = round(user_balance - bet + winnings, 2)

        # Update database
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging game play for user_id={user_id}")
                add_game_played(user_id)
                logging.debug(f"Logging coefficient for user_id={user_id}, coefficient={multiplier if is_win else 0.0}")
                add_coefficient(user_id, multiplier if is_win else 0.0)
                if winnings > 0:
                    logging.debug(f"Logging win for user_id={user_id}, winnings={winnings}")
                    add_winning(user_id, winnings)
                update_user_balance(user_id, new_balance)
                logging.debug(f"Updated balance for user_id={user_id}, new_balance={new_balance}")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_basketball for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, "none"
            except sqlite3.Error as e:
                logging.error(f"Database error in play_basketball for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, "none"

        # Отправляем результат в канал
        username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰Наш бот", url="https://t.me/WinRemboBot")]])
        if is_win:
            channel_text = f"[🎉] {username} вы забрали свой выигрыш!\n\n💸 Ставка - ${bet:.2f} \n✅ Выигрыш - ${winnings:.2f}"
        else:
            channel_text = f"{username} проигрыш ${bet:.2f} 💰 в игре 🏀"
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_text, reply_markup=kb, parse_mode="HTML")

        # Отправляем DM
        await send_result_dm(bot, user, user_id, bet, winnings, is_win, "🏀")

        await send_basketball_log(bot, user_id=user_id, user=user, bet=bet, win=is_win, result=result, dice_value=basketball_value, winnings=winnings)

        return channel_text, new_balance, winnings, result

    except Exception as e:
        logging.error(f"Unexpected error in play_basketball for user_id={user_id}: {e}")
        await bot.send_message(chat_id=CHANNEL_ID, text="❌ Произошла ошибка. Попробуйте позже.")
        return "Ошибка", user_balance, 0, "none"


@with_user_lock
async def play_bowling(
        bot: Bot,
        user_id: int,
        user: User,
        bet: float,
        chat_id: int,
        choice: str,
):
    user_data = get_user_data(user_id)
    user_balance = user_data.get("balance", 0)
    user_name = user_data.get("user_name") or "Аноним"
    user_level = get_user_level(user_id)

    logging.debug(f"play_bowling called for user_id={user_id}, bet={bet}, choice={choice}, balance={user_balance}")

    if bet < 0.1 or bet > 200:
        logging.debug(f"Invalid bet amount for user_id={user_id}: {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ Сумма ставки должна быть от $0.1 до $200.")
        return "Неверная сумма ставки", user_balance, 0, 0

    if user_balance < bet:
        logging.debug(f"Insufficient balance for user_id={user_id}: {user_balance} < {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ У вас недостаточно денег для ставки!")
        return "❌ У вас недостаточно денег для ставки!", user_balance, 0, 0

    max_retries = 5
    retry_delay = 0.1
    try:
        # Log turnover
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging turnover for user_id={user_id}, amount={bet}")
                add_turnover(user_id, bet)
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_bowling (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, 0
            except sqlite3.Error as e:
                logging.error(f"Database error in play_bowling (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, 0

        result_display = {"strike": "✅ Страйк", "miss": "💨 Мимо"}
        choice_display = result_display.get(choice, "Неизвестно")
        multiplier = BOWLING_MULTIPLIERS.get(choice, 0.0)
        potential = round(bet * multiplier, 2) if multiplier > 0 else 0

        initial_caption = (
            f"Ставка в игре «Боулинг»\n\n"
            f"🎳 Ставка: {choice_display}\n"
            f"💸 Сумма: ${bet:.2f}\n"
            f"⤷ Коэффициент: x{multiplier}\n"
            f"⭐️ Потенциал:\n"
            f"⤷ ${bet:.2f} x {multiplier} ➤ ${potential:.2f}"
        )
        try:
            username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
            announcement = (
                f"🎉 Новая ставка в канале!\n<blockquote>🎮 Информация о ставке:\n┣ Ставка \n┣ 🥷🏻 Игрок: {username}\n┣ 🎰 Исход: {choice_display} 🎳\n┗ 💸 Сумма: ${bet:.2f}\n</blockquote>@WinRemboBot"
            )
        except Exception as e:
            logging.error(f'Failed build announcement: {e}')
            announcement = initial_caption
        await bot.send_message(chat_id=CHANNEL_ID, text=announcement, parse_mode='HTML')
        await bot.send_message(chat_id=user_id, text="✅ Ставка принята! Бросаем...")

        bowling = await bot.send_dice(chat_id=user_id, emoji="🎳")
        await asyncio.sleep(4)
        bowling_value = bowling.dice.value

        # Маппинг значений боулинга
        outcomes = {
            1: "miss",
            2: "miss",
            3: "miss",
            4: "miss",
            5: "miss",
            6: "strike"  # Страйк
        }
        result = outcomes.get(bowling_value, "miss")

        is_win = result == choice
        winnings = round(bet * multiplier, 2) if is_win else 0
        new_balance = round(user_balance - bet + winnings, 2)

        # Update database
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging game play for user_id={user_id}")
                add_game_played(user_id)
                logging.debug(f"Logging coefficient for user_id={user_id}, coefficient={multiplier if is_win else 0.0}")
                add_coefficient(user_id, multiplier if is_win else 0.0)
                if winnings > 0:
                    logging.debug(f"Logging win for user_id={user_id}, winnings={winnings}")
                    add_winning(user_id, winnings)
                update_user_balance(user_id, new_balance)
                logging.debug(f"Updated balance for user_id={user_id}, new_balance={new_balance}")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_bowling for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, 0
            except sqlite3.Error as e:
                logging.error(f"Database error in play_bowling for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.")
                return "Ошибка базы данных", user_balance, 0, 0

        # Отправляем результат в канал
        username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰Наш бот", url="https://t.me/WinRemboBot")]])
        if is_win:
            channel_text = f"[🎉] {username} вы забрали свой выигрыш!\n\n💸 Ставка - ${bet:.2f} \n✅ Выигрыш - ${winnings:.2f}"
        else:
            channel_text = f"{username} проигрыш ${bet:.2f} 💰 в игре 🎳"
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_text, reply_markup=kb, parse_mode="HTML")

        # Отправляем DM
        await send_result_dm(bot, user, user_id, bet, winnings, is_win, "🎳")

        await send_bowling_log(bot, user_id=user_id, user=user, bet=bet, win=is_win, result=result, dice_value=bowling_value, winnings=winnings)

        return channel_text, new_balance, winnings, result

    except Exception as e:
        logging.error(f"Unexpected error in play_bowling for user_id={user_id}: {e}")
        await bot.send_message(chat_id=CHANNEL_ID, text="❌ Произошла ошибка. Попробуйте позже.")
        return "Ошибка", user_balance, 0, 0


@with_user_lock
async def play_even_odd(
        bot: Bot,
        user_id: int,
        user: User,
        bet: float,
        chat_id: int,
        choice: str,
):
    user_data = get_user_data(user_id)
    user_balance = user_data.get("balance", 0)
    user_name = user_data.get("user_name") or user.full_name or "Аноним"
    user_level = get_user_level(user_id)

    logging.debug(f"play_even_odd called for user_id={user_id}, bet={bet}, choice={choice}, balance={user_balance}")

    if bet < 0.1 or bet > 200:
        logging.debug(f"Invalid bet amount for user_id={user_id}: {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ Сумма ставки должна быть от $0.1 до $200.", parse_mode="HTML")
        return "Неверная сумма ставки", user_balance, 0, 0

    if user_balance < bet:
        logging.debug(f"Insufficient balance for user_id={user_id}: {user_balance} < {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ У вас недостаточно денег для ставки!", parse_mode="HTML")
        return "Недостаточно средств", user_balance, 0, 0

    if choice not in ["even", "odd"]:
        logging.debug(f"Invalid choice for user_id={user_id}: {choice}")
        await bot.send_message(chat_id=chat_id, text="❌ Неверный выбор. Выберите 'Четное' или 'Нечетное'.", parse_mode="HTML")
        return "Неверный выбор", user_balance, 0, 0

    max_retries = 5
    retry_delay = 0.1

    try:
        # Log turnover
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging turnover for user_id={user_id}, amount={bet}")
                add_turnover(user_id, bet)
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_even_odd (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, 0
            except sqlite3.Error as e:
                logging.error(f"Database error in play_even_odd (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, 0

        choice_display = {"even": "🔘 Четное", "odd": "⚫️ Нечетное"}
        initial_caption = (
            f"Ставка в игре «Чет/Нечет»\n\n"
            f"🎲 Ставка: {choice_display[choice]}\n"
            f"💸 Сумма: ${bet:.2f}\n"
            f"⤷ Коэффициент: x{EVEN_ODD_MULTIPLIER:.1f}\n"
            f"⭐️ Потенциал:\n"
            f"⤷ ${bet:.2f} x {EVEN_ODD_MULTIPLIER:.1f} ➤ ${round(bet * EVEN_ODD_MULTIPLIER, 2):.2f}"
        )
        try:
            username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
            announcement = (
                f"🎉 Новая ставка в канале!\n<blockquote>🎮 Информация о ставке:\n┣ Ставка \n┣ 🥷🏻 Игрок: {username}\n┣ 🎰 Исход: {choice_display[choice]} 🔢\n┗ 💸 Сумма: ${bet:.2f}\n</blockquote>@WinRemboBot"
            )
        except Exception as e:
            logging.error(f'Failed build announcement: {e}')
            announcement = initial_caption
        await bot.send_message(chat_id=CHANNEL_ID, text=announcement, parse_mode='HTML')
        await bot.send_message(chat_id=user_id, text="✅ Ставка принята! Бросаем...")

        dice = await bot.send_dice(chat_id=user_id, emoji="🎲")
        await asyncio.sleep(4)
        result = dice.dice.value

        is_even = result % 2 == 0
        is_win = (choice == "even" and is_even) or (choice == "odd" and not is_even)
        multiplier = EVEN_ODD_MULTIPLIER if is_win else 0.0
        winnings = round(bet * multiplier, 2) if is_win else 0
        new_balance = round(user_balance - bet + winnings, 2)

        # Update database
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging game play for user_id={user_id}")
                add_game_played(user_id)
                logging.debug(f"Logging coefficient for user_id={user_id}, coefficient={multiplier}")
                add_coefficient(user_id, multiplier)
                if winnings > 0:
                    logging.debug(f"Logging win for user_id={user_id}, winnings={winnings}")
                    add_winning(user_id, winnings)
                update_user_balance(user_id, new_balance)
                logging.debug(f"Updated balance for user_id={user_id}, new_balance={new_balance}")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_even_odd for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, 0
            except sqlite3.Error as e:
                logging.error(f"Database error in play_even_odd for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, 0

        # Отправляем результат в канал
        username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰Наш бот", url="https://t.me/WinRemboBot")]])
        if is_win:
            channel_text = f"[🎉] {username} вы забрали свой выигрыш!\n\n💸 Ставка - ${bet:.2f} \n✅ Выигрыш - ${winnings:.2f}"
        else:
            channel_text = f"{username} проигрыш ${bet:.2f} 💰 в игре 🔢"
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_text, reply_markup=kb, parse_mode="HTML")

        # Отправляем DM
        await send_result_dm(bot, user, user_id, bet, winnings, is_win, "🔢")

        await send_even_odd_log(bot, user_id=user_id, user=user, bet=bet, win=is_win, result=result, choice=choice, winnings=winnings)

        return channel_text, new_balance, winnings, result

    except Exception as e:
        logging.error(f"Unexpected error in play_even_odd for user_id={user_id}: {e}")
        await bot.send_message(chat_id=CHANNEL_ID, text="❌ Произошла ошибка. Попробуйте позже.", parse_mode="HTML")
        return "Ошибка", user_balance, 0, 0


@with_user_lock
async def play_guess_number(
        bot: Bot,
        user_id: int,
        user: User,
        bet: float,
        guessed_number: int,
        chat_id: int,
):
    user_data = get_user_data(user_id)
    user_balance = user_data.get("balance", 0)
    user_name = user_data.get("user_name") or user.full_name or "Аноним"
    user_level = get_user_level(user_id)

    logging.debug(f"play_guess_number called for user_id={user_id}, bet={bet}, guessed_number={guessed_number}, balance={user_balance}")

    # Validate bet amount
    if bet < 0.1 or bet > 200:
        logging.debug(f"Invalid bet amount for user_id={user_id}: {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ Сумма ставки должна быть от $0.1 до $200.", parse_mode="HTML")
        return "Неверная сумма ставки", user_balance, 0, 0

    # Validate balance
    if user_balance < bet:
        logging.debug(f"Insufficient balance for user_id={user_id}: {user_balance} < {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ У вас недостаточно денег для ставки!", parse_mode="HTML")
        return "Недостаточно средств", user_balance, 0, 0

    # Validate guessed number
    if not isinstance(guessed_number, int) or guessed_number < 1 or guessed_number > 6:
        logging.debug(f"Invalid guessed number for user_id={user_id}: {guessed_number}")
        await bot.send_message(chat_id=chat_id, text="❌ Неверное число. Выберите число от 1 до 6.", parse_mode="HTML")
        return "Неверное число", user_balance, 0, 0

    max_retries = 5
    retry_delay = 0.1

    try:
        # Log turnover
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging turnover for user_id={user_id}, amount={bet}")
                add_turnover(user_id, bet)
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_guess_number (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, 0
            except sqlite3.Error as e:
                logging.error(f"Database error in play_guess_number (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, 0

        initial_caption = (
            f"Ставка в игре «Угадай число»\n\n"
            f"🎯 Число: {guessed_number}\n"
            f"💸 Сумма: ${bet:.2f}\n"
            f"⤷ Коэффициент: x{GUESS_NUMBER_MULTIPLIER:.1f}\n"
            f"⭐️ Потенциал:\n"
            f"⤷ ${bet:.2f} x {GUESS_NUMBER_MULTIPLIER:.1f} ➤ ${round(bet * GUESS_NUMBER_MULTIPLIER, 2):.2f}"
        )
        try:
            username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
            announcement = (
                f"🎉 Новая ставка в канале!\n<blockquote>🎮 Информация о ставке:\n┣ Ставка \n┣ 🥷🏻 Игрок: {username}\n┣ 🎰 Исход: {guessed_number} 🎲\n┗ 💸 Сумма: ${bet:.2f}\n</blockquote>@WinRemboBot"
            )
        except Exception as e:
            logging.error(f'Failed build announcement: {e}')
            announcement = initial_caption
        await bot.send_message(chat_id=CHANNEL_ID, text=announcement, parse_mode='HTML')
        await bot.send_message(chat_id=user_id, text="✅ Ставка принята! Бросаем...")

        dice = await bot.send_dice(chat_id=user_id, emoji="🎲")
        await asyncio.sleep(4)
        result = dice.dice.value

        is_win = result == guessed_number
        multiplier = GUESS_NUMBER_MULTIPLIER if is_win else 0.0
        winnings = round(bet * multiplier, 2) if is_win else 0
        new_balance = round(user_balance - bet + winnings, 2)

        # Update database
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging game play for user_id={user_id}")
                add_game_played(user_id)
                logging.debug(f"Logging coefficient for user_id={user_id}, coefficient={multiplier}")
                add_coefficient(user_id, multiplier)
                if winnings > 0:
                    logging.debug(f"Logging win for user_id={user_id}, winnings={winnings}")
                    add_winning(user_id, winnings)
                update_user_balance(user_id, new_balance)
                logging.debug(f"Updated balance for user_id={user_id}, new_balance={new_balance}")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_guess_number for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, 0
            except sqlite3.Error as e:
                logging.error(f"Database error in play_guess_number for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, 0

        # Отправляем результат в канал
        username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰Наш бот", url="https://t.me/WinRemboBot")]])
        if is_win:
            channel_text = f"[🎉] {username} вы забрали свой выигрыш!\n\n💸 Ставка - ${bet:.2f} \n✅ Выигрыш - ${winnings:.2f}"
        else:
            channel_text = f"{username} проигрыш ${bet:.2f} 💰 в игре 🎲"
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_text, reply_markup=kb, parse_mode="HTML")

        # Отправляем DM
        await send_result_dm(bot, user, user_id, bet, winnings, is_win, "🎲")

        await send_guess_number_log(bot, user_id=user_id, user=user, bet=bet, win=is_win, result=result, guessed=guessed_number, winnings=winnings)

        return channel_text, new_balance, winnings, result

    except Exception as e:
        logging.error(f"Unexpected error in play_guess_number for user_id={user_id}: {e}")
        await bot.send_message(chat_id=CHANNEL_ID, text="❌ Произошла ошибка. Попробуйте позже.", parse_mode="HTML")
        return "Ошибка", user_balance, 0, 0


@with_user_lock
async def play_double_dice(
        bot: Bot,
        user_id: int,
        user: User,
        bet: float,
        chat_id: int,
        choice: str,
):
    user_data = get_user_data(user_id)
    user_balance = user_data.get("balance", 0)
    user_name = user_data.get("user_name") or user.full_name or "Аноним"
    user_level = get_user_level(user_id)

    logging.debug(f"play_double_dice called for user_id={user_id}, bet={bet}, choice={choice}, balance={user_balance}")

    # Validate bet amount
    if bet < 0.1 or bet > 200:
        logging.debug(f"Invalid bet amount for user_id={user_id}: {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ Сумма ставки должна быть от $0.1 до $200.", parse_mode="HTML")
        return "Неверная сумма ставки", user_balance, 0, (0, 0)

    # Validate balance
    if user_balance < bet:
        logging.debug(f"Insufficient balance for user_id={user_id}: {user_balance} < {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ У вас недостаточно денег для ставки!", parse_mode="HTML")
        return "Недостаточно средств", user_balance, 0, (0, 0)

    # Validate choice
    if choice not in ["high", "low"]:
        logging.debug(f"Invalid choice for user_id={user_id}: {choice}")
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Неверный выбор. Выберите 'Два больше' или 'Два меньше'.",
            parse_mode="HTML"
        )
        return "Неверный выбор", user_balance, 0, (0, 0)

    max_retries = 5
    retry_delay = 0.1

    try:
        # Log turnover
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging turnover for user_id={user_id}, amount={bet}")
                add_turnover(user_id, bet)
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_double_dice (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, (0, 0)
            except sqlite3.Error as e:
                logging.error(f"Database error in play_double_dice (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, (0, 0)

        # Send initial message
        choice_display = {
            "high": "🔼 Два больше",
            "low": "🔽 Два меньше"
        }
        initial_caption = (
            f"Ставка в игре «Двойной кубик»\n\n"
            f"🎲 Ставка: {choice_display.get(choice, 'Неизвестно')}\n"
            f"💸 Сумма: ${bet:.2f}\n"
            f"⤷ Коэффициент: x{DOUBLE_DICE_MULTIPLIER:.2f}\n"
            f"⭐️ Потенциал:\n"
            f"⤷ ${bet:.2f} x {DOUBLE_DICE_MULTIPLIER:.2f} ➤ ${round(bet * DOUBLE_DICE_MULTIPLIER, 2):.2f}"
        )
        try:
            username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
            announcement = (
                f"🎉 Новая ставка в канале!\n<blockquote>🎮 Информация о ставке:\n┣ Ставка \n┣ 🥷🏻 Игрок: {username}\n┣ 🎰 Исход: {choice_display.get(choice, 'Неизвестно')} 🎲\n┗ 💸 Сумма: ${bet:.2f}\n</blockquote>@WinRemboBot"
            )
        except Exception as e:
            logging.error(f'Failed build announcement: {e}')
            announcement = initial_caption
        await bot.send_message(chat_id=CHANNEL_ID, text=announcement, parse_mode='HTML')
        await bot.send_message(chat_id=user_id, text="✅ Ставка принята! Бросаем...")

        # Roll two dice
        dice1 = await bot.send_dice(chat_id=user_id, emoji="🎲")
        await asyncio.sleep(4)
        dice2 = await bot.send_dice(chat_id=user_id, emoji="🎲")
        await asyncio.sleep(4)
        result = (dice1.dice.value, dice2.dice.value)

        is_win = False
        if choice == "high":
            is_win = result[0] in [4, 5, 6] and result[1] in [4, 5, 6]
        elif choice == "low":
            is_win = result[0] in [1, 2, 3] and result[1] in [1, 2, 3]

        multiplier = DOUBLE_DICE_MULTIPLIER if is_win else 0.0
        winnings = round(bet * multiplier, 2) if is_win else 0
        new_balance = round(user_balance - bet + winnings, 2)

        # Update database
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging game play for user_id={user_id}")
                add_game_played(user_id)
                logging.debug(f"Logging coefficient for user_id={user_id}, coefficient={multiplier}")
                add_coefficient(user_id, multiplier)
                if winnings > 0:
                    logging.debug(f"Logging win for user_id={user_id}, winnings={winnings}")
                    add_winning(user_id, winnings)
                update_user_balance(user_id, new_balance)
                logging.debug(f"Updated balance for user_id={user_id}, new_balance={new_balance}")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_double_dice for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, (0, 0)
            except sqlite3.Error as e:
                logging.error(f"Database error in play_double_dice for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, (0, 0)

        # Отправляем результат в канал
        username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰Наш бот", url="https://t.me/WinRemboBot")]])
        if is_win:
            channel_text = f"[🎉] {username} вы забрали свой выигрыш!\n\n💸 Ставка - ${bet:.2f} \n✅ Выигрыш - ${winnings:.2f}"
        else:
            channel_text = f"{username} проигрыш ${bet:.2f} 💰 в игре 🎲"
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_text, reply_markup=kb, parse_mode="HTML")

        # Отправляем DM
        await send_result_dm(bot, user, user_id, bet, winnings, is_win, "🎲")

        await send_double_dice_log(bot, user_id=user_id, user=user, bet=bet, win=is_win, result=result, choice=choice, winnings=winnings)

        return channel_text, new_balance, winnings, result

    except Exception as e:
        logging.error(f"Unexpected error in play_double_dice for user_id={user_id}: {e}")
        await bot.send_message(chat_id=CHANNEL_ID, text="❌ Произошла ошибка. Попробуйте позже.", parse_mode="HTML")
        return "Ошибка", user_balance, 0, (0, 0)


@with_user_lock
async def play_special_rps(
        bot: Bot,
        user_id: int,
        user: User,
        bet: float,
        chat_id: int,
        choice: str,
):
    user_data = get_user_data(user_id)
    user_balance = user_data.get("balance", 0)
    user_name = user_data.get("user_name") or user.full_name or "Аноним"
    user_level = get_user_level(user_id)

    logging.debug(f"play_special_rps called for user_id={user_id}, bet={bet}, choice={choice}, balance={user_balance}")

    if bet < 0.1 or bet > 200:
        logging.debug(f"Invalid bet amount for user_id={user_id}: {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ Сумма ставки должна быть от $0.1 до $200.", parse_mode="HTML")
        return "Неверная сумма ставки", user_balance, 0, "none"

    if user_balance < bet:
        logging.debug(f"Insufficient balance for user_id={user_id}: {user_balance} < {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ У вас недостаточно денег для ставки!", parse_mode="HTML")
        return "Недостаточно средств", user_balance, 0, "none"

    if choice not in ["rock", "paper", "scissors"]:
        logging.debug(f"Invalid choice for user_id={user_id}: {choice}")
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Неверный выбор. Выберите 'Камень', 'Ножницы' или 'Бумага'.",
            parse_mode="HTML"
        )
        return "Неверный выбор", user_balance, 0, "none"

    max_retries = 5
    retry_delay = 0.1

    try:
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging turnover for user_id={user_id}, amount={bet}")
                add_turnover(user_id, bet)
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_special_rps (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, "none"
            except sqlite3.Error as e:
                logging.error(f"Database error in play_special_rps (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, "none"

        choice_display = {
            "rock": "✊ Камень",
            "paper": "👋 Бумага",
            "scissors": "✌️ Ножницы"
        }
        emoji_display = {
            "rock": "✊",
            "paper": "👋",
            "scissors": "✌️"
        }
        initial_caption = (
            f"Ставка в игре «✂️ КНБ»\n\n"
            f"🎮 Выбор: {choice_display.get(choice, 'Неизвестно')}\n"
            f"💸 Сумма: ${bet:.2f}\n"
            f"⤷ Коэффициент: x{RPS_MULTIPLIER:.2f}\n"
            f"⭐️ Потенциал:\n"
            f"⤷ ${bet:.2f} x {RPS_MULTIPLIER:.2f} ➤ ${round(bet * RPS_MULTIPLIER, 2):.2f}"
        )
        try:
            username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
            announcement = (
                f"🎉 Новая ставка в канале!\n<blockquote>🎮 Информация о ставке:\n┣ Ставка \n┣ 🥷🏻 Игрок: {username}\n┣ 🎰 Исход: {choice_display.get(choice, 'Неизвестно')} ✂️\n┗ 💸 Сумма: ${bet:.2f}\n</blockquote>@WinRemboBot"
            )
        except Exception as e:
            logging.error(f'Failed build announcement: {e}')
            announcement = initial_caption
        await bot.send_message(chat_id=CHANNEL_ID, text=announcement, parse_mode='HTML')
        await bot.send_message(chat_id=user_id, text="✅ Ставка принята! Бросаем...")

        await bot.send_message(chat_id=CHANNEL_ID, text=f"{emoji_display.get(choice, '❓')}", parse_mode="HTML")
        await asyncio.sleep(1)

        bot_choice = random.choice(["rock", "paper", "scissors"])

        await bot.send_message(chat_id=CHANNEL_ID, text=f"{emoji_display.get(bot_choice, '❓')}", parse_mode="HTML")
        await asyncio.sleep(1)

        is_win = False
        if choice == bot_choice:
            result = "tie"
        elif (choice == "rock" and bot_choice == "scissors") or \
             (choice == "paper" and bot_choice == "rock") or \
             (choice == "scissors" and bot_choice == "paper"):
            is_win = True
            result = "win"
        else:
            result = "lose"

        multiplier = RPS_MULTIPLIER if is_win else 0.0
        winnings = round(bet * multiplier, 2) if is_win else 0
        new_balance = round(user_balance - bet + winnings, 2)

        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging game play for user_id={user_id}")
                add_game_played(user_id)
                logging.debug(f"Logging coefficient for user_id={user_id}, coefficient={multiplier}")
                add_coefficient(user_id, multiplier)
                if winnings > 0:
                    logging.debug(f"Logging win for user_id={user_id}, winnings={winnings}")
                    add_winning(user_id, winnings)
                update_user_balance(user_id, new_balance)
                logging.debug(f"Updated balance for user_id={user_id}, new_balance={new_balance}")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_special_rps for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, "none"
            except sqlite3.Error as e:
                logging.error(f"Database error in play_special_rps for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, "none"

        # Отправляем результат в канал
        username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰Наш бот", url="https://t.me/WinRemboBot")]])
        if is_win:
            channel_text = f"[🎉] {username} вы забрали свой выигрыш!\n\n💸 Ставка - ${bet:.2f} \n✅ Выигрыш - ${winnings:.2f}"
        else:
            channel_text = f"{username} проигрыш ${bet:.2f} 💰 в игре ✂️"
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_text, reply_markup=kb, parse_mode="HTML")

        # Отправляем DM
        await send_result_dm(bot, user, user_id, bet, winnings, is_win, "✂️")

        await send_special_rps_log(bot, user_id=user_id, user=user, bet=bet, win=is_win, result=(choice, bot_choice),
                                   winnings=winnings)

        return channel_text, new_balance, winnings, result

    except Exception as e:
        logging.error(f"Unexpected error in play_special_rps for user_id={user_id}: {e}")
        await bot.send_message(chat_id=CHANNEL_ID, text="❌ Произошла ошибка. Попробуйте позже.", parse_mode="HTML")
        return "Ошибка", user_balance, 0, "none"


@with_user_lock
async def play_russian_roulette(
    bot: Bot,
    user_id: int,
    user: User,
    bet: float,
    bullet_count: int,
    chat_id: int,
):
    user_data = get_user_data(user_id)
    logging.debug(f"Retrieved user_data for user_id={user_id}: type={type(user_data)}, value={user_data}")
    if not isinstance(user_data, dict):
        logging.error(f"Invalid user_data type for user_id={user_id}: expected dict, got {type(user_data)} with value {user_data}")
        await bot.send_message(chat_id=chat_id, text="❌ Ошибка: Данные пользователя повреждены.", parse_mode="HTML")
        try:
            user_data = json.loads(user_data) if isinstance(user_data, str) else {}
            logging.debug(f"Parsed user_data for user_id={user_id}: {user_data}")
        except json.JSONDecodeError:
            logging.error(f"Failed to parse user_data as JSON for user_id={user_id}: {user_data}")
            return "Ошибка данных", 0, 0, "none"
    user_balance = user_data.get("balance", 0)
    user_name = user_data.get("user_name") or user.full_name or "Аноним"
    user_level = get_user_level(user_id)

    logging.debug(f"play_russian_roulette called for user_id={user_id}, bet={bet}, bullet_count={bullet_count}, balance={user_balance}")

    if not isinstance(bet, (int, float)):
        logging.error(f"Invalid bet type for user_id={user_id}: {type(bet)}, value={bet}")
        await bot.send_message(chat_id=chat_id, text="❌ Ошибка: Неверный тип ставки.", parse_mode="HTML")
        return "Ошибка ставки", 0, 0, "none"

    if bet < 0.1 or bet > 200:
        logging.debug(f"Invalid bet amount for user_id={user_id}: {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ Сумма ставки должна быть от $0.1 до $200.", parse_mode="HTML")
        return "Неверная сумма ставки", user_balance, 0, "none"

    if user_balance < bet:
        logging.debug(f"Insufficient balance for user_id={user_id}: {user_balance} < {bet}")
        await bot.send_message(chat_id=chat_id, text="❌ У вас недостаточно денег для ставки!", parse_mode="HTML")
        return "Недостаточно средств", user_balance, 0, "none"

    if bullet_count not in [1, 2, 3, 4, 5]:
        logging.debug(f"Invalid bullet count for user_id={user_id}: {bullet_count}")
        await bot.send_message(chat_id=chat_id, text="❌ Неверное количество пуль. Выберите от 1 до 5.", parse_mode="HTML")
        return "Неверное количество пуль", user_balance, 0, "none"

    max_retries = 5
    retry_delay = 0.1
    try:
        # Log turnover
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging turnover for user_id={user_id}, amount={bet}")
                add_turnover(user_id, bet)
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_russian_roulette (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, "none"
            except sqlite3.Error as e:
                logging.error(f"Database error in play_russian_roulette (turnover) for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, "none"

        if not isinstance(RUSSIAN_ROULETTE_MULTIPLIERS, dict):
            logging.error(f"Invalid RUSSIAN_ROULETTE_MULTIPLIERS type: expected dict, got {type(RUSSIAN_ROULETTE_MULTIPLIERS)} with value {RUSSIAN_ROULETTE_MULTIPLIERS}")
            await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка: Неверная конфигурация игры.", parse_mode="HTML")
            return "Ошибка конфигурации", user_balance, 0, "none"

        multiplier = RUSSIAN_ROULETTE_MULTIPLIERS.get(bullet_count, 1.0)
        choice_display = {1: "💀 1 пуля", 2: "💀 2 пули", 3: "💀 3 пули", 4: "💀 4 пули", 5: "💀 5 пуль"}
        emoji_display = {1: "💀", 2: "💀💀", 3: "💀💀💀", 4: "💀💀💀💀", 5: "💀💀💀💀💀"}
        initial_caption = (
            f"🔫 <b>Русская Рулетка</b>\n\n"
            f"🎯 Выбор: {choice_display.get(bullet_count, 'Неизвестно')}\n"
            f"💸 Сумма: ${bet:.2f}\n"
            f"⤷ Коэффициент: x{multiplier:.2f}\n"
            f"⭐️ Потенциал:\n"
            f"⤷ ${bet:.2f} x {multiplier:.2f} ➤ ${round(bet * multiplier, 2):.2f}"
        )
        try:
            username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
            announcement = (
                f"🎉 Новая ставка в канале!\n\n\n\n🎮 Информация о ставке:\n┣ Ставка \n┣ 🥷🏻 Игрок: {username}\n┣ 🎰 Исход: {choice_display.get(bullet_count, 'Неизвестно')} 🔫\n┗ 💸 Сумма: ${bet:.2f}\n\n@WinRemboBot"
            )
        except Exception as e:
            logging.error(f'Failed build announcement: {e}')
            announcement = initial_caption
        await bot.send_message(chat_id=CHANNEL_ID, text=announcement, parse_mode='HTML')
        await bot.send_message(chat_id=user_id, text="✅ Ставка принята! Бросаем...")
        await asyncio.sleep(1.5)

        chambers = [True] * bullet_count + [False] * (6 - bullet_count)
        random.shuffle(chambers)
        is_win = not chambers[0]

        sticker_map = {
            1: {
                "win": [
                    "stickers/win1_bullets_1.tgs",
                    "stickers/win1_bullets_2.tgs",
                    "stickers/win1_bullets_3.tgs",
                    "stickers/win1_bullets_4.tgs",
                    "stickers/win1_bullets_5.tgs"
                ],
                "lose": ["stickers/lose1_bullets.tgs"]
            },
            2: {
                "win": ["stickers/win2_bullets_1.tgs", "stickers/win2_bullets_2.tgs"],
                "lose": ["stickers/lose2_bullets.tgs"]
            },
            3: {
                "win": ["stickers/win3_bullets_1.tgs", "stickers/win3_bullets_2.tgs", "stickers/win3_bullets_3.tgs"],
                "lose": ["stickers/lose3_bullets_1.tgs", "stickers/lose3_bullets_2.tgs", "stickers/lose3_bullets_3.tgs"]
            },
            4: {
                "win": ["stickers/win4_bullets_1.tgs"],
                "lose": ["stickers/lose4_bullets_1.tgs", "stickers/lose4_bullets_2.tgs"]
            },
            5: {
                "win": ["stickers/win5_bullets_1.tgs"],
                "lose": ["stickers/lose5_bullets_1.tgs", "stickers/lose5_bullets_2.tgs", "stickers/lose5_bullets_3.tgs", "stickers/lose5_bullets_4.tgs"]
            }
        }

        outcome = "win" if is_win else "lose"
        available_stickers = sticker_map.get(bullet_count, {}).get(outcome, [])
        if not available_stickers:
            logging.error(f"No stickers available for bullet_count={bullet_count}, outcome={outcome}")
            await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка: Стикер результата не найден!", parse_mode="HTML")
            return "Ошибка стикера результата", user_balance, 0, "none"

        sticker_outcome = random.choice(available_stickers)
        if not os.path.exists(sticker_outcome):
            logging.error(f"Outcome sticker not found: {sticker_outcome}")
            await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка: Стикер результата не найден!", parse_mode="HTML")
            return "Ошибка стикера результата", user_balance, 0, "none"
        sticker_file = FSInputFile(sticker_outcome)
        await bot.send_sticker(chat_id=CHANNEL_ID, sticker=sticker_file)
        await asyncio.sleep(1.5)  # Pause to allow sticker animation to play

        result = "win" if is_win else "lose"
        winnings = round(bet * multiplier, 2) if is_win else 0
        new_balance = round(user_balance - bet + winnings, 2)

        # Update database
        for attempt in range(max_retries):
            try:
                logging.debug(f"Logging game play for user_id={user_id}")
                add_game_played(user_id)
                logging.debug(f"Logging coefficient for user_id={user_id}, coefficient={multiplier if is_win else 0.0}")
                add_coefficient(user_id, multiplier if is_win else 0.0)
                if winnings > 0:
                    logging.debug(f"Logging win for user_id={user_id}, winnings={winnings}")
                    add_winning(user_id, winnings)
                update_user_balance(user_id, new_balance)
                logging.debug(f"Updated balance for user_id={user_id}, new_balance={new_balance}")
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error(f"Database error in play_russian_roulette for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, "none"
            except sqlite3.Error as e:
                logging.error(f"Database error in play_russian_roulette for user_id={user_id}: {e}")
                await bot.send_message(chat_id=CHANNEL_ID, text="❌ Ошибка базы данных. Попробуйте позже.", parse_mode="HTML")
                return "Ошибка базы данных", user_balance, 0, "none"

        # Отправляем результат в канал
        username = f"@{getattr(user, 'username', None) or getattr(user, 'full_name', 'Аноним')}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰Наш бот", url="https://t.me/WinRemboBot")]])
        if is_win:
            channel_text = f"[🎉] {username} вы забрали свой выигрыш!\n\n💸 Ставка - ${bet:.2f} \n✅ Выигрыш - ${winnings:.2f}"
        else:
            channel_text = f"{username} проигрыш ${bet:.2f} 💰 в игре 🔫"
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_text, reply_markup=kb, parse_mode="HTML")

        # Отправляем DM
        await send_result_dm(bot, user, user_id, bet, winnings, is_win, "🔫")

        await send_russian_roulette_log(bot, user_id=user_id, user=user, bet=bet, bullet_count=bullet_count, win=is_win, winnings=winnings)

        return channel_text, new_balance, winnings, result

    except Exception as e:
        logging.error(f"Unexpected error in play_russian_roulette for user_id={user_id}: {e}\n{traceback.format_exc()}")
        await bot.send_message(chat_id=CHANNEL_ID, text="❌ Произошла ошибка. Попробуйте позже.", parse_mode="HTML")
        return "Ошибка", user_balance, 0, "none"

