from collections import Counter

from db.models import ComponentType
from services import funnel_service


CATALOG_STEPS: list[tuple[str, ComponentType]] = [
    ("shape", ComponentType.shape),
    ("filling", ComponentType.filling),
    ("decoration", ComponentType.decor),
    ("persons", ComponentType.persons),
    ("occasion", ComponentType.occasion),
]

CATALOG_TITLES = {
    "shape": "Выберите форму:",
    "filling": "Выберите изделие:",
    "decoration": "Выберите оформление:",
    "persons": "Выберите количество персон:",
    "occasion": "Выберите повод:",
}


def product_component_ids(product) -> set[int]:
    return {pc.component_id for pc in product.components}


def candidates_for(products, selected_ids: list[int]):
    selected = set(selected_ids)
    return [
        product for product in products
        if selected.issubset(product_component_ids(product))
    ]


def available_options(products, selected_ids: list[int], component_type: ComponentType):
    selected = set(selected_ids)
    counter = Counter()

    for product in candidates_for(products, selected_ids):
        component_ids = product_component_ids(product)
        for product_component in product.components:
            component = product_component.component
            if component.id in selected or component.type != component_type:
                continue
            if selected | {component.id} <= component_ids:
                counter[component] += 1

    return sorted(counter.items(), key=lambda item: (item[0].sort_order, item[0].id))


def next_step_key(selected_steps: dict) -> str | None:
    for step_key, _ in CATALOG_STEPS:
        if step_key not in selected_steps:
            return step_key
    return None


def selection_summary(product) -> str:
    by_type = {pc.component.type: pc.component.name for pc in product.components}
    lines = []
    labels = {
        ComponentType.shape: "Форма",
        ComponentType.filling: "Начинка",
        ComponentType.decor: "Оформление",
        ComponentType.persons: "Персон",
        ComponentType.occasion: "Повод",
    }
    for component_type, label in labels.items():
        if name := by_type.get(component_type):
            lines.append(f"{label}: {name}")
    return "\n".join(lines)


def selected_ids_from_data(data: dict) -> list[int]:
    ids = []
    for step_key, _ in CATALOG_STEPS:
        if component_id := data.get(f"cat_{step_key}"):
            ids.append(component_id)
    return ids


async def selected_description(session, selected_ids: list[int]) -> str:
    if not selected_ids:
        return "—"
    return await funnel_service.build_description(session, selected_ids)
