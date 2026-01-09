import os
import asyncio
from typing import List, Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext


# ----------------------------
# Config
# ----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables")

def parse_admin_ids(raw: str) -> List[int]:
    """
    ADMIN_IDS can be:
      "123456789"
      "123456789,987654321"
      "123456789 987654321"
    """
    if not raw:
        return []
    raw = raw.replace(" ", ",")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    ids = []
    for p in parts:
        if p.isdigit():
            ids.append(int(p))
    return ids

ADMIN_IDS = parse_admin_ids(ADMIN_IDS_RAW)


# ----------------------------
# Keyboards
# ----------------------------
user_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛒 Новый заказ")],
        [KeyboardButton(text="ℹ️ Как это работает")],
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧾 Заказы")],
        [KeyboardButton(text="👤 Пользователи"), KeyboardButton(text="💳 Кредиты")],
        [KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="⬅️ Выйти из админки")],
    ],
    resize_keyboard=True
)

services_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎨 Color Only")],
        [KeyboardButton(text="🧼 Clean Portrait")],
        [KeyboardButton(text="🧩 Pro Retouch")],
        [KeyboardButton(text="💄 Beauty Retouch")],
        [KeyboardButton(text="📦 Product Retouch")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True
)

skip_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⏭ Пропустить")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True
)


# ----------------------------
# FSM (Order flow)
# ----------------------------
class OrderState(StatesGroup):
    choosing_service = State()
    waiting_photo = State()
    waiting_comment = State()
    waiting_reference = State()


# ----------------------------
# App
# ----------------------------
dp = Dispatcher()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def notify_admins(text: str, bot: Bot, photo_file_id: Optional[str] = None,
                        ref_file_id: Optional[str] = None) -> None:
    """
    Sends order info to all admins. Photo/reference are forwarded if provided.
    """
    if not ADMIN_IDS:
        # If ADMIN_IDS isn't set, we still run, but no admin notifications.
        return

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
            if photo_file_id:
                await bot.send_photo(admin_id, photo_file_id, caption="📷 Фото клиента (file_id)")
            if ref_file_id:
                await bot.send_photo(admin_id, ref_file_id, caption="🧷 Референс (file_id)")
        except Exception:
            # do not crash on admin send errors
            pass


# ----------------------------
# Handlers: Start / Info
# ----------------------------
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Это RawWow.\n\n"
        "Выберите действие:",
        reply_markup=user_menu
    )

@dp.message(F.text == "ℹ️ Как это работает")
async def how_it_works(message: Message):
    await message.answer(
        "1) Вы выбираете услугу\n"
        "2) Отправляете фото (как фото или документ)\n"
        "3) Пишете комментарии/пожелания\n"
        "4) При желании добавляете референс\n\n"
        "После этого заказ уходит ретушёру.",
        reply_markup=user_menu
    )


# ----------------------------
# Admin panel
# ----------------------------
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if is_admin(message.from_user.id):
        await message.answer("🔐 Админ-панель", reply_markup=admin_menu)
    else:
        await message.answer("⛔ Доступ запрещён")

@dp.message(F.text == "⬅️ Выйти из админки")
async def admin_exit(message: Message):
    await message.answer("Ок, вы вышли из админки.", reply_markup=user_menu)

@dp.message(F.text == "🧾 Заказы")
async def admin_orders(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ Доступ запрещён")
    await message.answer(
        "🧾 Заказы: пока это заглушка.\n"
        "Следующим шагом подключим хранение заказов (в памяти/в файле/в базе) и просмотр списка."
    )


# ----------------------------
# Order flow
# ----------------------------
@dp.message(F.text == "🛒 Новый заказ")
async def new_order(message: Message, state: FSMContext):
    await state.set_state(OrderState.choosing_service)
    await message.answer(
        "Выберите услугу:",
        reply_markup=services_kb
    )

@dp.message(OrderState.choosing_service, F.text.in_({
    "🎨 Color Only", "🧼 Clean Portrait", "🧩 Pro Retouch", "💄 Beauty Retouch", "📦 Product Retouch"
}))
async def choose_service(message: Message, state: FSMContext):
    await state.update_data(service=message.text)
    await state.set_state(OrderState.waiting_photo)
    await message.answer(
        "Отправьте фото.\n\n"
        "Можно как **Фото** или как **Документ** (так качество будет лучше).",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True
        )
    )

@dp.message(OrderState.waiting_photo, F.text == "⬅️ Назад")
async def back_from_photo(message: Message, state: FSMContext):
    await state.set_state(OrderState.choosing_service)
    await message.answer("Выберите услугу:", reply_markup=services_kb)

