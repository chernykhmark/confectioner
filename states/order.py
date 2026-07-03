from aiogram.fsm.state import State, StatesGroup


class OrderFSM(StatesGroup):
    choosing_template = State()
    template_date = State()   # ← новое
    catalog = State()
    budget = State()
    occasion = State()
    persons = State()
    shape = State()
    filling = State()
    decoration = State()
    date_wishes = State()
    delivery_type = State()
    delivery_address = State()
    delivery_time = State()
    confirming = State()
    account = State()
    repeat_date = State()
    edit_date = State()
    edit_comment = State()
