from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from db.base import async_session
from db.models import ComponentType
from states.order import OrderFSM
from services import funnel_service
from keyboards.user import components_kb, date_wishes_kb, confirm_kb
from utils.message import send_step
from config import settings
from handlers.admin.monitoring import registry  # in-memory реестр сессий

router = Router()

# state -> (data-key, следующее состояние, следующий тип/None)
STEP_ORDER = ["occasion", "persons", "shape", "filling", "decoration"]


async def _show_component_step(bot, chat_id, state, step_key):
    type_map = dict(funnel_service.STEP_TYPES)
    async with async_session() as s:
        comps = await funnel_service.components_for_step(s, type_map[step_key])
    await state.set_state(getattr(OrderFSM, step_key))
    registry.set(chat_id, step_key)
    await send_step(bot, chat_id, state,
                    funnel_service.STEP_TITLES[step_key], components_kb(comps))


@router.callback_query(F.data == "menu:custom")
async def start_funnel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:
        pass
    await _show_component_step(cb.bot, cb.message.chat.id, state, "occasion")
    await cb.answer()


@router.callback_query(OrderFSM.occasion, F.data.startswith("comp:"))
async def pick_occasion(cb: CallbackQuery, state: FSMContext):
    await state.update_data(sel_occasion=int(cb.data.split(":")[1]))
    await _show_component_step(cb.bot, cb.message.chat.id, state, "persons")
    await cb.answer()


@router.callback_query(OrderFSM.persons, F.data.startswith("comp:"))
async def pick_persons(cb: CallbackQuery, state: FSMContext):
    await state.update_data(sel_persons=int(cb.data.split(":")[1]))
    await _show_component_step(cb.bot, cb.message.chat.id, state, "shape")
    await cb.answer()


@router.callback_query(OrderFSM.shape, F.data.startswith("comp:"))
async def pick_shape(cb: CallbackQuery, state: FSMContext):
    await state.update_data(sel_shape=int(cb.data.split(":")[1]))
    await _show_component_step(cb.bot, cb.message.chat.id, state, "filling")
    await cb.answer()


@router.callback_query(OrderFSM.filling, F.data.startswith("comp:"))
async def pick_filling(cb: CallbackQuery, state: FSMContext):
    await state.update_data(sel_filling=int(cb.data.split(":")[1]))
    await _show_component_step(cb.bot, cb.message.chat.id, state, "decoration")
    await cb.answer()


@router.callback_query(OrderFSM.decoration, F.data.startswith("comp:"))
async def pick_decoration(cb: CallbackQuery, state: FSMContext):
    await state.update_data(sel_decoration=int(cb.data.split(":")[1]))
    await state.set_state(OrderFSM.date_wishes)
    registry.set(cb.message.chat.id, "date_wishes")
    await send_step(
        cb.bot, cb.message.chat.id, state,
        "📅 Введите желаемую дату (ДД.ММ.ГГГГ) и пожелания одним сообщением:",
        date_wishes_kb(),
    )
    await cb.answer()


@router.message(OrderFSM.date_wishes, F.text)
async def input_date_wishes(message: Message, state: FSMContext):
    text = message.text.strip()
    # первое «слово» пытаемся трактовать как дату, остальное — пожелания
    parts = text.split(maxsplit=1)
    desired_date = parts[0] if parts else None
    wishes = parts[1] if len(parts) > 1 else None
    await state.update_data(desired_date=desired_date, wishes=wishes)

    # переходим к подтверждению
    await _show_confirm(message.bot, message.chat.id, state)


async def _show_confirm(bot, chat_id, state):
    data = await state.get_data()
    ids = []
    for key in STEP_ORDER:
        cid = data.get(f"sel_{key}")
        if cid:
            ids.append(cid)
    async with async_session() as s:
        desc = await funnel_service.build_description(s, ids)
        total = await funnel_service.calculate_price(s, ids, settings.base_price)

    wishes = data.get("wishes")
    date_str = data.get("desired_date") or "не указана"
    text = (
            "🧾 <b>Ваш торт</b>\n\n"
            f"Состав: {desc}\n"
            f"Дата: {date_str}\n"
            + (f"Пожелания: {wishes}\n" if wishes else "")
            + f"\n💰 Итоговая цена: <b>{int(total)}₽</b>"
    )
    await state.set_state(OrderFSM.confirming)
    await state.update_data(_is_template=False)
    registry.set(chat_id, "confirming")

    data2 = await state.get_data()
    if mid := data2.get("last_bot_message_id"):
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass
    msg = await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=confirm_kb())
    await state.update_data(last_bot_message_id=msg.message_id)