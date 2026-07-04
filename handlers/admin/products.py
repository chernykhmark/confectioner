from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from db.base import async_session
from db.repositories import components as component_repo
from db.repositories import products as product_repo
from db.models import ComponentType
from keyboards.admin import (
    admin_menu,
    edit_component_kb,
    edit_component_types_kb,
    edit_components_kb,
    edit_product_kb,
    edit_products_kb,
    edit_root_kb,
    product_cancel_kb,
    product_component_kb,
    product_confirm_kb,
    product_decor_multi_kb,
    product_image_kb,
)
from services import catalog_service
from states.admin_product import AdminEditFSM, AdminProductFSM
from utils.message import remember_bot_messages, send_photo_or_message
from states.admin_product import AdminNewComponentFSM


router = Router()

from keyboards.admin import product_availability_kb
from db.models import ProductStatus


@router.callback_query(F.data.startswith("adm:edit:availability:"))
async def edit_availability(cb: CallbackQuery):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    product_id = int(cb.data.split(":")[3])
    await cb.message.edit_text(
        "Выберите доступность продукта:",
        reply_markup=product_availability_kb(product_id),
    )


@router.callback_query(F.data.startswith("adm:set_avail:"))
async def set_availability(cb: CallbackQuery):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    _, _, product_id_raw, status_raw = cb.data.split(":")
    product_id = int(product_id_raw)
    async with async_session() as session:
        await product_repo.update_product(session, product_id, status=ProductStatus(status_raw))
    await _show_edit_product(cb.message, product_id)

def _is_admin_user(user_id: int | None) -> bool:
    return user_id == settings.admin_telegram_id


def _price_from_text(text: str) -> Decimal | None:
    normalized = text.strip().replace(" ", "").replace(",", ".")
    try:
        price = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None
    return price if price > 0 else None


def _full_description(description: str, ingredients: str) -> str:
    return f"{description.strip()}\nСостав: {ingredients.strip()}"


async def _remember_prompt(message: Message, state: FSMContext):
    await remember_bot_messages(state, [message])




@router.callback_query(F.data.startswith("adm:comp:new:"))
async def new_component_start(cb: CallbackQuery, state: FSMContext):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    ctype = cb.data.split(":")[-1]
    # запоминаем контекст редактора, чтобы вернуться
    data = await state.get_data()
    # определяем контекст: создание продукта или редактирование
    from_create = "product_component_step" in data
    await state.update_data(
        _new_comp_type=ctype,
        _new_comp_return=dict(data),
        _new_comp_return_state="create" if from_create else "edit",
    )
    await state.set_state(AdminNewComponentFSM.name)
    await cb.message.answer("Введите название нового компонента:")


