from aiogram import Bot
from aiogram.fsm.context import FSMContext


async def send_step(bot: Bot, chat_id: int, state: FSMContext, text: str, kb=None):
    data = await state.get_data()
    if mid := data.get("last_bot_message_id"):
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass
    msg = await bot.send_message(chat_id, text, reply_markup=kb)
    await state.update_data(last_bot_message_id=msg.message_id)
    return msg