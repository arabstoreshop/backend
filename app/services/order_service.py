import hashlib
import random
import re
import string
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Order, OrderItem
from app.schemas import BEAUTY_BUNDLE_PRICES, BEAUTY_SKUS, BUNDLE_PRICES, PRODUCT_CATALOG, UPSELL_PRICE, OrderIn


def _generate_order_number() -> str:
    """Generate NSM-YYYYMMDD-XXXX style order number."""
    date_part = datetime.utcnow().strftime("%Y%m%d")
    rand_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"NSM-{date_part}-{rand_part}"


def _normalize_phone(phone: str) -> dict[str, str]:
    """Return local, E.164, digits, and SHA256 hash. Accepts any country for tests."""
    local = phone.strip()[:20]
    digits = re.sub(r"\D", "", local)
    if digits.startswith("00"):
        digits = digits[2:]
    if local.startswith("+"):
        e164 = "+" + digits
        hashed_digits = digits
    elif digits.startswith("0") and len(digits) == 10:
        e164 = "+966" + digits[1:]
        hashed_digits = "966" + digits[1:]
    else:
        e164 = "+" + digits
        hashed_digits = digits
    hashed = hashlib.sha256(e164.encode()).hexdigest()
    return {"local": local, "e164": e164[:20], "digits": hashed_digits[:20], "hash": hashed}


def _bundle_table(sku: str) -> dict[int, int]:
    return BEAUTY_BUNDLE_PRICES if sku in BEAUTY_SKUS else BUNDLE_PRICES


def _compute_total(order_in: OrderIn) -> tuple[int, list[dict]]:
    """Each SKU is priced from its own 1/2/3 pack table."""
    regular_items = [i for i in order_in.items if not i.is_upsell]
    upsell_items = [i for i in order_in.items if i.is_upsell]
    enriched: list[dict] = []
    total = 0

    for item in regular_items:
        price = _bundle_table(item.sku)[item.quantity]
        enriched.append(
            {
                "sku": item.sku,
                "product_name": PRODUCT_CATALOG.get(item.sku, {}).get("name", item.sku),
                "quantity": item.quantity,
                "unit_price_sar": price,
                "line_total_sar": price,
                "is_upsell": False,
            }
        )
        total += price

    for item in upsell_items:
        enriched.append(
            {
                "sku": item.sku,
                "product_name": PRODUCT_CATALOG.get(item.sku, {}).get("name", item.sku),
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
        city=(order_in.city or "").strip() or None,
        address=(order_in.address or "").strip() or None,
        notes=(order_in.notes or "").strip() or None,
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
