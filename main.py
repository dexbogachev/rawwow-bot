import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from config import load_config
from states import OrderFlow
from keyboards import main_menu, yes_no_ref, services_kb, SERVICES, admin_actions, upgrade_options
from db import InMemoryDB, Order

cfg = load_config()
db = InMemoryDB()

SERVICE_MAP = {k: (title, credits) for (title, k, credits) in SERVICES}

bot = Bot(token=cfg.bot_token)
dp = Dispatcher()

def is_admin(user_id: int) -> bool:
    return user_id in cfg.admin_ids

@dp.message(CommandStart())
async def start(msg: Message):
    await msg.answer(
        "RawWowBot 👋\n\n"
        "Здесь вы можете оформить заказ на ретушь:\n"
        "1) Загрузить фото (как фото или документ)\n"
        "2) Добавить референс (по желанию)\n"
        "3) Написать пожелания\n"
        "4) Выбрать услугу\n\n"
        "Нажмите «Новый заказ».",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Главное меню:", reply_markup=main_menu())
    await cb.answer()

@dp.callback_query(F.data == "new_order")
async def new_order(cb: CallbackQuery, state: FSMContext):
    await state.set_state(OrderFlow.waiting_photo)
    await cb.message.edit_text(
        "📸 Отправьте фото.\n\n"
        "Можно:\n"
        "• как Фото (JPEG)\n"
        "• как Файл/Документ (RAW/TIFF/PNG/JPG)\n\n"
        "Если несколько — отправляйте по одному (в MVP)."
    )
    await cb.answer()

@dp.message(OrderFlow.waiting_photo, F.photo)
async def got_photo(msg: Message, state: FSMContext):
    file_id = msg.photo[-1].file_id
    await state.update_data(photo_file_id=file_id, photo_kind="photo")
    await msg.answer("Есть референс? (пример желаемого результата)", reply_markup=yes_no_ref())
    await state.set_state(OrderFlow.waiting_ref)

@dp.message(OrderFlow.waiting_photo, F.document)
async def got_document(msg: Message, state: FSMContext):
    file_id = msg.document.file_id
    await state.update_data(photo_file_id=file_id, photo_kind="document")
    await msg.answer("Есть референс? (пример желаемого результата)", reply_markup=yes_no_ref())
    await state.set_state(OrderFlow.waiting_ref)

@dp.callback_query(OrderFlow.waiting_ref, F.data.in_({"ref_yes", "ref_no"}))
async def ref_choice(cb: CallbackQuery, state: FSMContext):
    if cb.data == "ref_yes":
        await cb.message.edit_text("📎 Отправьте референс (фото или документ).")
        # остаёмся в waiting_ref, но ждём файл
    else:
        await state.update_data(ref_file_id=None, ref_kind=None)
        await cb.message.edit_text(
            "✍️ Напишите пожелания к обработке.\n"
            "Пример: «убрать прыщи, оставить текстуру кожи, выровнять тон, как на рефе»"
        )
        await state.set_state(OrderFlow.waiting_comment)
    await cb.answer()

@dp.message(OrderFlow.waiting_ref, F.photo)
async def got_ref_photo(msg: Message, state: FSMContext):
    await state.update_data(ref_file_id=msg.photo[-1].file_id, ref_kind="photo")
    await msg.answer(
        "✍️ Напишите пожелания к обработке.\n"
        "Пример: «убрать прыщи, оставить текстуру кожи, выровнять тон, как на рефе»"
    )
    await state.set_state(OrderFlow.waiting_comment)

@dp.message(OrderFlow.waiting_ref, F.document)
async def got_ref_doc(msg: Message, state: FSMContext):
    await state.update_data(ref_file_id=msg.document.file_id, ref_kind="document")
    await msg.answer(
        "✍️ Напишите пожелания к обработке.\n"
        "Пример: «убрать прыщи, оставить текстуру кожи, выровнять тон, как на рефе»"
    )
    await state.set_state(OrderFlow.waiting_comment)

@dp.message(OrderFlow.waiting_comment, F.text)
async def got_comment(msg: Message, state: FSMContext):
    await state.update_data(comment=msg.text.strip())
    await msg.answer("Выберите тип услуги:", reply_markup=services_kb())
    await state.set_state(OrderFlow.waiting_service)

@dp.callback_query(OrderFlow.waiting_service, F.data.startswith("svc:"))
async def choose_service(cb: CallbackQuery, state: FSMContext):
    svc_key = cb.data.split(":", 1)[1]
    if svc_key not in SERVICE_MAP:
        await cb.answer("Неизвестная услуга", show_alert=True)
        return

    title, credits = SERVICE_MAP[svc_key]
    data = await state.get_data()

    order_id = db.next_order_id()
    order = Order(
        id=order_id,
        user_id=cb.from_user.id,
        username=cb.from_user.username or "",
        photo_file_id=data["photo_file_id"],
        photo_kind=data["photo_kind"],
        ref_file_id=data.get("ref_file_id"),
        ref_kind=data.get("ref_kind"),
        comment=data.get("comment", ""),
        service=svc_key,
        credits_cost=credits,
        status="new",
    )
    db.create_order(order)

    # В MVP: сразу пробуем списать кредиты, если есть. Иначе "оплата вручную"
    user_credits = db.get_credits(order.user_id)
    if user_credits >= credits and db.spend_credits(order.user_id, credits):
        pay_text = f"✅ Оплачено кредитами. Списано: {credits} cr. Остаток: {db.get_credits(order.user_id)} cr."
    else:
        pay_text = (
            "💳 Оплата: (MVP) пока вручную.\n"
            "Поддержка пришлёт способ оплаты или вы подключите платежи на следующем шаге."
        )

    await cb.message.edit_text(
        f"✅ Заказ #{order_id} создан.\n"
        f"Услуга: {title} ({credits} cr)\n\n"
        f"{pay_text}\n\n"
        f"Статус: на проверке (валидация)."
    )
    await state.clear()
    await cb.answer()

    # Уведомление админам
    for admin_id in cfg.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"🆕 Новый заказ #{order_id}\n"
                f"От: @{order.username or 'без username'} (id {order.user_id})\n"
                f"Услуга: {title} ({credits} cr)\n"
                f"Комментарий: {order.comment[:500]}",
                reply_markup=admin_actions(order_id)
            )
        except Exception:
            pass

