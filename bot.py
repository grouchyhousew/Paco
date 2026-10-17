import logging
import os
from aiogram import Bot, Dispatcher

try:
    from aiogram import BaseMiddleware
except ImportError:
    try:
        from aiogram.dispatcher.middlewares.base import BaseMiddleware
    except ImportError:
        from aiogram.dispatcher.middlewares import BaseMiddleware
from config.config import *
from database.database import *
from datetime import datetime
import games.games
from cryptopay.cryptopay import *
import asyncio
import threading
import uvicorn
from admin.main import router as main_router
from aiogram import Bot, Dispatcher
from games.games import *
from aiogram.fsm.state import State, StatesGroup
from typing import Any, Awaitable, Callable, Dict
from typing import Protocol


class TelegramEvent(Protocol):
    pass


class WalletStates(StatesGroup):
    waiting_for_wallet_address = State()  # состояние для ожидания кошелька


class BanCheckMiddleware(BaseMiddleware):
    """
    Глобальная проверка бана — стоит ДО всех остальных обработчиков (и мин, и башни,
    и админки), поэтому забаненный не может ничего сделать ни одной кнопкой/командой,
    а не только через /start. Админов не блокирует, даже если кто-то ошибочно забанит
    самого себя.
    """
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None and user.id not in ADMIN_LIST:
            try:
                if is_user_banned(user.id):
                    from aiogram.types import CallbackQuery, Message
                    try:
                        if isinstance(event, CallbackQuery):
                            await event.answer("🚫 Ваш аккаунт заблокирован администрацией.", show_alert=True)
                        elif isinstance(event, Message):
                            await event.answer("🚫 Ваш аккаунт заблокирован администрацией.")
                    except Exception:
                        pass
                    return
            except Exception as e:
                logging.error(f"Ошибка при проверке бана для {user.id}: {e}")
        return await handler(event, data)

os.makedirs('logs', exist_ok=True)
log_file = f"logs/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

def start_api() -> None:
    """Run the Mini App API beside the Telegram polling process."""
    uvicorn.run("webapp.api:app", host=API_HOST, port=API_PORT, log_level="info")


async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.update.outer_middleware(BanCheckMiddleware())
    dp.include_router(router)
    dp.include_router(main_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Запуск бота и Mini App API на порту %s...", API_PORT)
    threading.Thread(target=start_api, name="mini-app-api", daemon=True).start()
    asyncio.run(main())
