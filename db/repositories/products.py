from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Product, ProductStatus


async def list_templates(session: AsyncSession):
    res = await session.execute(
        select(Product)
        .where(Product.is_template.is_(True), Product.status == ProductStatus.active)
        .order_by(Product.id)
    )
    return res.scalars().all()


async def get(session: AsyncSession, product_id: int) -> Product | None:
    return await session.get(Product, product_id)