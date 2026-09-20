"""
Server-side conversion APIs: Meta CAPI, TikTok Events API, Snap CAPI.
Browser/server deduplication uses matching event IDs passed from frontend.
Phone is hashed server-side only (never send raw phone to ad platforms).
"""
import hashlib
import logging
import time

import httpx

from app.config import settings
from app.models import Order

logger = logging.getLogger(__name__)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.strip().encode()).hexdigest()


def _meta_phone_hash(order: Order) -> str:
    """Meta wants SHA256 of digits only with country code, no + or symbols."""
    return _sha256(order.phone_digits)


def _e164_phone_hash(order: Order) -> str:
    """TikTok/Snap want SHA256 of E.164 including + (e.g. +9665xxxxxxxx)."""
    return _sha256(order.phone_e164)


def _make_event_id(order: Order) -> str:
    """Use browser_event_id if provided, else generate deterministic server ID."""
    return order.browser_event_id or f"server-{order.order_number}"


async def send_meta_capi(order: Order) -> None:
    if not settings.meta_access_token or not settings.meta_pixel_id:
        logger.warning("Meta CAPI credentials not configured, skipping")
        return

    event_id = _make_event_id(order)
    payload = {
        "data": [
            {
                "event_name": "Purchase",
                "event_time": int(time.time()),
                "event_id": event_id,
                "action_source": "website",
                "user_data": {
                    "ph": [_meta_phone_hash(order)],
                    "country": [_sha256("sa")],
                },
                "custom_data": {
                    "currency": "SAR",
                    "value": order.total_sar,
                    "order_id": order.order_number,
                    "content_ids": [item.sku for item in order.items],
                    "content_type": "product",
                },
            }
        ]
    }

    url = f"https://graph.facebook.com/v19.0/{settings.meta_pixel_id}/events"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                params={"access_token": settings.meta_access_token},
                json=payload,
            )
            resp.raise_for_status()
            logger.info("Meta CAPI sent for order %s", order.order_number)
    except Exception as exc:
        logger.error("Meta CAPI failed for order %s: %s", order.order_number, exc)


async def send_tiktok_events(order: Order) -> None:
    if not settings.tiktok_access_token or not settings.tiktok_pixel_id:
        logger.warning("TikTok Events API not configured, skipping")
        return

    event_id = _make_event_id(order)
    payload = {
        "pixel_code": settings.tiktok_pixel_id,
        "event": "CompletePayment",
        "event_id": event_id,
        "timestamp": str(int(time.time())),
        "context": {
            "user": {
                "phone_number": _e164_phone_hash(order),
            },
        },
        "properties": {
            "currency": "SAR",
            "value": str(order.total_sar),
            "order_id": order.order_number,
            "content_id": [item.sku for item in order.items],
            "content_type": "product",
        },
    }

    url = "https://business-api.tiktok.com/open_api/v1.3/event/track/"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                headers={"Access-Token": settings.tiktok_access_token},
                json=payload,
            )
            resp.raise_for_status()
            logger.info("TikTok Events API sent for order %s", order.order_number)
    except Exception as exc:
        logger.error("TikTok Events API failed for order %s: %s", order.order_number, exc)


async def send_snap_capi(order: Order) -> None:
    if not settings.snap_access_token or not settings.snap_pixel_id:
        logger.warning("Snap CAPI not configured, skipping")
        return

    event_id = _make_event_id(order)
    payload = {
        "pixel_id": settings.snap_pixel_id,
        "app_id": "",
        "events": [
            {
                "event_type": "PURCHASE",
                "event_conversion_type": "WEB",
                "event_tag": event_id,
                "timestamp": str(int(time.time() * 1000)),
                "hashed_phone_number": _e164_phone_hash(order),
                "price": order.total_sar,
                "currency": "SAR",
            }
        ],
    }

    url = "https://tr.snapchat.com/v2/conversion"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.snap_access_token}"},
                json=payload,
            )
            resp.raise_for_status()
            logger.info("Snap CAPI sent for order %s", order.order_number)
    except Exception as exc:
        logger.error("Snap CAPI failed for order %s: %s", order.order_number, exc)


async def send_all_capi(order: Order) -> None:
    """Fire all CAPI events. Failures are non-fatal."""
    import asyncio

    await asyncio.gather(
        send_meta_capi(order),
        send_tiktok_events(order),
        send_snap_capi(order),
        return_exceptions=True,
    )
