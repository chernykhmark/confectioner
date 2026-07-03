import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from db.base import async_session
from db.repositories import products as product_repo
from handlers.admin.monitoring import registry
from keyboards.user import (
    catalog_empty_kb,
    catalog_options_kb,
    catalog_products_kb,
    catalog_result_kb,
    confirm_kb,
)
from services import catalog_service
from states.order import OrderFSM
from utils.message import (
    delete_last_bot_messages,
    delete_message_ids,
    last_bot_message_ids,
    remember_bot_messages,
    send_photo_or_message,
    send_step,
)

router = Router()


def _product_text(product) -> str:
    summary = catalog_service.selection_summary(product)
    return (
        f"<b>Подобран торт</b>\n\n"
        f"<b>{product.name}</b>\n"
        f"{summary}\n\n"
        f"{product.description or ''}\n\n"
        f"Цена: <b>{int(product.price)}₽</b>"
    )


async def _show_product_result(bot, chat_id: int, state: FSMContext, product):
    await state.set_state(OrderFSM.catalog)
    old_ids = last_bot_message_ids(await state.get_data())
    asyncio.create_task(delete_message_ids(bot, chat_id, old_ids))

    text = _product_text(product)
    msg = await send_photo_or_message(
        bot,
        chat_id,
        product.image_url,
        text,
        parse_mode="HTML",
        reply_markup=catalog_result_kb(product.id),
        log_context=f"catalog_product:{product.id}",
    )
    await remember_bot_messages(state, [msg])


async def _show_catalog_step(bot, chat_id: int, state: FSMContext):
    data = await state.get_data()
    selected_ids = catalog_service.selected_ids_from_data(data)
    selected_steps = {
        key.removeprefix("cat_"): value
        for key, value in data.items()
        if key.startswith("cat_")
    }

    async with async_session() as session:
        products = await product_repo.list_catalog_products(session)
        candidates = catalog_service.candidates_for(products, selected_ids)
        next_step = catalog_service.next_step_key(selected_steps)
        selected_text = await catalog_service.selected_description(session, selected_ids)

    if not candidates:
        await send_step(
            bot,
            chat_id,
            state,
            "Не нашли точного варианта по выбранным параметрам.\n\n"
            "Можно подобрать заново или перейти в индивидуальный заказ.",
            catalog_empty_kb(),
        )
        return

    if len(candidates) == 1:
        await _show_product_result(bot, chat_id, state, candidates[0])
        return

    if not next_step:
        text = (
            "Мы нашли несколько вариантов:\n\n"
            + "\n".join(
                f"{idx}. {product.name} — {int(product.price)}₽"
                for idx, product in enumerate(candidates, start=1)
            )
            + "\n\nВыберите подходящий:"
        )
        await send_step(bot, chat_id, state, text, catalog_products_kb(candidates))
        return

    if next_step == "filling":
        text = (
            f"{catalog_service.CATALOG_TITLES[next_step]}\n\n"
            f"Уже выбрано: {selected_text}"
        )
        await send_step(bot, chat_id, state, text, catalog_products_kb(candidates))
        return

    step_type = dict(catalog_service.CATALOG_STEPS)[next_step]
    options = catalog_service.available_options(products, selected_ids, step_type)
    if not options:
        text = (
            "По выбранным параметрам осталось несколько вариантов:\n\n"
            + "\n".join(
                f"{idx}. {product.name} — {int(product.price)}₽"
                for idx, product in enumerate(candidates, start=1)
            )
            + "\n\nВыберите подходящий:"
        )
        await send_step(bot, chat_id, state, text, catalog_products_kb(candidates))
        return

    title = catalog_service.CATALOG_TITLES[next_step]
    text = f"{title}\n\nУже выбрано: {selected_text}"
    await send_step(
        bot,
        chat_id,
        state,
        text,
        catalog_options_kb(
            options,
            show_counts=False,
            show_restart=(next_step != "shape"),
        ),
    )


@router.callback_query(F.data == "menu:catalog")
async def start_catalog(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await delete_last_bot_messages(cb.bot, cb.message.chat.id, state)
    await state.clear()
    await state.set_state(OrderFSM.catalog)
    registry.set(cb.message.chat.id, "catalog")
    try:
        await cb.message.delete()
    except Exception:
        pass
    await _show_catalog_step(cb.bot, cb.message.chat.id, state)


@router.callback_query(F.data == "cat:restart")
async def restart_catalog(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await delete_last_bot_messages(cb.bot, cb.message.chat.id, state)
    await state.clear()
    await state.set_state(OrderFSM.catalog)
    registry.set(cb.message.chat.id, "catalog")
    await _show_catalog_step(cb.bot, cb.message.chat.id, state)


@router.callback_query(F.data == "cat:back")
async def back_to_catalog_list(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await _show_catalog_step(cb.bot, cb.message.chat.id, state)


@router.callback_query(OrderFSM.catalog, F.data.startswith("cat:comp:"))
async def choose_catalog_component(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    component_id = int(cb.data.split(":")[2])

    async with async_session() as session:
        products = await product_repo.list_catalog_products(session)

    selected_ids = catalog_service.selected_ids_from_data(await state.get_data())
    for step_key, step_type in catalog_service.CATALOG_STEPS:
        options = catalog_service.available_options(products, selected_ids, step_type)
        if any(component.id == component_id for component, _ in options):
            await state.update_data(**{f"cat_{step_key}": component_id})
            break

    await _show_catalog_step(cb.bot, cb.message.chat.id, state)


@router.callback_query(F.data.startswith("cat:preview:"))
async def preview_catalog_product(cb: CallbackQuery, state: FSMContext):
    product_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        product = await product_repo.get_with_components(session, product_id)
    if not product:
        await cb.answer("Торт не найден", show_alert=True)
        return

    await cb.answer()
    await _show_product_result(cb.bot, cb.message.chat.id, state, product)


@router.callback_query(F.data.startswith("cat:product:"))
async def choose_catalog_product(cb: CallbackQuery, state: FSMContext):
    product_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        product = await product_repo.get_with_components(session, product_id)
    if not product:
        await cb.answer("Торт не найден", show_alert=True)
        return

    await cb.answer()
    await state.update_data(_is_template=True, template_id=product.id, desired_date=None)
    from handlers.user.checkout import ask_date
    await ask_date(cb.bot, cb.message.chat.id, state)
