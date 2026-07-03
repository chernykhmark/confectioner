from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from db.base import async_session
from db.models import OrderStatus
from db.repositories import orders as order_repo
from db.repositories import reviews as review_repo
from db.repositories import users as users_repo
from keyboards.user import main_menu, review_cancel_kb, review_image_kb
from states.review import ReviewFSM

router = Router()


async def _send_review_to_admin(bot, *, order, user, text: str, image: dict | None):
    review_text = text
    if image and len(review_text) > 700:
        review_text = f"{review_text[:697]}..."

    admin_text = (
        f"<b>Новый отзыв по заказу #{order.id}</b>\n"
        f"Клиент: {escape(user.first_name or '')} @{escape(user.username or '—')} "
        f"(<code>{user.telegram_id}</code>)\n\n"
        f"{escape(review_text)}"
    )

    if image:
        if image["type"] == "photo":
            await bot.send_photo(
                settings.admin_telegram_id,
                image["file_id"],
                caption=admin_text,
                parse_mode="HTML",
            )
        else:
            await bot.send_document(
                settings.admin_telegram_id,
                image["file_id"],
                caption=admin_text,
                parse_mode="HTML",
            )
        return

    await bot.send_message(settings.admin_telegram_id, admin_text, parse_mode="HTML")


async def _finish_review(message: Message, state: FSMContext, tg_user, image: dict | None = None):
    data = await state.get_data()
    order_id = data.get("order_id")
    text = data.get("review_text")

    async with async_session() as session:
        user = await users_repo.get_or_create_user(session, tg_user)
        order = await order_repo.get_with_relations(session, order_id)

        if not order or order.user_id != user.id or order.status != OrderStatus.closed:
            await state.clear()
            await message.answer("Не получилось сохранить отзыв: заказ не найден или ещё не закрыт.")
            return

        await review_repo.create_review(
            session,
            order_id=order.id,
            user_id=user.id,
            text=text,
        )

    await _send_review_to_admin(message.bot, order=order, user=user, text=text, image=image)
    await state.clear()
    await message.answer("Спасибо! Отзыв отправлен кондитеру.", reply_markup=main_menu())


@router.callback_query(F.data.startswith("review:start:"))
async def start_review(cb: CallbackQuery, state: FSMContext):
    order_id = int(cb.data.split(":")[2])

    async with async_session() as session:
        user = await users_repo.get_or_create_user(session, cb.from_user)
        order = await order_repo.get_with_relations(session, order_id)

    if not order or order.user_id != user.id:
        await cb.answer("Заказ не найден", show_alert=True)
        return
    if order.status != OrderStatus.closed:
        await cb.answer("Отзыв можно оставить после закрытия заказа", show_alert=True)
        return

    await cb.answer()
    await state.clear()
    await state.set_state(ReviewFSM.text)
    await state.update_data(order_id=order_id)
    await cb.message.answer(
        f"Напишите отзыв по заказу #{order_id} одним сообщением:",
        reply_markup=review_cancel_kb(),
    )


@router.message(ReviewFSM.text, F.text)
async def input_review_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("Отзыв не должен быть пустым.")
        return

    await state.update_data(review_text=text[:1000])
    await state.set_state(ReviewFSM.image)
    await message.answer(
        "Можно прикрепить фото к отзыву или пропустить этот шаг.",
        reply_markup=review_image_kb(),
    )


@router.message(ReviewFSM.text)
async def invalid_review_text(message: Message):
    await message.answer("Пожалуйста, отправьте отзыв текстом.")


@router.callback_query(ReviewFSM.image, F.data == "review:skip_image")
async def skip_review_image(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await _finish_review(cb.message, state, cb.from_user)


@router.message(ReviewFSM.image, F.photo)
async def review_photo(message: Message, state: FSMContext):
    image = {"type": "photo", "file_id": message.photo[-1].file_id}
    await _finish_review(message, state, message.from_user, image=image)


@router.message(ReviewFSM.image, F.document)
async def review_document(message: Message, state: FSMContext):
    document = message.document
    if not document.mime_type or not document.mime_type.startswith("image/"):
        await message.answer("Нужна картинка. Отправьте фото или нажмите «Пропустить фото».")
        return

    image = {"type": "document", "file_id": document.file_id}
    await _finish_review(message, state, message.from_user, image=image)


@router.message(ReviewFSM.image)
async def invalid_review_image(message: Message):
    await message.answer("Отправьте фото или нажмите «Пропустить фото».", reply_markup=review_image_kb())


@router.callback_query(F.data == "review:cancel")
async def cancel_review(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer("Отзыв отменён.", reply_markup=main_menu())
