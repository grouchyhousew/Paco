from typing import List

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from config.config import *
from config import *


def mini_app_keyboard(lang="russian"):
    if not WEBAPP_URL:
        return None
    label = "Открыть SavanaWin" if lang == "russian" else "Open SavanaWin"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"🌴 {label}", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])


def language_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Русский", callback_data="language_russian", icon_custom_emoji_id = '5327915864219988749'),
            InlineKeyboardButton(text="English", callback_data="language_english", icon_custom_emoji_id = '5328239678984302432')
        ]
    ])

def start_bet_keyboard(user_id: int, lang="russian"):
    if lang == "english":
        buttons = [
            [InlineKeyboardButton(text="🌴 Open SavanaWin", web_app=WebAppInfo(url=WEBAPP_URL))] if WEBAPP_URL else [InlineKeyboardButton(text="Games", callback_data="games", icon_custom_emoji_id = '5452033976623467883')],
            [
                InlineKeyboardButton(text="Deposit", callback_data="deposit", icon_custom_emoji_id = '5406612507034948020'),
                InlineKeyboardButton(text="Withdraw", callback_data="withdraw", icon_custom_emoji_id = '5449624985301717991')
            ],
            [
                InlineKeyboardButton(text="Invite a Friend", callback_data="invite_friend", icon_custom_emoji_id = '5452145448204668230'),
                InlineKeyboardButton(text="TOP-10", callback_data="top_10_all_time", icon_custom_emoji_id = '5451916157080604249')
            ],
            [
                InlineKeyboardButton(text="Support", url=HELP_USERNAME, icon_custom_emoji_id = '5296410453742753454'),
                InlineKeyboardButton(text="Adapter", url=CHAT_CHANNEL, icon_custom_emoji_id = '5452008481697599177')
            ],
            [
                InlineKeyboardButton(text="📜 Bet History", callback_data="bet_history")
            ],
            [
                InlineKeyboardButton(text="Add Bot to Group", url=INVITE_BOT)
            ]
        ]

        if user_id in ADMIN_LIST:
            buttons.append([InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel")])

    else:
        buttons = [
            [InlineKeyboardButton(text="🌴 Открыть SavanaWin", web_app=WebAppInfo(url=WEBAPP_URL))] if WEBAPP_URL else [InlineKeyboardButton(text="Игры", callback_data="games", icon_custom_emoji_id = '5452033976623467883')],
            [
                InlineKeyboardButton(text="Пополнить", callback_data="deposit", icon_custom_emoji_id = '5406612507034948020'),
                InlineKeyboardButton(text="Вывести", callback_data="withdraw", icon_custom_emoji_id = '5449624985301717991')
            ],
            [
                InlineKeyboardButton(text="Пригласить друга", callback_data="invite_friend", icon_custom_emoji_id = '5452145448204668230'),
                InlineKeyboardButton(text="ТОП-10", callback_data="top_10_all_time", icon_custom_emoji_id = '5451916157080604249')
            ],
            [
                InlineKeyboardButton(text="Поддержка", url=HELP_USERNAME, icon_custom_emoji_id = '5296410453742753454'),
                InlineKeyboardButton(text="Игровой канал", url=CHAT_CHANNEL, icon_custom_emoji_id = '5452008481697599177')
            ],
            [
                InlineKeyboardButton(text="📜 История ставок", callback_data="bet_history")
            ],
            [
                InlineKeyboardButton(text="Добавить бота", url=INVITE_BOT)
            ]
        ]

        if user_id in ADMIN_LIST:
            buttons.append([InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin_panel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def deposit_payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🦋 CryptoBot — (2.9%)", callback_data="crypto_bot")],
        [InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id = '5877629862306385808')]
    ])

def withdraw_payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🦋 CryptoBot", callback_data="crypto_bot_withdraw")],
    [InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id = '5877629862306385808')]
])

def slot_payments_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="slots_amount_0.5"),
            InlineKeyboardButton(text="$1", callback_data="slots_amount_1"),
            InlineKeyboardButton(text="$2", callback_data="slots_amount_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="slots_amount_5"),
            InlineKeyboardButton(text="$25", callback_data="slots_amount_25"),
            InlineKeyboardButton(text="$50", callback_data="slots_amount_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="slots_amount_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id = '5877629862306385808'),
        ]
    ])