@router.message(AdminNewComponentFSM.name, F.text)
async def new_component_name(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return
    await state.update_data(_new_comp_name=message.text.strip()[:64])
    await state.set_state(AdminNewComponentFSM.price)
    await message.answer("Введите надбавку к цене (число, 0 если нет):")


@router.message(AdminNewComponentFSM.price, F.text)
async def new_component_price(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return
    price = _price_from_text(message.text) or Decimal("0")
    data = await state.get_data()
    ctype = ComponentType(data["_new_comp_type"])
    async with async_session() as session:
        component = await component_repo.create_component(
            session, type=ctype, name=data["_new_comp_name"], price_delta=price,
        )
    await message.answer(f"Компонент «{component.name}» создан. Выберите его в списке.")
    # вернуть в редактор компонентов
    prev = data.get("_new_comp_return") or {}
    return_state = data.get("_new_comp_return_state", "edit")
    await state.set_data(prev)
    if return_state == "create":
        await state.set_state(AdminProductFSM.components)
        await _show_component_pick(message, state)
    else:
        await state.set_state(AdminEditFSM.product_components)
        await _show_edit_product_component_pick(message, state)

@router.callback_query(F.data == "adm:product:new")
async def start_product_create(cb: CallbackQuery, state: FSMContext):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    await cb.answer()
    await state.clear()
    await state.set_state(AdminProductFSM.image)
    await state.update_data(image_url=None)

    text = (
        "Создание продукта\n\n"
        "Шаг 1 из 5. Отправьте изображение продукта.\n"
        "Можно отправить фото или картинку файлом."
    )
    try:
        await cb.message.edit_text(text, reply_markup=product_image_kb())
        await remember_bot_messages(state, [cb.message])
    except Exception:
        msg = await cb.message.answer(text, reply_markup=product_image_kb())
        await _remember_prompt(msg, state)


@router.callback_query(F.data == "adm:product:skip_image")
async def skip_product_image(cb: CallbackQuery, state: FSMContext):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    await cb.answer()
    await state.update_data(image_url=None)
    await state.set_state(AdminProductFSM.name)
    msg = await cb.message.answer("Шаг 2 из 5. Введите название продукта:", reply_markup=product_cancel_kb())
    await _remember_prompt(msg, state)


@router.message(AdminProductFSM.image, F.photo)
async def product_image_photo(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return

    await state.update_data(image_url=message.photo[-1].file_id)
    await state.set_state(AdminProductFSM.name)
    msg = await message.answer("Шаг 2 из 5. Введите название продукта:", reply_markup=product_cancel_kb())
    await _remember_prompt(msg, state)


@router.message(AdminProductFSM.image, F.document)
async def product_image_document(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return

    document = message.document
    if not document.mime_type or not document.mime_type.startswith("image/"):
        await message.answer("Нужна картинка. Отправьте изображение или нажмите «Пропустить изображение».")
        return

    await state.update_data(image_url=document.file_id)
    await state.set_state(AdminProductFSM.name)
    msg = await message.answer("Шаг 2 из 5. Введите название продукта:", reply_markup=product_cancel_kb())
    await _remember_prompt(msg, state)


@router.message(AdminProductFSM.image)
async def product_image_invalid(message: Message):
    if not _is_admin_user(message.from_user.id):
        return
    await message.answer("Отправьте изображение продукта или нажмите «Пропустить изображение».")


@router.message(AdminProductFSM.name, F.text)
async def product_name(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return

    name = message.text.strip()
    if not name:
        await message.answer("Название не должно быть пустым.")
        return

    await state.update_data(name=name[:64])
    await state.set_state(AdminProductFSM.description)
    msg = await message.answer("Шаг 3 из 5. Введите описание продукта:", reply_markup=product_cancel_kb())
    await _remember_prompt(msg, state)


@router.message(AdminProductFSM.description, F.text)
async def product_description(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return

    description = message.text.strip()
    if not description:
        await message.answer("Описание не должно быть пустым.")
        return

    await state.update_data(description=description)
    await state.set_state(AdminProductFSM.price)
    msg = await message.answer("Шаг 4 из 5. Введите цену в рублях:", reply_markup=product_cancel_kb())
    await _remember_prompt(msg, state)


@router.message(AdminProductFSM.price, F.text)
async def product_price(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return

    price = _price_from_text(message.text)
    if price is None:
        await message.answer("Введите цену числом, например: 4500")
        return

    await state.update_data(price=str(price))
    await state.set_state(AdminProductFSM.ingredients)
    msg = await message.answer("Шаг 5 из 5. Введите состав или ингредиенты:", reply_markup=product_cancel_kb())
    await _remember_prompt(msg, state)


@router.message(AdminProductFSM.ingredients, F.text)
async def product_ingredients(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return

    ingredients = message.text.strip()
    if not ingredients:
        await message.answer("Состав не должен быть пустым.")
        return

    await state.update_data(
        ingredients=ingredients,
        product_component_ids=[],
        product_decor_ids=[],
        product_component_step=0,
    )
    await state.set_state(AdminProductFSM.components)
    await _show_component_pick(message, state)

async def _show_component_pick(message: Message, state: FSMContext):
    data = await state.get_data()
    step_index = data.get("product_component_step", 0)
    steps = catalog_service.ADMIN_PRODUCT_STEPS
    if step_index >= len(steps):
        await _show_product_confirm(message, state)
        return

    step_key, component_type = steps[step_index]
    async with async_session() as session:
        components = await component_repo.list_by_type(session, component_type)

    title = catalog_service.ADMIN_PRODUCT_TITLES[step_key]

    if step_key == "decoration":
        selected = data.get("product_decor_ids") or []
        msg = await message.answer(
            f"{title}\n\nМожно выбрать до 5 элементов.",
            reply_markup=product_decor_multi_kb(components, selected),
        )
    else:
        msg = await message.answer(
            title,
            reply_markup=product_component_kb(components, allow_create=True, ctype=component_type.value),
        )
    await _remember_prompt(msg, state)


async def _show_product_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.set_state(AdminProductFSM.confirming)

    total_components = len(data.get("product_component_ids") or []) + len(data.get("product_decor_ids") or [])
    summary = (
        "<b>Проверьте продукт</b>\n\n"
        f"Название: {data['name']}\n"
        f"Описание: {data['description']}\n"
        f"Цена: <b>{int(Decimal(data['price']))}₽</b>\n"
        f"Состав: {data['ingredients']}\n"
        f"Компонентов каталога: {total_components}\n"
        f"Изображение: {'добавлено' if data.get('image_url') else 'нет'}"
    )
    image_url = data.get("image_url")
    if image_url:
        msg = await send_photo_or_message(
            message.bot,
            message.chat.id,
            image_url,
            summary,
            parse_mode="HTML",
            reply_markup=product_confirm_kb(),
            log_context="admin_product_confirm",
        )
    else:
        msg = await message.answer(summary, parse_mode="HTML", reply_markup=product_confirm_kb())
    await _remember_prompt(msg, state)


@router.callback_query(AdminProductFSM.components, F.data.startswith("adm:product:component:"))
async def product_component(cb: CallbackQuery, state: FSMContext):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    await cb.answer()
    data = await state.get_data()
    component_ids = list(data.get("product_component_ids") or [])
    raw = cb.data.split(":")[-1]
    if raw != "skip":
        component_id = int(raw)
        if component_id not in component_ids:
            component_ids.append(component_id)

    await state.update_data(
        product_component_ids=component_ids,
        product_component_step=data.get("product_component_step", 0) + 1,
    )
    await _show_component_pick(cb.message, state)


@router.callback_query(AdminProductFSM.components, F.data.startswith("adm:product:decor:"))
async def product_decor(cb: CallbackQuery, state: FSMContext):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    await cb.answer()
    data = await state.get_data()
    decor_ids = list(data.get("product_decor_ids") or [])
    raw = cb.data.split(":")[-1]

    if raw == "done":
        await state.update_data(product_component_step=data.get("product_component_step", 0) + 1)
        await _show_component_pick(cb.message, state)
        return

    component_id = int(raw)
    if component_id in decor_ids:
        decor_ids.remove(component_id)
    elif len(decor_ids) < 5:
        decor_ids.append(component_id)
    else:
        await cb.answer("Можно выбрать не более 5", show_alert=True)
        return

    await state.update_data(product_decor_ids=decor_ids)
    async with async_session() as session:
        components = await component_repo.list_by_type(session, ComponentType.decor)
    try:
        await cb.message.edit_reply_markup(reply_markup=product_decor_multi_kb(components, decor_ids))
    except Exception:
        pass


@router.callback_query(F.data == "adm:product:confirm")
async def confirm_product_create(cb: CallbackQuery, state: FSMContext):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    required = ("name", "description", "price", "ingredients")
    if not all(data.get(key) for key in required):
        await cb.answer("Не хватает данных", show_alert=True)
        return

    await cb.answer()
    description = _full_description(data["description"], data["ingredients"])
    all_component_ids = list(data.get("product_component_ids") or []) + list(data.get("product_decor_ids") or [])
    async with async_session() as session:
        product = await product_repo.create_template_product(
            session,
            name=data["name"],
            description=description,
            price=Decimal(data["price"]),
            image_url=data.get("image_url"),
            component_ids=all_component_ids,
        )

    await cb.answer()
    await state.clear()
    try:
        await cb.message.edit_text("Создание продукта отменено.", reply_markup=admin_menu())
    except Exception:
        await cb.message.answer("Создание продукта отменено.", reply_markup=admin_menu())

@router.callback_query(F.data == "adm:product:cancel")
async def cancel_product_create(cb: CallbackQuery, state: FSMContext):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return

    await cb.answer()
    await state.clear()
    try:
        await cb.message.edit_text("Создание продукта отменено.", reply_markup=admin_menu())
    except Exception:
        await cb.message.answer("Создание продукта отменено.", reply_markup=admin_menu())


def _component_type_from_raw(raw: str) -> ComponentType:
    return ComponentType(raw)


async def _show_edit_product(message: Message, product_id: int):
    async with async_session() as session:
        product = await product_repo.get_with_components(session, product_id)
    if not product:
        await message.edit_text("Продукт не найден.", reply_markup=edit_root_kb())
        return

    components = ", ".join(pc.component.name for pc in product.components) or "не указаны"
    status_text = "Доступен" if product.status == ProductStatus.active else "В стоп-листе"
    text = (
        f"<b>Продукт #{product.id}</b>\n"
        f"Название: {product.name}\n"
        f"Цена: <b>{int(product.price)}₽</b>\n"
        f"Доступность: {status_text}\n"
        f"Компоненты: {components}\n"
        f"Фото: {'есть' if product.image_url else 'нет'}\n\n"
        f"{product.description or ''}"
    )
    await message.edit_text(text, parse_mode="HTML", reply_markup=edit_product_kb(product.id))


async def _show_edit_component(message: Message, component_id: int):
    async with async_session() as session:
        component = await component_repo.get(session, component_id)
    if not component:
        await message.edit_text("Компонент не найден.", reply_markup=edit_root_kb())
        return

    text = (
        f"<b>Компонент #{component.id}</b>\n"
        f"Название: {component.name}\n"
        f"Тип: {component.type.value}\n"
        f"Надбавка: <b>{int(component.price_delta or 0)}₽</b>\n"
        f"Активен: {'да' if component.is_active else 'нет'}\n"
        f"Фото: {'есть' if component.image_url else 'нет'}"
    )
    await message.edit_text(text, parse_mode="HTML", reply_markup=edit_component_kb(component.id))


@router.callback_query(F.data == "adm:edit")
async def edit_catalog_root(cb: CallbackQuery, state: FSMContext):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    await state.clear()
    await cb.message.edit_text("Редактирование каталога", reply_markup=edit_root_kb())


@router.callback_query(F.data == "adm:edit:products")
async def edit_products(cb: CallbackQuery):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    async with async_session() as session:
        products = await product_repo.list_all(session)
    await cb.message.edit_text("Выберите продукт:", reply_markup=edit_products_kb(products[:40]))


@router.callback_query(F.data.startswith("adm:edit:product:"))
async def edit_product_card(cb: CallbackQuery):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    product_id = int(cb.data.split(":")[3])
    await _show_edit_product(cb.message, product_id)


@router.callback_query(F.data.startswith("adm:edit:product_field:"))
async def edit_product_field(cb: CallbackQuery, state: FSMContext):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    _, _, _, product_id_raw, field = cb.data.split(":")
    product_id = int(product_id_raw)

    if field == "image":
        await state.set_state(AdminEditFSM.product_image)
        await state.update_data(edit_product_id=product_id)
        await cb.message.answer("Отправьте новое фото продукта.")
        return

    if field == "components":
        await state.set_state(AdminEditFSM.product_components)
        await state.update_data(
            edit_product_id=product_id,
            edit_component_ids=[],
            edit_component_step=0,
        )
        await _show_edit_product_component_pick(cb.message, state)
        return

    await state.set_state(AdminEditFSM.product_field)
    await state.update_data(edit_product_id=product_id, edit_product_field=field)
    labels = {"name": "название", "description": "описание", "price": "цену"}
    await cb.message.answer(f"Введите новое {labels.get(field, 'значение')}:")


@router.message(AdminEditFSM.product_image, F.photo)
async def edit_product_photo(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return
    data = await state.get_data()
    product_id = data["edit_product_id"]
    async with async_session() as session:
        await product_repo.update_product(session, product_id, image_url=message.photo[-1].file_id)
    await state.clear()
    await message.answer("Фото продукта обновлено.")


@router.message(AdminEditFSM.product_image, F.document)
async def edit_product_image_document(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return
    document = message.document
    if not document.mime_type or not document.mime_type.startswith("image/"):
        await message.answer("Нужно отправить изображение.")
        return
    data = await state.get_data()
    product_id = data["edit_product_id"]
    async with async_session() as session:
        await product_repo.update_product(session, product_id, image_url=document.file_id)
    await state.clear()
    await message.answer("Фото продукта обновлено.")


@router.message(AdminEditFSM.product_field, F.text)
async def edit_product_text_field(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return
    data = await state.get_data()
    product_id = data["edit_product_id"]
    field = data["edit_product_field"]
    value = message.text.strip()
    if field == "price":
        value = _price_from_text(value)
        if value is None:
            await message.answer("Введите цену числом, например: 4500")
            return
    elif field == "name":
        value = value[:64]
    async with async_session() as session:
        await product_repo.update_product(session, product_id, **{field: value})
    await state.clear()
    await message.answer("Продукт обновлён.")


async def _show_edit_product_component_pick(message: Message, state: FSMContext):
    data = await state.get_data()
    step_index = data.get("edit_component_step", 0)
    if step_index >= len(catalog_service.CATALOG_STEPS):
        product_id = data["edit_product_id"]
        component_ids = data.get("edit_component_ids") or []
        async with async_session() as session:
            await product_repo.replace_product_components(session, product_id, component_ids)
        await state.clear()
        await message.answer("Компоненты продукта обновлены.")
        return

    step_key, component_type = catalog_service.CATALOG_STEPS[step_index]
    async with async_session() as session:
        components = await component_repo.list_by_type(session, component_type)
    title = catalog_service.CATALOG_TITLES[step_key].replace("Выберите", "Укажите")
    await message.answer(
        title,
        reply_markup=product_component_kb(components, allow_create=True, ctype=component_type.value),
    )


@router.callback_query(AdminEditFSM.product_components, F.data.startswith("adm:product:component:"))
async def edit_product_component_pick(cb: CallbackQuery, state: FSMContext):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    data = await state.get_data()
    component_ids = list(data.get("edit_component_ids") or [])
    raw = cb.data.split(":")[-1]
    if raw != "skip":
        component_id = int(raw)
        if component_id not in component_ids:
            component_ids.append(component_id)
    await state.update_data(
        edit_component_ids=component_ids,
        edit_component_step=data.get("edit_component_step", 0) + 1,
    )
    await _show_edit_product_component_pick(cb.message, state)


@router.callback_query(F.data == "adm:edit:components")
async def edit_component_types(cb: CallbackQuery):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_text("Выберите тип компонентов:", reply_markup=edit_component_types_kb())


@router.callback_query(F.data.startswith("adm:edit:components:"))
async def edit_components_by_type(cb: CallbackQuery):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    component_type = _component_type_from_raw(cb.data.split(":")[3])
    async with async_session() as session:
        components = await component_repo.list_by_type(session, component_type)
    await cb.message.edit_text("Выберите компонент:", reply_markup=edit_components_kb(components))


@router.callback_query(F.data.startswith("adm:edit:component:"))
async def edit_component_card(cb: CallbackQuery):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    component_id = int(cb.data.split(":")[3])
    await _show_edit_component(cb.message, component_id)


@router.callback_query(F.data.startswith("adm:edit:component_field:"))
async def edit_component_field(cb: CallbackQuery, state: FSMContext):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    _, _, _, component_id_raw, field = cb.data.split(":")
    component_id = int(component_id_raw)
    if field == "image":
        await state.set_state(AdminEditFSM.component_image)
        await state.update_data(edit_component_id=component_id)
        await cb.message.answer("Отправьте новое фото компонента.")
        return
    await state.set_state(AdminEditFSM.component_field)
    await state.update_data(edit_component_id=component_id, edit_component_field=field)
    await cb.message.answer("Введите новое значение:")


@router.message(AdminEditFSM.component_image, F.photo)
async def edit_component_photo(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return
    data = await state.get_data()
    async with async_session() as session:
        await component_repo.update_component(session, data["edit_component_id"], image_url=message.photo[-1].file_id)
    await state.clear()
    await message.answer("Фото компонента обновлено.")


@router.message(AdminEditFSM.component_field, F.text)
async def edit_component_text_field(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return
    data = await state.get_data()
    field = data["edit_component_field"]
    value = message.text.strip()
    if field == "name":
        value = value[:64]
    if field == "price_delta":
        value = _price_from_text(value) or Decimal("0")
    async with async_session() as session:
        await component_repo.update_component(session, data["edit_component_id"], **{field: value})
    await state.clear()
    await message.answer("Компонент обновлён.")


@router.message(AdminEditFSM.component_image, F.document)
async def edit_component_image_document(message: Message, state: FSMContext):
    if not _is_admin_user(message.from_user.id):
        return
    document = message.document
    if not document.mime_type or not document.mime_type.startswith("image/"):
        await message.answer("Нужно отправить изображение.")
        return
    data = await state.get_data()
    async with async_session() as session:
        await component_repo.update_component(session, data["edit_component_id"], image_url=document.file_id)
    await state.clear()
    await message.answer("Фото компонента обновлено.")


@router.callback_query(F.data.startswith("adm:edit:component_toggle:"))
async def edit_component_toggle(cb: CallbackQuery):
    if not _is_admin_user(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    component_id = int(cb.data.split(":")[3])
    async with async_session() as session:
        component = await component_repo.get(session, component_id)
        if component:
            await component_repo.update_component(session, component_id, is_active=not component.is_active)
    await _show_edit_component(cb.message, component_id)
