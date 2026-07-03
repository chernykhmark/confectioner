import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.base import async_session
from db.models import (
    Component, Product, ProductComponent,
    ComponentType, ProductStatus,
)

# type: [(name, weight_grams, price_delta)]
COMPONENTS = {
    ComponentType.occasion: [
        ("День рождения", None, 0), ("Свадьба", None, 0), ("Без повода", None, 0),
    ],
    ComponentType.persons: [
        ("6-8 персон", 1000, 0), ("10-12 персон", 1600, 800), ("15+ персон", 2500, 1800),
    ],
    ComponentType.shape: [
        ("Круглый", None, 0), ("Квадратный", None, 200), ("Цифра", None, 700),
    ],
    ComponentType.filling: [
        ("Красный бархат", None, 300), ("Шоколадный", None, 200), ("Ванильный", None, 0),
    ],
    ComponentType.decor: [
        ("Классика крем", None, 0), ("Ягоды сверху", None, 500), ("Мастика", None, 900),
    ],
}

TEMPLATES = [
    {
        "name": "Классический ДР",
        "description": "Круглый, красный бархат, крем",
        "price": 3500, "is_template": True,
        "components": ["День рождения", "10-12 персон", "Круглый",
                       "Красный бархат", "Классика крем"],
    },
    {
        "name": "Свадебный ярус",
        "description": "Квадратный, ванильный, мастика",
        "price": 7000, "is_template": True,
        "components": ["Свадьба", "15+ персон", "Квадратный",
                       "Ванильный", "Мастика"],
    },
    {
        "name": "Шоколадная цифра",
        "description": "Цифра, шоколад, ягоды",
        "price": 4200, "is_template": True,
        "components": ["Без повода", "6-8 персон", "Цифра",
                       "Шоколадный", "Ягоды сверху"],
    },
]


async def seed():
    async with async_session() as s:
        name_to_comp = {}
        for ctype, items in COMPONENTS.items():
            for order, (name, weight, delta) in enumerate(items):
                c = Component(
                    type=ctype,
                    name=name,
                    weight_grams=weight,
                    price_delta=delta,
                    sort_order=order,
                )
                s.add(c)
                await s.flush()
                name_to_comp[name] = c.id

        for t in TEMPLATES:
            p = Product(
                name=t["name"],
                description=t["description"],
                price=t["price"],
                is_template=t["is_template"],
                status=ProductStatus.active,
            )
            s.add(p)
            await s.flush()
            for cname in t["components"]:
                s.add(ProductComponent(
                    product_id=p.id,
                    component_id=name_to_comp[cname],
                ))
        await s.commit()
        print("✅ Seed завершён")


if __name__ == "__main__":
    asyncio.run(seed())