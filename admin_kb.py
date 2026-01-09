from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧾 Заказы")],
        [KeyboardButton(text="👤 Пользователи"), KeyboardButton(text="💳 Кредиты")],
        [KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="⚙️ Настройки")],
    ],
    resize_keyboard=True
)
