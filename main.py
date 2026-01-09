import os
import asyncio
from typing import List, Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from db import init_db, create_order, list_orders, get_order, set_order_status


# ----------------------------
# Config
# ----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables")


def parse_admin_ids(raw: str) -> List[int]:
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


async def notify_admins(
    text: str,
    bot: Bot,
    photo_file_id: Optional[str] = None,
    ref_file_id: Optional[str] = None
) -> None:
    if not ADMIN_IDS:
        return

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
            if photo_file_id:
                await bot.send_photo(admin_id, photo_file_id, caption="📷 Фото клиента")
            if ref_file_id:
                await bot.send_photo(admin_id, ref_file_id, caption="🧷 Референс")
        except Exception:
            pass


# ----------------------------
# Handlers: Start / Info
# ----------------------------
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Это RawWow.\n\nВыберите действие:",
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

    orders = await list_orders(limit=10)
    if not orders:
        return await message.answer("Пока нет заказов.")

    # компактный список
    lines = ["🧾 Последние 10 заказов:\n"]
    for o in orders:
        who = o.get("full_name") or (o.get("username") and f"@{o.get('username')}") or str(o.get("user_id"))
        lines.append(f"#{o['id']} • {o['created_at']} • {o['service']} • {o['status']} • {who}")

    lines.append("\nЧтобы открыть заказ: отправьте команду:\n/order 123")
    await message.answer("\n".join(lines))


@dp.message(Command("order"))
async def admin_open_order(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ Доступ запрещён")

    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.answer("Формат: /order 123")

    order_id = int(parts[1])
    o = await get_order(order_id)
    if not o:
        return await message.answer("Не нашёл такой заказ.")

    who = f"{o.get('full_name') or '—'} (@{o.get('username') or '—'})"
    text = (
        f"🧾 Заказ #{o['id']}\n"
        f"🕒 {o['created_at']}\n"
        f"👤 {who}\n"
        f"🆔 user_id: {o['user_id']}\n"
        f"🛠 Услуга: {o['service']}\n"
        f"💬 Комментарий: {o.get('comment') or '—'}\n"
        f"📌 Статус: {o['status']}\n\n"
        "Команды:\n"
        f"/setstatus {o['id']} in_work\n"
        f"/setstatus {o['id']} done\n"
    )
    await message.answer(text)

    # показать вложения
    try:
        await bot.send_photo(message.chat.id, o["photo_file_id"], caption="📷 Фото клиента")
    except Exception:
        await message.answer("⚠️ Не смог отправить фото (возможно документ/не фото). file_id сохранён.")
        await message.answer(f"photo_file_id: {o['photo_file_id']}")

    if o.get("ref_file_id"):
        try:
            await bot.send_photo(message.chat.id, o["ref_file_id"], caption="🧷 Референс")
        except Exception:
            await message.answer("⚠️ Не смог отправить референс как фото.")
            await message.answer(f"ref_file_id: {o['ref_file_id']}")


@dp.message(Command("setstatus"))
async def admin_set_status(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ Доступ запрещён")

    parts = message.text.split()
    if len(parts) != 3 or not parts[1].isdigit():
        return await message.answer("Формат: /setstatus 123 new|in_work|done")

    order_id = int(parts[1])
    status = parts[2].strip()
    if status not in {"new", "in_work", "done"}:
        return await message.answer("Статусы: new, in_work, done")

    await set_order_status(order_id, status)
    await message.answer(f"✅ Заказ #{order_id}: статус обновлён на {status}")


# ----------------------------
# Order flow
# ----------------------------
@dp.message(F.text == "🛒 Новый заказ")
async def new_order(message: Message, state: FSMContext):
    await state.set_state(OrderState.choosing_service)
    await message.answer("Выберите услугу:", reply_markup=services_kb)


@dp.message(OrderState.choosing_service, F.text.in_({
    "🎨 Color Only", "🧼 Clean Portrait", "🧩 Pro Retouch", "💄 Beauty Retouch", "📦 Product Retouch"
}))
async def choose_service(message: Message, state: FSMContext):
    await state.update_data(service=message.text)
    await state.set_state(OrderState.waiting_photo)
    await message.answer(
        "Отправьте фото.\n\nМожно как Фото или как Документ (лучше качество).",
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
    file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=file_id, photo_type="photo", photo_name=None)
    await state.set_state(OrderState.waiting_comment)
    await message.answer("Напишите комментарий/пожелания к ретуши:", reply_markup=skip_kb)


@dp.message(OrderState.waiting_photo, F.document)
async def got_photo_as_document(message: Message, state: FSMContext):
    file_id = message.document.file_id
    await state.update_data(
        photo_file_id=file_id,
        photo_type="document",
        photo_name=message.document.file_name
    )
    await state.set_state(OrderState.waiting_comment)
    await message.answer("Напишите комментарий/пожелания к ретуши:", reply_markup=skip_kb)


@dp.message(OrderState.waiting_photo)
async def photo_expected(message: Message):
    await message.answer("Пожалуйста, отправьте фото (как фото или документ).")


@dp.message(OrderState.waiting_comment, F.text == "⬅️ Назад")
async def back_from_comment(message: Message, state: FSMContext):
    await state.set_state(OrderState.waiting_photo)
    await message.answer(
        "Ок, вернулись. Отправьте фото снова:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Назад")]],
            resize_keyboard=True
        )
    )


