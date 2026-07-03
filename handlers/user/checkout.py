import asyncio
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from config import settings
from db.base import async_session
from db.models import User
from db.repositories import calendar as calendar_repo, funnel_events, products as product_repo, users as users_repo
from keyboards.user import confirm_kb, date_wishes_kb, delivery_time_kb, delivery_type_kb
from services import funnel_service
from states.order import OrderFSM
from utils.message import (
    delete_message_ids,
    image_input,
    last_bot_message_ids,
    remember_bot_messages,
    send_step,
)

router = Router()
log = logging.getLogger(__name__)

PICKUP_ADDRESS = "Адрес самовывоза уточнит администратор после подтверждения заказа."


def parse_date(raw: str | None):
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def format_date(value) -> str:
    return value.strftime("%d.%m.%Y") if value else "не указана"


def selected_component_ids(data: dict) -> list[int]:
    ids = []
    for key, _ in funnel_service.STEP_TYPES:
        value = data.get(f"sel_{key}")
        if isinstance(value, list):
            ids.extend(value)
        elif value:
            ids.append(value)
    return ids


async def ask_date(bot, chat_id: int, state: FSMContext):
    await state.set_state(OrderFSM.date_wishes)
    await send_step(
        bot,
        chat_id,
        state,
        "Выберите дату доставки/самовывоза.\n\nВведите дату в формате ДД.ММ.ГГГГ:",
        date_wishes_kb(),
    )


async def process_date_text(message: Message, state: FSMContext):
    text = message.text.strip()
    parts = text.split(maxsplit=1)
    desired_date = parse_date(parts[0] if parts else None)
    if not desired_date:
        await message.answer("Не получилось распознать дату. Введите дату в формате ДД.ММ.ГГГГ.")
        return

    async with async_session() as session:
        if not await calendar_repo.is_available(session, desired_date):
            nearest = await calendar_repo.nearest_available_dates(session, desired_date)
            nearest_text = "\n".join(f"- {format_date(item)}" for item in nearest) or "- пока нет дат"
            await message.answer(
                f"К сожалению, на {format_date(desired_date)} заказы уже не принимаются.\n\n"
                f"Ближайшие доступные даты:\n{nearest_text}"
            )
            return

    wishes = parts[1] if len(parts) > 1 else None
    await state.update_data(desired_date=format_date(desired_date), wishes=wishes)
    try:
        async with async_session() as session:
            user = await users_repo.get_or_create_user(session, message.from_user)
            await funnel_events.log_event(
                session,
                user_id=user.id,
                event_type="step_selected",
                step="date_wishes",
                payload={"desired_date": format_date(desired_date), "has_wishes": bool(wishes)},
            )
    except Exception:
        log.exception("date_step_event_failed telegram_id=%s", message.from_user.id)
    await ask_delivery_type(message.bot, message.chat.id, state)


async def ask_delivery_type(bot, chat_id: int, state: FSMContext):
    await state.set_state(OrderFSM.delivery_type)
    await send_step(
        bot,
        chat_id,
        state,
        "Как хотите получить заказ?",
        delivery_type_kb(),
    )


