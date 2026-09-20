import logging

import httpx

from app.config import settings
from app.models import Order

logger = logging.getLogger(__name__)

SUKOON_SHEET_WEBHOOK = (
    "https://script.google.com/macros/s/"
    "AKfycbxTidbmqTr6dKV7lOEmlQBR81R_Sv-VF8AA7UerWzvJ0wWd8pT5QtyyA9NlOGU7WLE9YQ/exec"
)


async def forward_to_sheet(order: Order) -> None:
    """Forward Naseem orders to the Sukoon spreadsheet, tab «نسيم»."""
    webhook = (settings.sheet_webhook_url or SUKOON_SHEET_WEBHOOK).strip()
    if not webhook:
        logger.warning("SHEET_WEBHOOK_URL not configured, skipping Sheet forward")
        return

    items = [
        {
            "sku": item.sku,
            "product_name": item.product_name,
            "quantity": item.quantity,
            "unit_price_sar": item.unit_price_sar,
            "line_total_sar": item.line_total_sar,
            "is_upsell": item.is_upsell,
        }
        for item in order.items
    ]
    products = " | ".join(
        f"{item.product_name} x{item.quantity}" for item in order.items
    )
    payload = {
        "brand": "naseem",
        "source": "naseem",
        "order_number": order.order_number,
        "name": order.name,
        "phone": order.phone_local,
        "phone_e164": order.phone_e164,
        "city": order.city or "",
        "address": order.address or "",
        "notes": order.notes or "",
        "total_sar": order.total_sar,
        "price": order.total_sar,
        "status": order.status,
        "created_at": order.created_at.isoformat() if order.created_at else "",
        "products": products,
        "items": items,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.post(webhook, json=payload)
            resp.raise_for_status()
            logger.info("Sheet webhook success for order %s", order.order_number)
    except Exception as exc:
        logger.error("Sheet webhook failed for order %s: %s", order.order_number, exc)
