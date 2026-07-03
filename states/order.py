from aiogram.fsm.state import State, StatesGroup


class OrderFSM(StatesGroup):
    choosing_template = State()
    template_date = State()   # ← новое
    occasion = State()
    persons = State()
    shape = State()
    filling = State()
    decoration = State()
    date_wishes = State()
    confirming = State()