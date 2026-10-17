from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def kb_admin():
    builder = InlineKeyboardBuilder()

    buttons = [
        [
            InlineKeyboardButton(text="📢 Рассылка", callback_data="all_message_send"),
            InlineKeyboardButton(text="🏓 Измер. Пинг", callback_data="ping_check"),
        ],
        [
            InlineKeyboardButton(text="📩 Попол. Казну", callback_data="add_balance"),
            InlineKeyboardButton(text="🏛 Лимиты ставок", callback_data="edit_bet"),
        ],
        [
            InlineKeyboardButton(text="🔗 Изм. Счёт", callback_data="edit_wallet"),
            InlineKeyboardButton(text="✏️ Изм. Баннеры", callback_data="edit_banners"),
        ],
        [
            InlineKeyboardButton(text="📁 Скачать БД", callback_data="send_db"),
            InlineKeyboardButton(text="📂 Загрузить БД", callback_data="load_db"),
        ],
        [
            InlineKeyboardButton(text="Выдать баланс", callback_data="give_money_admin"),
        ],
        [
            InlineKeyboardButton(text="🎁 Раздача", callback_data="giveaway_menu"),
            InlineKeyboardButton(text="🚫 Бан/Разбан", callback_data="ban_menu"),
        ],
        [
            InlineKeyboardButton(text="Добавить админа", callback_data="add_admin"),
            InlineKeyboardButton(text="Удалить админа", callback_data="remove_admin"),
        ],
    ]

    for row in buttons:
        builder.row(*row)

    return builder.as_markup()
