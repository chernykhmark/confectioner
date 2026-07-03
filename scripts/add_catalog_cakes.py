import asyncio
import os
import sys
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.base import async_session
from db.models import Component, ComponentType, Product, ProductComponent, ProductStatus


BASE_COMPONENTS = {
    ComponentType.occasion: ["Без повода", "День рождения"],
    ComponentType.persons: ["6-8 персон", "10-12 персон"],
    ComponentType.shape: ["Круглый"],
    ComponentType.decor: [
        "Шоколадный декор",
        "Ягодный декор",
        "Фруктовый декор",
        "Карамельный декор",
        "Ореховый декор",
        "Домашний декор",
        "Минимализм",
    ],
}

CAKES = [
    {
        "name": "Шоколад-вишня",
        "price": 4500,
        "filling": "Шоколад-вишня",
        "decor": "Шоколадный декор",
        "description": (
            "Слои: шоколадный бисквит, вишневая прослойка с кусочками ягод, "
            "шоколадный чизкейк, крем чиз. Декор: сочащийся вишневый джем, "
            "горький шоколад и коктейльная вишня с хвостиком."
        ),
    },
    {
        "name": "Сникерс",
        "price": 4700,
        "filling": "Сникерс",
        "decor": "Ореховый декор",
        "description": (
            "Слои: шоколадный бисквит, тягучая карамель с целыми орешками, "
            "крем на бельгийском шоколаде, шоколадный крем чиз. Декор: "
            "шоколадные подтеки, соленый арахис и попкорн."
        ),
    },
    {
        "name": "Тропический шоколад",
        "price": 4600,
        "filling": "Тропический шоколад",
        "decor": "Фруктовый декор",
        "description": (
            "Слои: шоколадный бисквит, яркое мангово-тропическое желе с "
            "вкраплениями, объемный крем на бельгийском шоколаде. Декор: "
            "кусочки манго и карамбола, глянец и минимализм."
        ),
    },
    {
        "name": "Красная смородина в шоколаде",
        "price": 4500,
        "filling": "Красная смородина в шоколаде",
        "decor": "Ягодный декор",
        "description": (
            "Слои: шоколадный бисквит, рубиновое желе красной смородины, "
            "белый мусс на белом шоколаде, крем чиз. Декор: алые ягоды "
            "и листочек мяты на белом креме."
        ),
    },
    {
        "name": "Красный бархат",
        "price": 4300,
        "filling": "Красный бархат",
        "decor": "Ягодный декор",
        "description": (
            "Слои: ярко-красный бисквит с рыхлым срезом и малиновый конфитюр. "
            "Декор: белый крем-чиз, крошка красного бисквита на боках, "
            "контрастный красно-белый разрез."
        ),
    },
    {
        "name": "Фисташка-малина",
        "price": 4800,
        "filling": "Фисташка-малина",
        "decor": "Ягодный декор",
        "description": (
            "Слои: зеленый фисташковый бисквит, малиновый конфитюр, "
            "нежный фисташковый крем. Декор: фисташковые лепестки, "
            "малина и фактурный ягодный разлом."
        ),
    },
    {
        "name": "Клубничное мохито",
        "price": 4400,
        "filling": "Клубничное мохито",
        "decor": "Фруктовый декор",
        "description": (
            "Слои: ванильный бисквит с цедрой лайма, клубничная прослойка, "
            "крем с цедрой, белый крем-чиз. Декор: клубника, лайм, мята "
            "и летний свежий срез."
        ),
    },
    {
        "name": "Хрустящая карамель",
        "price": 4700,
        "filling": "Хрустящая карамель",
        "decor": "Карамельный декор",
        "description": (
            "Слои: карамельный бисквит, хрустящий слой с арахисом, мягкая "
            "карамель, темный шоколадный мусс, карамельный крем. Декор: "
            "карамельные орехи и фактурный разлом."
        ),
    },
    {
        "name": "Молочная девочка",
        "price": 4200,
        "filling": "Молочная девочка",
        "decor": "Домашний декор",
        "description": (
            "Слои: тонкие коржи на сгущенке, сливочная пропитка, белоснежный "
            "творожный крем и много свежих ягод. Домашний сочный срез."
        ),
    },
    {
        "name": "Ваниль-ягоды",
        "price": 4200,
        "filling": "Ваниль-ягоды",
        "decor": "Ягодный декор",
        "description": "Светло-желтый бисквит, белый крем, голубика и малина.",
    },
    {
        "name": "Экзотик",
        "price": 4400,
        "filling": "Экзотик",
        "decor": "Фруктовый декор",
        "description": "Белый бисквит, крем-чиз с кусочками манго и киви в разрезе.",
    },
    {
        "name": "Пряная вишня",
        "price": 4300,
        "filling": "Пряная вишня",
        "decor": "Ягодный декор",
        "description": "Темный бисквит с пряными вкраплениями и тягучая вишня.",
    },
    {
        "name": "Фундук-молочный шоколад",
        "price": 4700,
        "filling": "Фундук-молочный шоколад",
        "decor": "Ореховый декор",
        "description": "Ореховый бисквит, янтарная карамель и молочный шоколад.",
    },
    {
        "name": "Шоколад-черная смородина",
        "price": 4500,
        "filling": "Шоколад-черная смородина",
        "decor": "Ягодный декор",
        "description": "Темный бисквит и чернично-фиолетовый крем черной смородины.",
    },
    {
        "name": "Клубника со сливками",
        "price": 4300,
        "filling": "Клубника со сливками",
        "decor": "Ягодный декор",
        "description": "Ангельский белый бисквит, воздушный мусс и алая клубничная полоса.",
    },
    {
        "name": "Вишня со сливками",
        "price": 4300,
        "filling": "Вишня со сливками",
        "decor": "Ягодный декор",
        "description": "Миндальный золотистый бисквит, сливочный мусс и розовый вишневый мусс.",
    },
    {
        "name": "Карамельная девочка",
        "price": 4400,
        "filling": "Карамельная девочка",
        "decor": "Карамельный декор",
        "description": "Бисквит и прослойка с вареной сгущенкой, плюс темная мягкая карамель.",
    },
]


