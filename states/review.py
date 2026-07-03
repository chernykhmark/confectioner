from aiogram.fsm.state import State, StatesGroup


class ReviewFSM(StatesGroup):
    text = State()
    image = State()
