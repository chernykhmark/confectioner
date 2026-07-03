from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from db.base import async_session
from db.repositories import users as users_repo
from keyboards.user import main_menu
from keyboards.admin import admin_menu
from config import settings
from states.order import OrderFSM
from utils.message import send_step
from services import funnel_service
from keyboards.user import components_kb

from db.repositories import sessions as sessions_repo
from db.repositories import users as users_repo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from states.order import OrderFSM


router = Router()

WELCOME = "🎂 Добро пожаловать в конструктор тортов!\nВыберите действие:"
HELP_TEXT = (
    "ℹ️ <b>Справка</b>\n\n"
    "• «Популярные заказы» — готовые торты в один клик.\n"
    "• «Создать самому» — соберите торт по шагам, цена посчитается автоматически.\n"
    "На каждом шаге можно вернуться назад или в меню."
)

# порядок шагов для навигации «назад»
FUNNEL_STEPS = ["occasion", "persons", "shape", "filling", "decoration", "date_wishes"]





def _resume_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="▶️ Продолжить", callback_data="resume:yes")
    kb.button(text="🔄 Начать заново", callback_data="resume:no")
    kb.adjust(1)
    return kb.as_markup()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    async with async_session() as s:
        user = await users_repo.get_or_create_user(s, message.from_user)
        sess = await sessions_repo.get_session(s, user.id)

    # админ — только панель, без пользовательского меню и без draft-логики
    if user.is_admin:
        await message.answer("🛠 Панель администратора:", reply_markup=admin_menu())
        return

    # есть незавершённый draft — предлагаем продолжить
    if sess and sess.draft and any(k.startswith("sel_") for k in sess.draft):
        await message.answer(
            f"🔔 У вас есть незавершённый торт (шаг «{sess.current_step}»).\n"
            "Продолжить сборку или начать заново?",
            reply_markup=_resume_kb(),
        )
        return

    await message.answer(WELCOME, reply_markup=main_menu())


@router.callback_query(F.data == "menu:help")
async def show_help(cb: CallbackQuery):
    await cb.message.edit_text(HELP_TEXT, parse_mode="HTML", reply_markup=main_menu())
    await cb.answer()

@router.callback_query(F.data == "resume:yes")
async def resume_yes(cb: CallbackQuery, state: FSMContext):
    async with async_session() as s:
        user = await users_repo.get_or_create_user(s, cb.from_user)
        sess = await sessions_repo.get_session(s, user.id)
    if not sess or not sess.draft:
        await go_home(cb, state)
        return

    # единый источник при восстановлении: draft -> FSM-data
    draft = {k: v for k, v in sess.draft.items() if not k.startswith("_")}
    await state.set_data(draft)
    step = sess.current_step or "occasion"

    try:
        await cb.message.delete()
    except Exception:
        pass

    # восстановление шага
    if step in ("occasion", "persons", "shape", "filling", "decoration"):
        await _render_component_step(cb, state, step)
    elif step == "date_wishes":
        from keyboards.user import date_wishes_kb
        await state.set_state(OrderFSM.date_wishes)
        await send_step(cb.bot, cb.message.chat.id, state,
                        "📅 Введите желаемую дату (ДД.ММ.ГГГГ) и пожелания:",
                        date_wishes_kb())
    elif step == "confirming":
        from handlers.user.funnel import _show_confirm
        await _show_confirm(cb.bot, cb.message.chat.id, state)
    else:
        await go_home(cb, state)
    await cb.answer()


@router.callback_query(F.data == "resume:no")
async def resume_no(cb: CallbackQuery, state: FSMContext):
    async with async_session() as s:
        user = await users_repo.get_or_create_user(s, cb.from_user)
        await sessions_repo.delete_session(s, user.id)
    await go_home(cb, state)


@router.callback_query(F.data == "nav:home")
async def go_home(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    # удаляем персист-сессию при выходе в меню
    async with async_session() as s:
        user = await users_repo.get_or_create_user(s, cb.from_user)
        await sessions_repo.delete_session(s, user.id)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(WELCOME, reply_markup=main_menu())
    await cb.answer()



async def _render_component_step(cb, state, step_key):
    """Отрисовать шаг воронки по ключу (для «Назад»)."""
    from db.models import ComponentType
    type_map = dict(funnel_service.STEP_TYPES)
    ctype: ComponentType = type_map[step_key]
    async with async_session() as s:
        comps = await funnel_service.components_for_step(s, ctype)
    await getattr(state, "set_state")(getattr(OrderFSM, step_key
        if step_key != "decoration" else "decoration"))
    title = funnel_service.STEP_TITLES[step_key]
    await send_step(cb.bot, cb.message.chat.id, state, title, components_kb(comps))


@router.callback_query(F.data == "nav:back")
async def go_back(cb: CallbackQuery, state: FSMContext):
    cur = await state.get_state()
    # текущий шаг -> индекс
    step_name = cur.split(":")[-1] if cur else None

    # шаблонная ветка
    if step_name == OrderFSM.choosing_template.state.split(":")[-1]:
        await go_home(cb, state)
        return

    if step_name in FUNNEL_STEPS:
        idx = FUNNEL_STEPS.index(step_name)
        if idx == 0:
            await go_home(cb, state)
            return
        prev = FUNNEL_STEPS[idx - 1]
        if prev == "date_wishes":
            # маловероятно, но на всякий
            await _render_component_step(cb, state, "decoration")
        else:
            await _render_component_step(cb, state, prev)
        await cb.answer()
        return

    if step_name == "confirming":
        # назад к последнему шагу воронки (date_wishes)
        await state.set_state(OrderFSM.date_wishes)
        from keyboards.user import date_wishes_kb
        await send_step(cb.bot, cb.message.chat.id, state,
                        "📅 Введите желаемую дату (ДД.ММ.ГГГГ) и пожелания одним сообщением:",
                        date_wishes_kb())
        await cb.answer()
        return

    await go_home(cb, state)
    await cb.answer()