@dp.message(OrderState.choosing_service, F.text == "⬅️ Назад")
async def cancel_order(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Ок, отменил. Возвращаю в меню.", reply_markup=user_menu)

@dp.message(OrderState.waiting_photo, F.photo)
async def got_photo_as_photo(message: Message, state: FSMContext):
    # Highest size is last
    file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=file_id, photo_type="photo")
    await state.set_state(OrderState.waiting_comment)
    await message.answer("Напишите комментарий/пожелания к ретуши:", reply_markup=skip_kb)

@dp.message(OrderState.waiting_photo, F.document)
async def got_photo_as_document(message: Message, state: FSMContext):
    # Document might be any file; assume it's image
    file_id = message.document.file_id
    await state.update_data(photo_file_id=file_id, photo_type="document", document_name=message.document.file_name)
    await state.set_state(OrderState.waiting_comment)
    await message.answer("Напишите комментарий/пожелания к ретуши:", reply_markup=skip_kb)

@dp.message(OrderState.waiting_photo)
async def photo_expected(message: Message):
    await message.answer("Пожалуйста, отправьте фото (как фото или документ).")

@dp.message(OrderState.waiting_comment, F.text == "⬅️ Назад")
async def back_from_comment(message: Message, state: FSMContext):
    await state.set_state(OrderState.waiting_photo)
    await message.answer("Ок, вернулись. Отправьте фото снова:", reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    ))

@dp.message(OrderState.waiting_comment, F.text == "⏭ Пропустить")
async def skip_comment(message: Message, state: FSMContext):
    await state.update_data(comment="")
    await state.set_state(OrderState.waiting_reference)
    await message.answer("Если есть референс — отправьте его. Если нет — нажмите «Пропустить».", reply_markup=skip_kb)

@dp.message(OrderState.waiting_comment, F.text)
async def got_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await state.set_state(OrderState.waiting_reference)
    await message.answer("Если есть референс — отправьте его. Если нет — нажмите «Пропустить».", reply_markup=skip_kb)

@dp.message(OrderState.waiting_reference, F.text == "⬅️ Назад")
async def back_from_reference(message: Message, state: FSMContext):
    await state.set_state(OrderState.waiting_comment)
    await message.answer("Напишите комментарий/пожелания к ретуши:", reply_markup=skip_kb)

@dp.message(OrderState.waiting_reference, F.text == "⏭ Пропустить")
async def finish_without_ref(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()

    user = message.from_user
    service = data.get("service", "—")
    comment = data.get("comment", "")
    photo_file_id = data.get("photo_file_id")

    text = (
        "🆕 Новый заказ\n"
        f"👤 Клиент: {user.full_name} (@{user.username or '—'})\n"
        f"🆔 ID: {user.id}\n"
        f"🛠 Услуга: {service}\n"
        f"💬 Комментарий: {comment or '—'}\n"
        f"📎 Референс: —\n"
    )

    await notify_admins(text, bot, photo_file_id=photo_file_id, ref_file_id=None)
    await message.answer("✅ Заказ принят! Мы скоро свяжемся/приступим к работе.", reply_markup=user_menu)

@dp.message(OrderState.waiting_reference, F.photo)
async def finish_with_ref_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user = message.from_user

    ref_file_id = message.photo[-1].file_id
    service = data.get("service", "—")
    comment = data.get("comment", "")
    photo_file_id = data.get("photo_file_id")

    text = (
        "🆕 Новый заказ\n"
        f"👤 Клиент: {user.full_name} (@{user.username or '—'})\n"
        f"🆔 ID: {user.id}\n"
        f"🛠 Услуга: {service}\n"
        f"💬 Комментарий: {comment or '—'}\n"
        f"📎 Референс: ✅\n"
    )

    await state.clear()
    await notify_admins(text, bot, photo_file_id=photo_file_id, ref_file_id=ref_file_id)
    await message.answer("✅ Заказ принят! Спасибо.", reply_markup=user_menu)

@dp.message(OrderState.waiting_reference, F.document)
async def finish_with_ref_doc(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user = message.from_user

    ref_file_id = message.document.file_id
    service = data.get("service", "—")
    comment = data.get("comment", "")
    photo_file_id = data.get("photo_file_id")

    text = (
        "🆕 Новый заказ\n"
        f"👤 Клиент: {user.full_name} (@{user.username or '—'})\n"
        f"🆔 ID: {user.id}\n"
        f"🛠 Услуга: {service}\n"
        f"💬 Комментарий: {comment or '—'}\n"
        f"📎 Референс: ✅ (документ)\n"
    )

    await state.clear()
    # For reference as document we still try send as photo; if Telegram can't show, it'll fail silently
    await notify_admins(text, bot, photo_file_id=photo_file_id, ref_file_id=ref_file_id)
    await message.answer("✅ Заказ принят! Спасибо.", reply_markup=user_menu)


# ----------------------------
# Entrypoint
# ----------------------------
async def main():
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