def darts_payments_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="darts_amount_0.5"),
            InlineKeyboardButton(text="$1", callback_data="darts_amount_1"),
            InlineKeyboardButton(text="$2", callback_data="darts_amount_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="darts_amount_5"),
            InlineKeyboardButton(text="$25", callback_data="darts_amount_25"),
            InlineKeyboardButton(text="$50", callback_data="darts_amount_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="darts_amount_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id = '5877629862306385808'),
        ]
    ])

def football_payments_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="football_amount_0.5"),
            InlineKeyboardButton(text="$1", callback_data="football_amount_1"),
            InlineKeyboardButton(text="$2", callback_data="football_amount_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="football_amount_5"),
            InlineKeyboardButton(text="$25", callback_data="football_amount_25"),
            InlineKeyboardButton(text="$50", callback_data="football_amount_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="football_amount_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id = '5877629862306385808'),
        ]
    ])

def bowling_payments_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="bowling_amount_0.5"),
            InlineKeyboardButton(text="$1", callback_data="bowling_amount_1"),
            InlineKeyboardButton(text="$2", callback_data="bowling_amount_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="bowling_amount_5"),
            InlineKeyboardButton(text="$25", callback_data="bowling_amount_25"),
            InlineKeyboardButton(text="$50", callback_data="bowling_amount_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="bowling_amount_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id = '5877629862306385808'),
        ]
    ])
def basketball_payments_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="basketball_amount_0.5"),
            InlineKeyboardButton(text="$1", callback_data="basketball_amount_1"),
            InlineKeyboardButton(text="$2", callback_data="basketball_amount_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="basketball_amount_5"),
            InlineKeyboardButton(text="$25", callback_data="basketball_amount_25"),
            InlineKeyboardButton(text="$50", callback_data="basketball_amount_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="basketball_amount_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id = '5877629862306385808'),
        ]
    ])

def hearts_payments_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="$1", callback_data="hearts_amount_1"),
            InlineKeyboardButton(text="$5", callback_data="hearts_amount_5"),
            InlineKeyboardButton(text="$10", callback_data="hearts_amount_10")
        ],
        [
            InlineKeyboardButton(text="$20", callback_data="hearts_amount_20"),
            InlineKeyboardButton(text="$50", callback_data="hearts_amount_50"),
            InlineKeyboardButton(text="$100", callback_data="hearts_amount_100")
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id = '5877629862306385808')
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def hearts_choice_keyboard(bet: float) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Красное", callback_data=f"hearts_red_{bet}"),
            InlineKeyboardButton(text="💙 Синее", callback_data=f"hearts_blue_{bet}")
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id = '5877629862306385808')
        ]
    ])

def even_odd_payments_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="even_odd_amount_0.5"),
            InlineKeyboardButton(text="$1", callback_data="even_odd_amount_1"),
            InlineKeyboardButton(text="$2", callback_data="even_odd_amount_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="even_odd_amount_5"),
            InlineKeyboardButton(text="$25", callback_data="even_odd_amount_25"),
            InlineKeyboardButton(text="$50", callback_data="even_odd_amount_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="even_odd_amount_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="main_menu", icon_custom_emoji_id = '5877629862306385808'),
        ]
    ])

def guess_number_payments_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="guess_number_amount_0.5"),
            InlineKeyboardButton(text="$1", callback_data="guess_number_amount_1"),
            InlineKeyboardButton(text="$2", callback_data="guess_number_amount_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="guess_number_amount_5"),
            InlineKeyboardButton(text="$25", callback_data="guess_number_amount_25"),
            InlineKeyboardButton(text="$50", callback_data="guess_number_amount_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="guess_number_amount_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="main_menu", icon_custom_emoji_id = '5877629862306385808'),
        ]
    ])