@router.callback_query(OrderFSM.delivery_type, F.data.startswith("delivery:type:"))
async def choose_delivery_type(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    delivery_type = cb.data.split(":")[2]
    await state.update_data(delivery_type=delivery_type)
    if delivery_type == "delivery":
        await state.set_state(OrderFSM.delivery_address)
        await send_step(
            cb.bot,
            cb.message.chat.id,
            state,
            "Введите адрес доставки и комментарий курьеру, если он нужен:",
            date_wishes_kb(),
        )
        return

    await state.update_data(delivery_address=PICKUP_ADDRESS, delivery_comment=None)
    await ask_delivery_time(cb.bot, cb.message.chat.id, state)


@router.message(OrderFSM.delivery_address, F.text)
async def input_delivery_address(message: Message, state: FSMContext):
    await state.update_data(delivery_address=message.text.strip())
    await ask_delivery_time(message.bot, message.chat.id, state)


async def ask_delivery_time(bot, chat_id: int, state: FSMContext):
    data = await state.get_data()
    date_text = data.get("desired_date") or "не указана"
    await state.set_state(OrderFSM.delivery_time)
    await send_step(
        bot,
        chat_id,
        state,
        f"Когда нужен торт?\n\nДата: {date_text}\nВремя:",
        delivery_time_kb(),
    )


@router.callback_query(OrderFSM.delivery_time, F.data.startswith("delivery:time:"))
async def choose_delivery_time(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    raw_interval = cb.data.removeprefix("delivery:time:")
    time_from, time_to = raw_interval[:5], raw_interval[-5:]
    await state.update_data(delivery_time_from=time_from, delivery_time_to=time_to)
    await show_confirm(cb.bot, cb.message.chat.id, state)


async def show_confirm(bot, chat_id: int, state: FSMContext):
    data = await state.get_data()
    is_template = data.get("_is_template", False)
    ids = selected_component_ids(data)
    product = None

    async with async_session() as session:
        if is_template and data.get("template_id"):
            product = await product_repo.get_with_components(session, data["template_id"])
            total = product.price
            desc = product.name
            weight = await funnel_service.calculate_weight_kg(
                session,
                [pc.component_id for pc in product.components],
            )
        elif data.get("_repeat_order_id"):
            total = data.get("repeat_price", 0)
            desc = data.get("repeat_description") or "повтор заказа"
            weight = None
            raw_weight = data.get("repeat_weight")
            if raw_weight:
                text_weight = str(raw_weight).replace(" кг", "")
                weight = text_weight
        else:
            desc = await funnel_service.build_description(session, ids)
            total = await funnel_service.calculate_price(session, ids, settings.base_price)
            weight = await funnel_service.calculate_weight_kg(session, ids)

    delivery_label = "Доставка" if data.get("delivery_type") == "delivery" else "Самовывоз"
    time_text = (
        f"{data.get('delivery_time_from')}-{data.get('delivery_time_to')}"
        if data.get("delivery_time_from") and data.get("delivery_time_to")
        else "не указано"
    )
    text = (
        "🧾 <b>Ваш заказ</b>\n\n"
        f"Состав: {desc or '—'}\n"
        f"Дата: {data.get('desired_date') or 'не указана'}\n"
        f"Получение: {delivery_label}\n"
        f"Время: {time_text}\n"
    )
    if data.get("delivery_address"):
        text += f"Адрес: {data['delivery_address']}\n"
    if data.get("wishes"):
        text += f"Пожелания: {data['wishes']}\n"
    if weight:
        text += f"\n🎂 Примерный вес: <b>{weight} кг</b>"
    text += f"\n💰 Цена: <b>{int(total or 0)}₽</b>"

    await state.set_state(OrderFSM.confirming)
    try:
        async with async_session() as session:
            res_user = await session.execute(select(User).where(User.telegram_id == chat_id))
            user = res_user.scalar_one_or_none()
            if user:
                await funnel_events.log_event(
                    session,
                    user_id=user.id,
                    event_type="confirmation_shown",
                    step="confirming",
                    payload={"is_template": bool(is_template), "repeat": bool(data.get("_repeat_order_id"))},
                )
    except Exception:
        log.exception("confirmation_event_failed chat_id=%s", chat_id)
    old_ids = last_bot_message_ids(await state.get_data())
    asyncio.create_task(delete_message_ids(bot, chat_id, old_ids))

    if product and product.image_url:
        msg = await bot.send_photo(
            chat_id,
            image_input(product.image_url),
            caption=text,
            parse_mode="HTML",
            reply_markup=confirm_kb(),
        )
    else:
        msg = await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=confirm_kb())
    await remember_bot_messages(state, [msg])
