from __future__ import annotations

import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Order, OrderItem

router = APIRouter(prefix="/admin", tags=["admin"])

SAR_PER_USD = 3.75


def require_admin(x_admin_key: Optional[str] = Header(default=None)):
    expected = (settings.admin_api_key or "").strip()
    if not expected:
        if settings.environment == "production":
            raise HTTPException(status_code=503, detail="Admin is not configured")
        return True
    if not x_admin_key or not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@router.get("/aov")
def lifetime_aov(_: bool = Depends(require_admin), db: Session = Depends(get_db)):
    """Lifetime AOV + average pieces from stored orders (SAR)."""
    row = db.query(
        func.count(Order.id),
        func.coalesce(func.sum(Order.total_sar), 0),
    ).one()
    order_count = int(row[0] or 0)
    revenue_sar = float(row[1] or 0)

    pieces = db.query(func.coalesce(func.sum(OrderItem.quantity), 0)).scalar()
    pieces = float(pieces or 0)

    aov_sar = (revenue_sar / order_count) if order_count else float(settings.price_1)
    if order_count:
        avg_pieces = (pieces / order_count) if pieces else 1.0
    else:
        avg_pieces = 1.0
    aov_usd = aov_sar / SAR_PER_USD

    return {
        "order_count": order_count,
        "revenue_sar": round(revenue_sar, 2),
        "aov_sar": round(aov_sar, 2),
        "aov_usd": round(aov_usd, 2),
        "avg_pieces": round(avg_pieces, 2),
        "sar_per_usd": SAR_PER_USD,
        "source": "orders" if order_count else "catalog_fallback",
    }
