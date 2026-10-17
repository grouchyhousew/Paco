from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def hearts_choice_keyboard(bet: float = None) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="❤️ Красное", callback_data=f"hearts_red_{bet}" if bet else "hearts_red"),
            InlineKeyboardButton(text="💙 Синее", callback_data=f"hearts_blue_{bet}" if bet else "hearts_blue")
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id='5877629862306385808')
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def dice_choice_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 Меньше", callback_data="dice_less"),
            InlineKeyboardButton(text="🎲 Больше", callback_data="dice_more"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="games", icon_custom_emoji_id='5877629862306385808'),
        ]
    ])
    return keyboard

def darts_choice_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Красное", callback_data=f"bet_red"),
            InlineKeyboardButton(text="⚪️ Белое", callback_data=f"bet_white")
        ],
        [
            InlineKeyboardButton(text="🍎 Центер", callback_data=f"bet_center"),
            InlineKeyboardButton(text="❌ Мимо", callback_data=f"bet_miss")
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id='5877629862306385808'),
        ]
    ])
    return keyboard

def football_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Гол", callback_data="bet_goal"),
         InlineKeyboardButton(text="💨 Мимо", callback_data="bet_football_miss")],
        [InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id='5877629862306385808')]
    ])

def bowling_choice_keyboard(bet: float) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏆 Победа", callback_data=f"bet_win_{bet}"),
            InlineKeyboardButton(text="🚫 Поражение", callback_data=f"bet_lose_{bet}")
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id='5877629862306385808')
        ]
    ])

def basketball_choice_keyboard(bet: float) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏀 Гол", callback_data=f"basketball_goal_{bet}"),
            InlineKeyboardButton(text="💨 Мимо", callback_data=f"basketball_miss_{bet}"),
            InlineKeyboardButton(text="❌ Застрянет", callback_data=f"basketball_stuck_{bet}")
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id='5877629862306385808')
        ]
    ])

def even_odd_choice_keyboard(bet: float) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔢 Чётное", callback_data=f"even_odd_even_{bet:.2f}"),
            InlineKeyboardButton(text="🔣 Нечётное", callback_data=f"even_odd_odd_{bet:.2f}")
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="main_menu", icon_custom_emoji_id='5877629862306385808')
        ]
    ])

def guess_number_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1", callback_data="guess_1"),
            InlineKeyboardButton(text="2", callback_data="guess_2"),
            InlineKeyboardButton(text="3", callback_data="guess_3")
        ],
        [
            InlineKeyboardButton(text="4", callback_data="guess_4"),
            InlineKeyboardButton(text="5", callback_data="guess_5"),
            InlineKeyboardButton(text="6", callback_data="guess_6")
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="main_menu", icon_custom_emoji_id='5877629862306385808')
        ]
    ])


def mines() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Продолжить", callback_data="play_mines")],
        [InlineKeyboardButton(text="Назад", callback_data="main_menu", icon_custom_emoji_id='5877629862306385808'),
         InlineKeyboardButton(text="💣 Бомбы", callback_data="bomb_select")]
    ])

async def get_tower_keyboard_with_state(lang: str, state, selected: int = None) -> InlineKeyboardMarkup:
    # ПРИМЕЧАНИЕ: эта версия не используется — games/games.py объявляет свою локальную
    # async def get_tower_keyboard_with_state(selected=None), которая перекрывает эту при wildcard-импорте.
    # Оставлено синхронизированной на случай, если импорт когда-нибудь понадобится напрямую.
    def label(n: int) -> str:
        return f"✅ 🗼 {n}💣" if n == selected else f"🗼 {n}💣"

    keyboard = [
        [
            InlineKeyboardButton(text=label(1), callback_data="tower_select_1"),
            InlineKeyboardButton(text=label(2), callback_data="tower_select_2"),
        ],
        [
            InlineKeyboardButton(text=label(3), callback_data="tower_select_3"),
            InlineKeyboardButton(text=label(4), callback_data="tower_select_4"),
        ],
    ]
    if selected is not None:
        keyboard.append([
            InlineKeyboardButton(text="Назад", callback_data="tower", icon_custom_emoji_id='5877629862306385808'),
            InlineKeyboardButton(text="▶️ Играть", callback_data="tower_play"),
        ])
    else:
        keyboard.append([InlineKeyboardButton(text="Назад", callback_data="tower", icon_custom_emoji_id='5877629862306385808')])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
