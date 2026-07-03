from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from config import settings
from db.base import async_session
from db.models import Component, Product

router = Router()


def _is_admin(message: Message) -> bool:
    return message.from_user and message.from_user.id == settings.admin_telegram_id


def _parse_target(caption: str | None) -> tuple[str, int] | None:
    if not caption:
        return None

    normalized = caption.strip().lower().replace(":", " ")
    parts = normalized.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return None

    aliases = {
        "product": "product",
        "template": "product",
        "tpl": "product",
        "p": "product",
        "торт": "product",
        "шаблон": "product",
        "component": "component",
        "comp": "component",
        "c": "component",
        "компонент": "component",
    }
    target = aliases.get(parts[0])
    if not target:
        return None
    return target, int(parts[1])


async def _save_image_if_targeted(message: Message, file_id: str) -> bool:
    target = _parse_target(message.caption)
    if not target:
        return False

    kind, item_id = target
    model = Product if kind == "product" else Component
    label = "торта" if kind == "product" else "компонента"

    async with async_session() as session:
        item = await session.get(model, item_id)
        if not item:
            await message.answer(f"Не нашёл {label} с ID {item_id}.")
            return True

        item.image_url = file_id
        await session.commit()

    await message.answer(
        f"✅ Изображение сохранено для {label} #{item_id}.\n\n"
        "file_id:\n"
        f"<code>{file_id}</code>",
        parse_mode="HTML",
    )
    return True


@router.message(Command("image_id"))
async def image_id_help(message: Message):
    if not _is_admin(message):
        return

    await message.answer(
        "📸 Отправьте сюда фото торта или картинки для варианта конструктора.\n\n"
        "Без подписи я верну <code>file_id</code>.\n"
        "С подписью сразу сохраню картинку в базу:\n"
        "<code>product 3</code> — для готового торта #3\n"
        "<code>component 7</code> — для компонента #7",
        parse_mode="HTML",
    )


@router.message(F.photo)
async def admin_photo_file_id(message: Message):
    if not _is_admin(message):
        return

    photo = message.photo[-1]
    if await _save_image_if_targeted(message, photo.file_id):
        return

    await message.answer(
        "✅ Фото принято.\n\n"
        "file_id:\n"
        f"<code>{photo.file_id}</code>\n\n"
        "Вставьте это значение в <code>products.image_url</code> "
        "или <code>components.image_url</code>.",
        parse_mode="HTML",
    )


@router.message(F.document)
async def admin_image_document_file_id(message: Message):
    if not _is_admin(message):
        return

    document = message.document
    if not document.mime_type or not document.mime_type.startswith("image/"):
        return

    if await _save_image_if_targeted(message, document.file_id):
        return

    await message.answer(
        "✅ Картинка-файл принята.\n\n"
        "file_id:\n"
        f"<code>{document.file_id}</code>\n\n"
        "Вставьте это значение в <code>products.image_url</code> "
        "или <code>components.image_url</code>.",
        parse_mode="HTML",
    )
