from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from db.repositories import orders as order_repo, products as product_repo
from services import funnel_service
from db.models import OrderStatus


def _selected_ids_from_data(data: dict) -> list[int]:
    ids = []
    for key, _ in funnel_service.STEP_TYPES:
        value = data.get(f"sel_{key}")
        if isinstance(value, list):
            ids.extend(value)
        elif value:
            ids.append(value)
    return ids


def _parse_date(raw: str | None):
    if not raw:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return date.fromisoformat(raw) if fmt == "%Y-%m-%d" else \
                __import__("datetime").datetime.strptime(raw, fmt).date()
        except Exception:
            continue
    return None


async def create_custom_order(session: AsyncSession, user_id: int, data: dict):
    ids = _selected_ids_from_data(data)
    total = await funnel_service.calculate_price(session, ids, settings.base_price)
    desc = await funnel_service.build_description(session, ids)
    wishes = data.get("wishes")
    if wishes:
        desc = f"{desc} | Пожелания: {wishes}"
    if data.get("budget"):
        desc = f"{desc} | Бюджет: {data['budget']}"
    order = await order_repo.create_order(
        session,
        user_id=user_id,
        product_id=None,
        description=desc[:255],
        total_price=total,
        desired_date=_parse_date(data.get("desired_date")),
        result_image_url=None,
        component_ids=ids,
        delivery_type=data.get("delivery_type"),
        delivery_address=data.get("delivery_address"),
        delivery_comment=data.get("delivery_comment"),
        delivery_time_from=data.get("delivery_time_from"),
        delivery_time_to=data.get("delivery_time_to"),
        customer_comment=wishes,
    )
    return order


async def create_template_order(session: AsyncSession, user_id: int, product_id: int,
                                desired_date_raw: str | None = None, data: dict | None = None):
    payload = dict(data or {})
    if desired_date_raw is not None:
        payload["desired_date"] = desired_date_raw
    return await create_product_order(session, user_id, product_id, payload)


async def create_product_order(session: AsyncSession, user_id: int, product_id: int, data: dict):
    product = await product_repo.get_with_components(session, product_id)
    component_ids = [pc.component_id for pc in product.components] if product else []
    order = await order_repo.create_order(
        session,
        user_id=user_id,
        product_id=product.id,
        description=product.description,
        total_price=product.price,
        desired_date=_parse_date(data.get("desired_date")),
        result_image_url=product.image_url,
        component_ids=component_ids,
        delivery_type=data.get("delivery_type"),
        delivery_address=data.get("delivery_address"),
        delivery_comment=data.get("delivery_comment"),
        delivery_time_from=data.get("delivery_time_from"),
        delivery_time_to=data.get("delivery_time_to"),
        customer_comment=data.get("wishes"),
    )
    return order


async def create_repeat_order(session: AsyncSession, user_id: int, source_order_id: int, data: dict):
    source = await order_repo.get_with_relations(session, source_order_id)
    component_ids = [oc.component_id for oc in source.components] if source else []
    order = await order_repo.create_order(
        session,
        user_id=user_id,
        product_id=source.product_id,
        description=source.description,
        total_price=source.total_price,
        desired_date=_parse_date(data.get("desired_date")),
        result_image_url=source.result_image_url,
        component_ids=component_ids,
        delivery_type=data.get("delivery_type"),
        delivery_address=data.get("delivery_address"),
        delivery_comment=data.get("delivery_comment"),
        delivery_time_from=data.get("delivery_time_from"),
        delivery_time_to=data.get("delivery_time_to"),
        customer_comment=data.get("wishes") or source.customer_comment,
    )
    return order


async def change_status(session: AsyncSession, order_id: int, new_status: OrderStatus):
    return await order_repo.update_status(session, order_id, new_status)
