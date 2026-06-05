import logging

import httpx

from app.config import settings
from app.models import Order

logger = logging.getLogger(__name__)


async def forward_to_sheet(order: Order) -> None:
    """Forward order data to Google Sheets Apps Script webhook."""
    if not settings.sheet_webhook_url:
        logger.warning("SHEET_WEBHOOK_URL not configured, skipping Sheet forward")
        return

    payload = {
        "order_number": order.order_number,
        "name": order.name,
        "phone": order.phone_local,
        "phone_e164": order.phone_e164,
        "total_sar": order.total_sar,
        "status": order.status,
        "created_at": order.created_at.isoformat(),
        "items": [
            {
                "sku": item.sku,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price_sar": item.unit_price_sar,
                "line_total_sar": item.line_total_sar,
                "is_upsell": item.is_upsell,
            }
            for item in order.items
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(settings.sheet_webhook_url, json=payload)
            resp.raise_for_status()
            logger.info("Sheet webhook success for order %s", order.order_number)
    except Exception as exc:
        # Non-fatal: log and continue — order already saved to DB
        logger.error(
            "Sheet webhook failed for order %s: %s", order.order_number, exc
        )
