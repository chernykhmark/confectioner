import time

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Product, ProductComponent, ProductStatus

_CACHE_TTL_SECONDS = 15
_templates_cache: tuple[float, list[Product]] | None = None


async def list_templates(session: AsyncSession):
    global _templates_cache

    now = time.monotonic()
    if _templates_cache and _templates_cache[0] > now:
        return _templates_cache[1]

    res = await session.execute(
        select(Product)
        .where(Product.is_template.is_(True), Product.status == ProductStatus.active)
        .order_by(Product.id)
    )
    templates = res.scalars().all()
    _templates_cache = (now + _CACHE_TTL_SECONDS, templates)
    return templates


def invalidate_templates_cache():
    global _templates_cache
    _templates_cache = None


async def get(session: AsyncSession, product_id: int) -> Product | None:
    return await session.get(Product, product_id)


async def get_with_components(session: AsyncSession, product_id: int) -> Product | None:
    res = await session.execute(
        select(Product)
        .options(selectinload(Product.components).selectinload(ProductComponent.component))
        .where(Product.id == product_id)
    )
    return res.scalar_one_or_none()


async def list_catalog_products(session: AsyncSession) -> list[Product]:
    res = await session.execute(
        select(Product)
        .options(selectinload(Product.components).selectinload(ProductComponent.component))
        .where(Product.status == ProductStatus.active)
        .order_by(Product.id)
    )
    return [product for product in res.scalars().all() if product.components]


async def list_all(session: AsyncSession) -> list[Product]:
    res = await session.execute(select(Product).order_by(Product.id.desc()))
    return res.scalars().all()


async def create_template_product(
    session: AsyncSession,
    *,
    name: str,
    description: str | None,
    price,
    image_url: str | None,
    component_ids: list[int] | None = None,
) -> Product:
    product = Product(
        name=name[:64],
        description=description if description else None,
        price=price,
        image_url=image_url,
        is_template=True,
        status=ProductStatus.active,
    )
    session.add(product)
    await session.flush()
    for component_id in component_ids or []:
        session.add(ProductComponent(product_id=product.id, component_id=component_id))
    await session.commit()
    await session.refresh(product)
    invalidate_templates_cache()
    return product


async def update_product(session: AsyncSession, product_id: int, **values) -> Product | None:
    product = await session.get(Product, product_id)
    if not product:
        return None
    for key, value in values.items():
        setattr(product, key, value)
    await session.commit()
    await session.refresh(product)
    invalidate_templates_cache()
    return product


async def replace_product_components(
    session: AsyncSession,
    product_id: int,
    component_ids: list[int],
) -> Product | None:
    product = await get_with_components(session, product_id)
    if not product:
        return None

    await session.execute(delete(ProductComponent).where(ProductComponent.product_id == product.id))
    for component_id in component_ids:
        session.add(ProductComponent(product_id=product.id, component_id=component_id))
    await session.commit()
    invalidate_templates_cache()
    return await get_with_components(session, product_id)
