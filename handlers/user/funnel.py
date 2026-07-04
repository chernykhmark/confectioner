import asyncio
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from db.base import async_session
from db.models import ComponentType
from states.order import OrderFSM
from services import funnel_service
from keyboards.user import (
    budget_kb,
    component_card_kb,
    components_kb,
    decoration_multi_kb,
)
from utils.message import (
    delete_last_bot_messages,
    delete_message_ids,
    image_input,
    last_bot_message_ids,
    remember_bot_messages,
    send_step,
)
from config import settings
from handlers.admin.monitoring import registry  # in-memory реестр сессий
# ... импорты — добавить:
from db.repositories import funnel_events, users as users_repo
from db.repositories import sessions as sessions_repo


router = Router()
log = logging.getLogger(__name__)

# state -> (data-key, следующее состояние, следующий тип/None)
STEP_ORDER = ["occasion", "persons", "shape", "decoration"]


from sqlalchemy import select
from db.models import User

def _draft_from_data(data: dict) -> dict:
    return {
        k: v for k, v in data.items()
        if k not in ("last_bot_message_id", "last_bot_message_ids")
    }


async def _persist_draft(chat_id, step_key, draft):
    """Дублировать текущий шаг и выбор в user_sessions."""
    if not draft:
        return

    async with async_session() as s:
        res = await s.execute(select(User).where(User.telegram_id == chat_id))
        user = res.scalar_one_or_none()
        if user:
            await sessions_repo.upsert_session(s, user.id, step_key, draft)


async def _log_funnel_event(tg_user, event_type: str, step: str | None = None, payload: dict | None = None):
    try:
        async with async_session() as s:
            user = await users_repo.get_or_create_user(s, tg_user)
            await funnel_events.log_event(
                s,
                user_id=user.id,
                event_type=event_type,
                step=step,
                payload=payload,
            )
    except Exception:
        log.exception("funnel_event_write_failed event_type=%s step=%s", event_type, step)


def _component_text(component) -> str:
    price_delta = int(component.price_delta or 0)
    price = f"+{price_delta}₽" if price_delta else "без доплаты"
    text = f"🎂 <b>{component.name}</b>\n{price}"
    if getattr(component, "short_description", None):
        text += f"\n{component.short_description}"
    return text


async def _send_component_cards(bot, chat_id, state, title, components):
    old_ids = last_bot_message_ids(await state.get_data())
    asyncio.create_task(delete_message_ids(bot, chat_id, old_ids))
    messages = [await bot.send_message(chat_id, title)]

    for component in components:
        caption = _component_text(component)
        if component.image_url:
            try:
                msg = await bot.send_photo(
                    chat_id,
                    image_input(component.image_url),
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=component_card_kb(component.id),
                )
            except Exception:
                msg = await bot.send_message(
                    chat_id,
                    caption,
                    parse_mode="HTML",
                    reply_markup=component_card_kb(component.id),
                )
        else:
            msg = await bot.send_message(
                chat_id,
                caption,
                parse_mode="HTML",
                reply_markup=component_card_kb(component.id),
            )
        messages.append(msg)

    await remember_bot_messages(state, messages)


async def _show_component_step(bot, chat_id, state, step_key):
    type_map = dict(funnel_service.STEP_TYPES)
    async with async_session() as s:
        comps = await funnel_service.components_for_step(s, type_map[step_key])
    await state.set_state(getattr(OrderFSM, step_key))
    registry.set(chat_id, step_key)
    asyncio.create_task(_persist_draft(chat_id, step_key, _draft_from_data(await state.get_data())))
    title = funnel_service.STEP_TITLES[step_key]
    if step_key == "decoration":
        selected = (await state.get_data()).get("sel_decoration", [])
        await send_step(
            bot,
            chat_id,
            state,
            f"{title}\n\nМожно выбрать до трёх элементов.",
            decoration_multi_kb(comps, selected),
        )
        return
    if any(c.image_url for c in comps):
        await _send_component_cards(bot, chat_id, state, title, comps)
    else:
        await send_step(bot, chat_id, state, title, components_kb(comps))


