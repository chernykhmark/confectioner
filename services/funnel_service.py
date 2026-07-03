import time
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import ComponentType
from db.repositories import components as comp_repo

# порядок шагов воронки и соответствие ключам FSM-data
STEP_TYPES: list[tuple[str, ComponentType]] = [
    ("occasion", ComponentType.occasion),
    ("persons", ComponentType.persons),
    ("shape", ComponentType.shape),
    ("decoration", ComponentType.decor),
]

STEP_TITLES = {
    "occasion": "🎉 Выберите повод:",
    "persons": "👥 Сколько персон?",
    "shape": "⬛ Выберите форму:",
    "decoration": "🎨 Выберите оформление:",
}

_CACHE_TTL_SECONDS = 15
_components_cache: dict[ComponentType, tuple[float, list]] = {}


async def components_for_step(session: AsyncSession, step_type: ComponentType):
    now = time.monotonic()
    cached = _components_cache.get(step_type)
    if cached and cached[0] > now:
        return cached[1]

    components = await comp_repo.list_by_type(session, step_type)
    _components_cache[step_type] = (now + _CACHE_TTL_SECONDS, components)
    return components


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


async def calculate_weight_kg(session: AsyncSession, selected_ids: list[int]) -> Decimal | None:
    comps = await comp_repo.get_many(session, selected_ids)
    for component in comps:
        if component.type == ComponentType.persons and component.weight_grams:
            return (component.weight_grams / Decimal(1000)).quantize(Decimal("0.1"))
    return None