def more_less_payments_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="more_less_amount_0.5"),
            InlineKeyboardButton(text="$1", callback_data="more_less_amount_1"),
            InlineKeyboardButton(text="$2", callback_data="more_less_amount_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="more_less_amount_5"),
            InlineKeyboardButton(text="$25", callback_data="more_less_amount_25"),
            InlineKeyboardButton(text="$50", callback_data="more_less_amount_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="more_less_amount_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="main_menu", icon_custom_emoji_id = '5877629862306385808'),
        ]
    ])


def double_dice_payments_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="double_dice_amount_0.5"),
            InlineKeyboardButton(text="$1", callback_data="double_dice_amount_1"),
            InlineKeyboardButton(text="$2", callback_data="double_dice_amount_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="double_dice_amount_5"),
            InlineKeyboardButton(text="$25", callback_data="double_dice_amount_25"),
            InlineKeyboardButton(text="$50", callback_data="double_dice_amount_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="double_dice_amount_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="main_menu", icon_custom_emoji_id = '5877629862306385808'),
        ]
    ])


def rps_payments_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="rps_amount_0.5"),
            InlineKeyboardButton(text="$1", callback_data="rps_amount_1"),
            InlineKeyboardButton(text="$2", callback_data="rps_amount_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="rps_amount_5"),
            InlineKeyboardButton(text="$25", callback_data="rps_amount_25"),
            InlineKeyboardButton(text="$50", callback_data="rps_amount_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="rps_amount_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="main_menu", icon_custom_emoji_id = '5877629862306385808'),
        ]
    ])

def russun_roulet_payments_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="russun_roolet_amount_0.5"),
            InlineKeyboardButton(text="$1", callback_data="russun_roulet_amount_1"),
            InlineKeyboardButton(text="$2", callback_data="russun_roulet_amount_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="russun_roulet_amount_5"),
            InlineKeyboardButton(text="$25", callback_data="russun_roulet_amount_25"),
            InlineKeyboardButton(text="$50", callback_data="russun_roulet_amount_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="russun_roulet_amount_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="main_menu", icon_custom_emoji_id = '5877629862306385808'),
        ]
    ])

def mines_payments_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="mines_amount_0.5"),
            InlineKeyboardButton(text="$1", callback_data="mines_amount_1"),
            InlineKeyboardButton(text="$2", callback_data="mines_amount_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="mines_amount_5"),
            InlineKeyboardButton(text="$25", callback_data="mines_amount_25"),
            InlineKeyboardButton(text="$50", callback_data="mines_amount_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="mines_amount_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="main_menu", icon_custom_emoji_id = '5877629862306385808'),
        ]
    ])

def special_tower_payments_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="special_tower_amount_0.5"),
            InlineKeyboardButton(text="$1", callback_data="special_tower_amount_1"),
            InlineKeyboardButton(text="$2", callback_data="special_tower_amount_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="special_tower_amount_5"),
            InlineKeyboardButton(text="$25", callback_data="special_tower_amount_25"),
            InlineKeyboardButton(text="$50", callback_data="special_tower_amount_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="special_tower_amount_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="main_menu", icon_custom_emoji_id = '5877629862306385808'),
        ]
    ])

def games():
    return InlineKeyboardMarkup(inline_keyboard=[

        [InlineKeyboardButton(text="Дартс", callback_data="emoji_darts", icon_custom_emoji_id = '5451826078731503931'),
         InlineKeyboardButton(text="Футбол", callback_data="emoji_football", icon_custom_emoji_id = '5451811677706167149')],

        [InlineKeyboardButton(text="Боулинг", callback_data="emoji_bowling", icon_custom_emoji_id = '5451684138652306936'),
         InlineKeyboardButton(text="❣️ Сердца", callback_data="emoji_hearts"),
         InlineKeyboardButton(text="Баскет", callback_data="emoji_basketball", icon_custom_emoji_id = '5296290950572707978')],

        [InlineKeyboardButton(text="Больше/Меньше", callback_data="more_less", icon_custom_emoji_id = '5451788978804001506'),
         InlineKeyboardButton(text="📗 Чётное/Нечётное", callback_data="even_odd")],

        [InlineKeyboardButton(text="Угадай число", callback_data="guess_number", icon_custom_emoji_id = '5451789399710798534'),
         InlineKeyboardButton(text="Двойной кубик", callback_data="double_dice", icon_custom_emoji_id = '5449654410122663850')],


        [InlineKeyboardButton(text="Мины", callback_data="special_mines", icon_custom_emoji_id = '5452018153963948977'),
         InlineKeyboardButton(text="Башня", callback_data="special_tower", icon_custom_emoji_id = '5449397725697187601'),
         InlineKeyboardButton(text="✂️ КНБ", callback_data="special_rps")],

        [InlineKeyboardButton(text="Русская Рулетка", callback_data="russian_roulette", icon_custom_emoji_id = '5449706211723221696')],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back")]
    ])