@dp.message(OrderState.waiting_comment, F.text == "⏭ Пропустить")
async def skip_comment(message: Message, state: FSMContext):
    await state.update_data(comment="")
    await state.set_state(OrderState.waiting_reference)
    await message.answer("Если есть референс — отправьте. Если нет — «Пропустить».", reply_markup=skip_kb)


@dp.message(OrderState.waiting_comment, F.text)
async def got_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await state.set_state(OrderState.waiting_reference)
    await message.answer("Если есть референс — отправьте. Если нет — «Пропустить».", reply_markup=skip_kb)


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
    photo_type = data.get("photo_type")
    photo_name = data.get("photo_name")

    order_id = await create_order(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        service=service,
        comment=comment,
        photo_file_id=photo_file_id,
        photo_type=photo_type,
        photo_name=photo_name,
        ref_file_id=None,
        ref_type=None
    )

    text = (
        f"🆕 Новый заказ #{order_id}\n"
        f"👤 {user.full_name} (@{user.username or '—'})\n"
        f"🛠 {service}\n"
        f"💬 {comment or '—'}\n"
        f"📎 Референс: —"
    )

    await notify_admins(text, bot, photo_file_id=photo_file_id, ref_file_id=None)
    await message.answer("✅ Заказ принят! Спасибо.", reply_markup=user_menu)


@dp.message(OrderState.waiting_reference, F.photo)
async def finish_with_ref_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user = message.from_user

    ref_file_id = message.photo[-1].file_id
    service = data.get("service", "—")
    comment = data.get("comment", "")
    photo_file_id = data.get("photo_file_id")
    photo_type = data.get("photo_type")
    photo_name = data.get("photo_name")

    order_id = await create_order(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        service=service,
        comment=comment,
        photo_file_id=photo_file_id,
        photo_type=photo_type,
        photo_name=photo_name,
        ref_file_id=ref_file_id,
        ref_type="photo"
    )

    await state.clear()

    text = (
        f"🆕 Новый заказ #{order_id}\n"
        f"👤 {user.full_name} (@{user.username or '—'})\n"
        f"🛠 {service}\n"
        f"💬 {comment or '—'}\n"
        f"📎 Референс: ✅"
    )

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
    photo_type = data.get("photo_type")
    photo_name = data.get("photo_name")

    order_id = await create_order(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        service=service,
        comment=comment,
        photo_file_id=photo_file_id,
        photo_type=photo_type,
        photo_name=photo_name,
        ref_file_id=ref_file_id,
        ref_type="document"
    )

    await state.clear()

    text = (
        f"🆕 Новый заказ #{order_id}\n"
        f"👤 {user.full_name} (@{user.username or '—'})\n"
        f"🛠 {service}\n"
        f"💬 {comment or '—'}\n"
        f"📎 Референс: ✅ (документ)"
    )

    await notify_admins(text, bot, photo_file_id=photo_file_id, ref_file_id=None)
    await message.answer("✅ Заказ принят! Спасибо.", reply_markup=user_menu)


# ----------------------------
# Entrypoint
# ----------------------------
async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
