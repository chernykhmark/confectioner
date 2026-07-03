from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Review


async def create_review(
    session: AsyncSession,
    *,
    order_id: int,
    user_id: int,
    text: str,
) -> Review:
    review = Review(order_id=order_id, user_id=user_id, text=text[:1000])
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review