@router.callback_query(F.data == "menu:custom")
async def start_funnel(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:
        log.exception("start_funnel_delete_failed chat_id=%s", cb.message.chat.id)
    await _log_funnel_event(cb.from_user, "funnel_started", "budget")
    await state.set_state(OrderFSM.budget)
    await send_step(
        cb.bot,
        cb.message.chat.id,
        state,
        "Какой ориентировочный бюджет?",
        budget_kb(),
    )


@router.callback_query(OrderFSM.budget, F.data.startswith("budget:"))
async def pick_budget(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    budget = cb.data.split(":", 1)[1]
    await state.update_data(budget=budget)
    await _log_funnel_event(cb.from_user, "step_selected", "budget", {"budget": budget})
    await _show_component_step(cb.bot, cb.message.chat.id, state, "occasion")


@router.callback_query(OrderFSM.occasion, F.data.startswith("comp:"))
async def pick_occasion(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    component_id = int(cb.data.split(":")[1])
    await state.update_data(sel_occasion=component_id)
    await _log_funnel_event(cb.from_user, "step_selected", "occasion", {"component_id": component_id})
    await _show_component_step(cb.bot, cb.message.chat.id, state, "persons")


@router.callback_query(OrderFSM.persons, F.data.startswith("comp:"))
async def pick_persons(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    component_id = int(cb.data.split(":")[1])
    await state.update_data(sel_persons=component_id)
    await _log_funnel_event(cb.from_user, "step_selected", "persons", {"component_id": component_id})
    await _show_component_step(cb.bot, cb.message.chat.id, state, "shape")


@router.callback_query(OrderFSM.shape, F.data.startswith("comp:"))
async def pick_shape(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    component_id = int(cb.data.split(":")[1])
    await state.update_data(sel_shape=component_id)
    await _log_funnel_event(cb.from_user, "step_selected", "shape", {"component_id": component_id})
    await _show_component_step(cb.bot, cb.message.chat.id, state, "decoration")


@router.callback_query(OrderFSM.decoration, F.data.startswith("decor:toggle:"))
async def toggle_decoration(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    component_id = int(cb.data.split(":")[2])
    data = await state.get_data()
    selected = list(data.get("sel_decoration", []))
    if component_id in selected:
        selected.remove(component_id)
    elif len(selected) >= 3:
        await cb.answer("Можно выбрать не больше трёх элементов", show_alert=True)
        return
    else:
        selected.append(component_id)
    await state.update_data(sel_decoration=selected)
    await _log_funnel_event(
        cb.from_user,
        "step_selected",
        "decoration",
        {"component_id": component_id, "selected_ids": selected},
    )
    await _show_component_step(cb.bot, cb.message.chat.id, state, "decoration")


@router.callback_query(OrderFSM.decoration, F.data == "decor:done")
async def pick_decoration_done(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("sel_decoration"):
        await cb.answer("Выберите хотя бы один элемент оформления", show_alert=True)
        return
    await cb.answer()
    await _log_funnel_event(cb.from_user, "date_reached", "date_wishes")
    from handlers.user.checkout import ask_date
    await ask_date(cb.bot, cb.message.chat.id, state)



async def _show_confirm(bot, chat_id, state):
    from handlers.user.checkout import show_confirm
    await state.update_data(_is_template=False)
    await show_confirm(bot, chat_id, state)


async def start_funnel_from(bot, chat_id: int, state: FSMContext, tg_user):
    """Запуск кастомной воронки программно (для админского создания заказа)."""
    await _log_funnel_event(tg_user, "funnel_started", "budget")
    await state.set_state(OrderFSM.budget)
    await send_step(bot, chat_id, state, "Какой ориентировочный бюджет?", budget_kb())


async def start_funnel_from(bot, chat_id: int, state: FSMContext, tg_user):
    await _log_funnel_event(tg_user, "funnel_started", "budget")
    await state.set_state(OrderFSM.budget)
    await send_step(bot, chat_id, state, "Какой ориентировочный бюджет?", budget_kb())