def payments_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="amounts_0.5"),
            InlineKeyboardButton(text="$1", callback_data="amounts_1"),
            InlineKeyboardButton(text="$2", callback_data="amounts_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="amounts_5"),
            InlineKeyboardButton(text="$25", callback_data="amounts_25"),
            InlineKeyboardButton(text="$50", callback_data="amounts_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="amounts_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id='5877629862306385808'),
        ]
    ])

def withdraw_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$0.5", callback_data="withdraw_0.5"),
            InlineKeyboardButton(text="$1", callback_data="withdraw_1"),
            InlineKeyboardButton(text="$2", callback_data="withdraw_2"),
        ],
        [
            InlineKeyboardButton(text="$5", callback_data="withdraw_5"),
            InlineKeyboardButton(text="$25", callback_data="withdraw_25"),
            InlineKeyboardButton(text="$50", callback_data="withdraw_50"),
        ],
        [
            InlineKeyboardButton(text="$100", callback_data="withdraw_100"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="withdraw", icon_custom_emoji_id='5877629862306385808'),
        ]
    ])

def back():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Назад", callback_data="back", icon_custom_emoji_id='5877629862306385808'),
        ],
    ])

def top_10_keyboard(lang: str, selected_category: str, selected_period: str) -> InlineKeyboardMarkup:
    categories = {
        "games": ("🎮 Games" if lang == "english" else "🎮 Игры"),
        "turnover": ("💰 Turnover" if lang == "english" else "💰 Оборот"),
        "winnings": ("🏆 Winnings" if lang == "english" else "🏆 Выигрыши"),
        "coefficient": ("📈 Coefficient" if lang == "english" else "📈 Коэффициент")
    }
    periods = {
        "all_time": ("All Time" if lang == "english" else "Всё время"),
        "today": ("Today" if lang == "english" else "Сегодня"),
        "week": ("Week" if lang == "english" else "Неделя"),
        "month": ("Month" if lang == "english" else "Месяц")
    }

    category_buttons = [
        InlineKeyboardButton(
            text=f"✅ {name}" if key == selected_category else name,
            callback_data=f"top_10_{key}_{selected_period}"
        ) for key, name in categories.items()
    ]

    period_buttons = [
        InlineKeyboardButton(
            text=f"✅ {name}" if key == selected_period else name,
            callback_data=f"top_10_{selected_category}_{key}"
        ) for key, name in periods.items()
    ]

    back_button = InlineKeyboardButton(
        text="🔙 Back" if lang == "english" else "🔙 Назад",
        callback_data="back_to_menu"
    )

    keyboard = [
        category_buttons,
        period_buttons[:2],
        period_buttons[2:],
        [back_button]
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def mines_settings_keyboard(selected_bombs: int) -> InlineKeyboardMarkup:
    keyboard = []
    row = []
    for i in range(3, 18):
        text = f"{i}{' 💣' if i == selected_bombs else ''}".strip()
        row.append(InlineKeyboardButton(text=text, callback_data=f"mines_bombs_{i}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="Назад", callback_data="mines_amount_stored", icon_custom_emoji_id='5877629862306385808')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def generate_mine_grid(opened=None, mine_positions=None, lost=False, current_coef=None,
                        fair_hash=None, fair_reveal_id=None):
    opened = opened or []
    mine_positions = mine_positions or []
    keyboard_buttons = []

    for i in range(TOTAL_CELLS):
        if lost:
            # Игра окончена — раскрываем ВСЁ поле целиком, а не только то, что игрок успел открыть:
            # мины — 💥 (если игрок наступил именно сюда) или 💣 (просто мина, до которой не дошли),
            # безопасные клетки — ✅ (успел открыть) или 💎 (безопасная, но так и не открытая).
            if i in mine_positions:
                label = "💥" if i in opened else "💣"
            else:
                label = "✅" if i in opened else "💎"
            callback_data = "ignore"
        elif i in opened:
            label = "✅"
            callback_data = "ignore"
        else:
            label = " "
            callback_data = f"mine_cell_{i}"

        keyboard_buttons.append(
            InlineKeyboardButton(text=label, callback_data=callback_data)
        )

    inline_keyboard = [keyboard_buttons[i:i + 5] for i in range(0, TOTAL_CELLS, 5)]

    if current_coef is not None and not lost:
        action_row = [InlineKeyboardButton(text=f"Забрать x{current_coef:.2f}", callback_data="mine_cashout")]
        if fair_hash:
            action_row.append(InlineKeyboardButton(text="🔒 Честность", callback_data="mines_fair_pending"))
        inline_keyboard.append(action_row)

    if not lost:
        cancel_row = [InlineKeyboardButton(text="⬅️ Отмена", callback_data="mines_cancel")]
        if fair_hash and current_coef is None:
            cancel_row.append(InlineKeyboardButton(text="🔒 Честность", callback_data="mines_fair_pending"))
        inline_keyboard.append(cancel_row)
    elif fair_reveal_id is not None:
        inline_keyboard.append([InlineKeyboardButton(text="🔒 Честность", callback_data=f"mines_fair_reveal_{fair_reveal_id}")])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def generate_mine_log_grid(mines_field: list, opened: list) -> InlineKeyboardMarkup:
    """
    Статичная (некликабельная) сетка для рекап-сообщения в чат после окончания игры «Мины».
    Все callback_data = "ignore", чтобы никто в общем чате не мог случайно задеть активную игру.
    """
    keyboard_buttons = []
    for i in range(TOTAL_CELLS):
        if mines_field[i]:
            label = "💥" if i in opened else "💣"
        elif i in opened:
            label = "💎"
        else:
            label = "▫️"
        keyboard_buttons.append(InlineKeyboardButton(text=label, callback_data="ignore"))

    inline_keyboard = [keyboard_buttons[i:i + 5] for i in range(0, TOTAL_CELLS, 5)]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


TOWER_CELLS_PER_LAYER = 5  # 5 клеток в слое — все уровни (1-4 мины) остаются проходимыми


def generate_tower_grid(opened: list, bomb_count: int, current_coef: float, mine_positions: list,
                         current_layer: int, last_selected: int = None,
                         fair_hash: str = None, fair_reveal_id: int = None) -> InlineKeyboardMarkup:
    """
    Рисует башню.
    mine_positions — список списков: mine_positions[layer] = позиции мин (0..3) на этом слое.
    Каждый слой при отрисовке использует СВОИ собственные (уже зафиксированные) позиции мин,
    а не позиции текущего/следующего слоя — иначе мины "прыгают" по старым слоям.
    Кликабелен только текущий (current_layer) слой, остальные — задизейблены.
    """
    keyboard = []
    coefs = TOWER_COEFFICIENTS[bomb_count]
    max_layers = len(coefs)

    # Отображаем сверху вниз в порядке прохождения: слой 1 — сверху, далее вниз
    for layer in range(max_layers):
        layer_mines = mine_positions[layer] if layer < len(mine_positions) else []

        row_buttons = [InlineKeyboardButton(text=f"x{coefs[layer]:.2f}", callback_data="ignore")]

        for col in range(TOWER_CELLS_PER_LAYER):
            cell_idx = layer * TOWER_CELLS_PER_LAYER + col
            if cell_idx in opened:
                # Слой уже пройден/открыт — показываем то, что реально было на этой клетке
                if col in layer_mines:
                    label = "💣"
                elif cell_idx == last_selected:
                    label = "✅"
                else:
                    label = "📦"
                callback_data = "ignore"
            elif layer == current_layer:
                label = "☁️"
                callback_data = f"tower_cell_{cell_idx}"
            else:
                # Слои выше текущего ещё не доступны для клика
                label = "▫️"
                callback_data = "ignore"
            row_buttons.append(InlineKeyboardButton(text=label, callback_data=callback_data))

        keyboard.append(row_buttons)

    if current_coef and current_coef > 0:
        action_row = [InlineKeyboardButton(text=f"Забрать x{current_coef:.2f}", callback_data="tower_cashout")]
        if fair_hash:
            action_row.append(InlineKeyboardButton(text="🔒 Честность", callback_data="tower_fair_pending"))
        keyboard.append(action_row)
        keyboard.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data="tower")])
    else:
        cancel_row = [InlineKeyboardButton(text="⬅️ Отмена", callback_data="tower")]
        if fair_hash:
            cancel_row.append(InlineKeyboardButton(text="🔒 Честность", callback_data="tower_fair_pending"))
        keyboard.append(cancel_row)

    if fair_reveal_id is not None:
        keyboard.append([InlineKeyboardButton(text="🔒 Честность", callback_data=f"tower_fair_reveal_{fair_reveal_id}")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def generate_tower_log_grid(mine_positions: list, opened: list, bomb_count: int) -> InlineKeyboardMarkup:
    """
    Статичная (некликабельная) сетка для рекап-сообщения в чат после окончания игры «Башня».
    Показывает только реально пройденные/раскрытые слои; остальные — заглушки (◻️).
    Все callback_data = "ignore", чтобы никто в общем чате не мог задеть активную игру.
    """
    keyboard = []
    coefs = TOWER_COEFFICIENTS[bomb_count]
    max_layers = len(coefs)

    for layer in range(max_layers):
        layer_mines = mine_positions[layer] if layer < len(mine_positions) else []
        row_buttons = [InlineKeyboardButton(text=f"x{coefs[layer]:.2f}", callback_data="ignore")]
        for col in range(TOWER_CELLS_PER_LAYER):
            cell_idx = layer * TOWER_CELLS_PER_LAYER + col
            if cell_idx in opened:
                label = "💣" if col in layer_mines else "💎"
            else:
                label = "▫️"
            row_buttons.append(InlineKeyboardButton(text=label, callback_data="ignore"))
        keyboard.append(row_buttons)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def generate_tower_finish_grid(mine_positions: list, opened: list, bomb_count: int,
                                fair_reveal_id: int = None) -> InlineKeyboardMarkup:
    """
    Полностью раскрытая сетка Башни после ОКОНЧАНИЯ раунда (проигрыш/победа/кэшаут) —
    показывает мины на ВСЕХ слоях (не только на пройденных), ровно как в Минах, чтобы
    игра оставалась видна целиком в том же сообщении, а не пропадала за текстом.
    Плюс кнопки «Играть снова» и «Честность» внизу.
    """
    keyboard = []
    coefs = TOWER_COEFFICIENTS[bomb_count]
    max_layers = len(coefs)

    for layer in range(max_layers):
        layer_mines = mine_positions[layer] if layer < len(mine_positions) else []
        row_buttons = [InlineKeyboardButton(text=f"x{coefs[layer]:.2f}", callback_data="ignore")]
        for col in range(TOWER_CELLS_PER_LAYER):
            cell_idx = layer * TOWER_CELLS_PER_LAYER + col
            if col in layer_mines:
                label = "💥" if cell_idx in opened else "💣"
            else:
                label = "✅" if cell_idx in opened else "💎"
            row_buttons.append(InlineKeyboardButton(text=label, callback_data="ignore"))
        keyboard.append(row_buttons)

    keyboard.append([InlineKeyboardButton(text="🔁 Играть снова", callback_data="special_tower")])
    if fair_reveal_id is not None:
        keyboard.append([InlineKeyboardButton(text="🔒 Честность", callback_data=f"tower_fair_reveal_{fair_reveal_id}")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