async def get_or_create_component(session, component_type, name, sort_order=100):
    res = await session.execute(
        select(Component).where(Component.type == component_type, Component.name == name)
    )
    component = res.scalar_one_or_none()
    if component:
        return component

    component = Component(
        type=component_type,
        name=name,
        price_delta=Decimal("0"),
        sort_order=sort_order,
        is_active=True,
    )
    session.add(component)
    await session.flush()
    return component


async def upsert_product(session, cake, components):
    res = await session.execute(
        select(Product)
        .options(selectinload(Product.components))
        .where(Product.name == cake["name"])
    )
    product = res.scalar_one_or_none()
    if product:
        product.description = cake["description"]
        product.price = Decimal(cake["price"])
        product.is_template = True
        product.status = ProductStatus.active
    else:
        product = Product(
            name=cake["name"],
            description=cake["description"],
            price=Decimal(cake["price"]),
            is_template=True,
            status=ProductStatus.active,
        )
        session.add(product)
        await session.flush()

    await session.execute(delete(ProductComponent).where(ProductComponent.product_id == product.id))

    for component in components:
        session.add(ProductComponent(product_id=product.id, component_id=component.id))


async def main():
    async with async_session() as session:
        component_by_name = {}

        for component_type, names in BASE_COMPONENTS.items():
            for index, name in enumerate(names):
                component_by_name[name] = await get_or_create_component(
                    session, component_type, name, index
                )

        for index, cake in enumerate(CAKES):
            component_by_name[cake["filling"]] = await get_or_create_component(
                session, ComponentType.filling, cake["filling"], index + 10
            )

        for cake in CAKES:
            components = [
                component_by_name["Без повода"],
                component_by_name["6-8 персон"],
                component_by_name["Круглый"],
                component_by_name[cake["filling"]],
                component_by_name[cake["decor"]],
            ]
            await upsert_product(session, cake, components)

        await session.commit()
        print(f"Добавлено/обновлено тортов: {len(CAKES)}")


if __name__ == "__main__":
    asyncio.run(main())
