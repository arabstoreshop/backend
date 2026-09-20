import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import OrderIn, OrderOut
from app.services.ip_service import check_ip
from app.services.order_service import create_order, get_order_by_number
from app.services.rate_limit import too_many_orders
from app.services.sheet_service import forward_to_sheet
from app.services.tracking_service import send_all_capi

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])


def _get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting reverse-proxy headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else ""


@router.post("", response_model=OrderOut, status_code=201)
@router.post("/", response_model=OrderOut, status_code=201, include_in_schema=False)
async def place_order(request: Request, order_in: OrderIn, db: Session = Depends(get_db)):
    client_ip = _get_client_ip(request)
    logger.info("Order attempt from IP=%s phone=%s", client_ip, order_in.phone[:4] + "****")

    if not order_in.items:
        raise HTTPException(status_code=422, detail="يجب أن يحتوي الطلب على منتج واحد على الأقل")

    if too_many_orders(f"{client_ip}:{order_in.phone}"):
        raise HTTPException(status_code=429, detail="طلبات كثيرة. حاول بعد قليل.")

    ip_result = await check_ip(client_ip, phone=order_in.phone)
    if not ip_result.allowed:
        logger.warning(
            "Order blocked — IP=%s reason=%s country=%s risk=%.1f",
            client_ip, ip_result.reason, ip_result.country, ip_result.risk_score,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "order_blocked",
                "reason": ip_result.reason,
                "message": "عذراً، لا يمكن إتمام الطلب من موقعك الحالي. يرجى التأكد من أنك في السعودية وعدم استخدام VPN.",
                "message_en": "Sorry, we cannot process orders from your current location. Please ensure you are in Saudi Arabia and not using a VPN.",
            },
        )

    order = create_order(db, order_in)

    # Fire-and-forget: Sheet + CAPI. Failures must not affect order response.
    asyncio.create_task(_post_order_tasks(order))

    return order


@router.get("/{order_number}", response_model=OrderOut)
def fetch_order(order_number: str, db: Session = Depends(get_db)):
    order = get_order_by_number(db, order_number)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


async def _post_order_tasks(order):
    await asyncio.gather(
        forward_to_sheet(order),
        send_all_capi(order),
        return_exceptions=True,
    )
