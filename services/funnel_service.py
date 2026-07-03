from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import ComponentType
from db.repositories import components as comp_repo

# порядок шагов воронки и соответствие ключам FSM-data
STEP_TYPES: list[tuple[str, ComponentType]] = [
    ("occasion", ComponentType.occasion),
    ("persons", ComponentType.persons),
    ("shape", ComponentType.shape),
    ("filling", ComponentType.filling),
    ("decoration", ComponentType.decor),
]

STEP_TITLES = {
    "occasion": "🎉 Выберите повод:",
    "persons": "👥 Сколько персон?",
    "shape": "⬛ Выберите форму:",
    "filling": "🍫 Выберите начинку:",
    "decoration": "🎨 Выберите оформление:",
}


async def components_for_step(session: AsyncSession, step_type: ComponentType):
    return await comp_repo.list_by_type(session, step_type)


async def calculate_price(session: AsyncSession, selected_ids: list[int],
                          base_price: Decimal) -> Decimal:
    comps = await comp_repo.get_many(session, selected_ids)
    total = base_price + sum((c.price_delta or Decimal(0)) for c in comps)
    return total


async def build_description(session: AsyncSession, selected_ids: list[int]) -> str:
    comps = await comp_repo.get_many(session, selected_ids)
    by_id = {c.id: c for c in comps}
    ordered = [by_id[i].name for i in selected_ids if i in by_id]
    return ", ".join(ordered)