@dp.callback_query(F.data == "credits")
async def credits(cb: CallbackQuery):
    bal = db.get_credits(cb.from_user.id)
    await cb.message.edit_text(
        f"💳 Ваш баланс: {bal} cr\n\n"
        "В MVP кредиты можно добавить командой /add_credits (только админ).\n"
        "Дальше подключим автоматическую оплату и подписки.",
        reply_markup=main_menu()
    )
    await cb.answer()

@dp.callback_query(F.data == "support")
async def support(cb: CallbackQuery):
    await cb.message.edit_text(
        "🆘 Поддержка\n\n"
        "Напишите сюда вопрос и обязательно укажите номер заказа.\n"
        "Если вопрос про оплату — тоже номер заказа.\n\n"
        "В прод-версии эта кнопка будет вести в отдельный чат/контакт.",
        reply_markup=main_menu()
    )
    await cb.answer()

# --- Админка ---
@dp.callback_query(F.data.startswith("adm:"))
async def admin_router(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    parts = cb.data.split(":")
    action = parts[1]

    if action == "accept":
        order_id = int(parts[2])
        db.set_status(order_id, "accepted")
        order = db.get_order(order_id)
        await cb.message.edit_text(f"✅ Заказ #{order_id} принят в работу.")
        await cb.answer("OK")
        if order:
            await bot.send_message(order.user_id, f"✅ Ваш заказ #{order_id} принят в работу. Скоро пришлём результат.")
        return

    if action == "reject":
        order_id = int(parts[2])
        db.set_status(order_id, "rejected")
        order = db.get_order(order_id)
        await cb.message.edit_text(f"❌ Заказ #{order_id} отклонён. (Нужно уточнение/неподходящий формат)")
        await cb.answer("OK")
        if order:
            await bot.send_message(order.user_id, f"❌ Ваш заказ #{order_id} отклонён. Напишите в поддержку с номером заказа.")
        return

    if action == "upgrade":
        order_id = int(parts[2])
        await cb.message.edit_text(f"⬆️ Апгрейд заказа #{order_id}: выберите новый тип", reply_markup=upgrade_options(order_id))
        await cb.answer("OK")
        return

    if action == "upg_to":
        new_svc = parts[2]
        order_id = int(parts[3])
        order = db.get_order(order_id)
        if not order:
            await cb.answer("Заказ не найден", show_alert=True)
            return

        old_cost = order.credits_cost
        new_title, new_cost = SERVICE_MAP.get(new_svc, ("", 0))
        diff = max(0, new_cost - old_cost)

        order.service = new_svc
        order.credits_cost = new_cost
        db.set_status(order_id, "upgrade", note=f"Upgrade to {new_svc}")

        await cb.message.edit_text(
            f"⬆️ Заказ #{order_id} требует апгрейда.\n"
            f"Новая услуга: {new_title} ({new_cost} cr)\n"
            f"Доплата: {diff} cr\n\n"
            f"Клиенту отправлено уведомление."
        )
        await cb.answer("OK")

        await bot.send_message(
            order.user_id,
            f"⬆️ Ваш заказ #{order_id} требует апгрейда тарифа.\n"
            f"Новая услуга: {new_title} ({new_cost} cr)\n"
            f"Нужно доплатить: {diff} cr.\n\n"
            f"Ответьте в поддержку с номером заказа — вам пришлём ссылку на оплату/варианты."
        )
        return

    if action == "upg_cancel":
        order_id = int(parts[2])
        await cb.message.edit_text(f"Отменено. Заказ #{order_id} без изменений.")
        await cb.answer("OK")
        return

@dp.message(Command("add_credits"))
async def add_credits_cmd(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    # /add_credits user_id amount
    parts = msg.text.strip().split()
    if len(parts) != 3:
        await msg.answer("Формат: /add_credits user_id amount")
        return
    user_id = int(parts[1])
    amount = int(parts[2])
    new_bal = db.add_credits(user_id, amount)
    await msg.answer(f"✅ Начислено {amount} cr пользователю {user_id}. Баланс: {new_bal} cr.")
    try:
        await bot.send_message(user_id, f"💳 Вам начислено {amount} кредитов. Баланс: {new_bal} cr.")
    except Exception:
        pass

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
