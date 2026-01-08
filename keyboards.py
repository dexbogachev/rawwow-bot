from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

SERVICES = [
    ("🎨 Color Only", "color", 1),
    ("😊 Clean Portrait", "clean", 2),
    ("🔥 Pro Retouch", "pro", 4),
    ("💄 Beauty", "beauty", 7),
    ("📦 Product", "product", 3),
]

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Новый заказ", callback_data="new_order")],
        [InlineKeyboardButton(text="💳 Кредиты / Подписка", callback_data="credits")],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")],
    ])

def yes_no_ref() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, есть референс", callback_data="ref_yes")],
        [InlineKeyboardButton(text="Нет", callback_data="ref_no")],
    ])

def services_kb() -> InlineKeyboardMarkup:
    rows = []
    for title, key, credits in SERVICES:
        rows.append([InlineKeyboardButton(text=f"{title} — {credits} cr", callback_data=f"svc:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_actions(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Accept", callback_data=f"adm:accept:{order_id}"),
            InlineKeyboardButton(text="⬆️ Upgrade", callback_data=f"adm:upgrade:{order_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"adm:reject:{order_id}"),
        ]
    ])

def upgrade_options(order_id: int) -> InlineKeyboardMarkup:
    # варианты апгрейда: на product/pro/beauty
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Product (3 cr)", callback_data=f"adm:upg_to:product:{order_id}")],
        [InlineKeyboardButton(text="🔥 Pro (4 cr)", callback_data=f"adm:upg_to:pro:{order_id}")],
        [InlineKeyboardButton(text="💄 Beauty (7 cr)", callback_data=f"adm:upg_to:beauty:{order_id}")],
        [InlineKeyboardButton(text="Отмена", callback_data=f"adm:upg_cancel:{order_id}")],
    ])
