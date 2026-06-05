import hashlib
import random
import string
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Order, OrderItem
from app.schemas import BUNDLE_PRICES, PRODUCT_CATALOG, UPSELL_PRICE, OrderIn


def _generate_order_number() -> str:
    """Generate NSM-YYYYMMDD-XXXX style order number."""
    date_part = datetime.utcnow().strftime("%Y%m%d")
    rand_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"NSM-{date_part}-{rand_part}"


def _normalize_phone(phone: str) -> dict[str, str]:
    """Return local, E.164, digits, and SHA256 hash."""
    local = phone  # already validated as 05XXXXXXXX
    e164 = "+966" + phone[1:]  # replace leading 0 with +966
    digits = "966" + phone[1:]
    hashed = hashlib.sha256(phone.lower().encode()).hexdigest()
    return {"local": local, "e164": e164, "digits": digits, "hash": hashed}


def _compute_total(order_in: OrderIn) -> tuple[int, list[dict]]:
    """
    Compute server-side validated total.
    Returns (total_sar, enriched_items).
    """
    regular_items = [i for i in order_in.items if not i.is_upsell]
    upsell_items = [i for i in order_in.items if i.is_upsell]

    total_main_qty = sum(i.quantity for i in regular_items)
    bundle_price = BUNDLE_PRICES[total_main_qty]

    enriched: list[dict] = []

    # Distribute bundle price proportionally across SKUs
    # For simplicity when multiple SKUs: charge full bundle price on first item,
    # zero on additional SKUs (edge-case; standard flow is one SKU per order).
    remaining = bundle_price
    for idx, item in enumerate(regular_items):
        unit_price = remaining if idx == 0 else 0
        enriched.append(
            {
                "sku": item.sku,
                "product_name": PRODUCT_CATALOG[item.sku]["name"],
                "quantity": item.quantity,
                "unit_price_sar": unit_price,
                "line_total_sar": unit_price,
                "is_upsell": False,
            }
        )
        remaining = 0

    total = bundle_price

    for item in upsell_items:
        enriched.append(
            {
                "sku": item.sku,
                "product_name": PRODUCT_CATALOG[item.sku]["name"],
                "quantity": 1,
                "unit_price_sar": UPSELL_PRICE,
                "line_total_sar": UPSELL_PRICE,
                "is_upsell": True,
            }
        )
        total += UPSELL_PRICE

    return total, enriched


def create_order(db: Session, order_in: OrderIn) -> Order:
    phone_data = _normalize_phone(order_in.phone)
    total_sar, enriched_items = _compute_total(order_in)

    order_number = _generate_order_number()

    order = Order(
        order_number=order_number,
        name=order_in.name,
        phone_local=phone_data["local"],
        phone_e164=phone_data["e164"],
        phone_digits=phone_data["digits"],
        phone_hash=phone_data["hash"],
        total_sar=total_sar,
        status="pending",
        browser_event_id=order_in.browser_event_id,
    )
    db.add(order)
    db.flush()

    for item_data in enriched_items:
        db.add(OrderItem(order_id=order.id, **item_data))

    db.commit()
    db.refresh(order)
    return order


def get_order_by_number(db: Session, order_number: str) -> "Optional[Order]":
    return db.query(Order).filter(Order.order_number == order_number).first()
