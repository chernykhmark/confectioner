from aiogram.fsm.state import State, StatesGroup


class AdminProductFSM(StatesGroup):
    image = State()
    name = State()
    description = State()
    price = State()
    ingredients = State()
    components = State()
    confirming = State()


class AdminEditFSM(StatesGroup):
    product_field = State()
    product_image = State()
    product_components = State()
    component_field = State()
    component_image = State()
