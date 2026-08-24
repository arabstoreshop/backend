import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator

# Valid Saudi phone pattern
_SAUDI_PHONE_RE = re.compile(r"^05\d{8}$")

# Canonical product catalog — server-side source of truth
PRODUCT_CATALOG = {
    "NSM-GEL-001": {
        "name": "جل البواسير بتقنية الكيتوزان الحيوي",
        "slug": "chitosan-bio-gel",
    },
    "NSM-DIO-001": {
        "name": "كبسولات الديوسمين والهسبريدين لدعم الأوردة",
        "slug": "diosmin-hesperidin-capsules",
    },
    "NSM-CUR-001": {
        "name": "كبسولات الكركمين المُعزّز لعلاج البواسير",
        "slug": "curcumin-advanced-capsules",
    },
    "NSM-SPR-001": {
        "name": "بخاخ الأعشاب الطبيعية لتخفيف البواسير",
        "slug": "herbal-relief-spray",
    },
    "NSM-WIP-001": {
        "name": "مناديل الويتش هازل والألوفيرا الطبية",
        "slug": "witch-hazel-aloe-wipes",
    },
    "NSM-FIB-001": {
        "name": "كبسولات الألياف الطبيعية بالسيليوم",
        "slug": "psyllium-fiber-capsules",
    },
    "NSM-SUP-001": {
        "name": "تحاميل البواسير بالكيتوزان والأعشاب",
        "slug": "herbal-hemorrhoid-suppositories",
    },
    "NSM-CSH-001": {
        "name": "وسادة الراحة الطبية للبواسير",
        "slug": "hemorrhoid-donut-cushion",
    },
    "NSM-BTH-001": {
        "name": "حوض المقعدة العلاجي القابل للطي",
        "slug": "foldable-sitz-bath",
    },
}

# Tiered pricing: qty → price per unit (total price / qty)
# Actually priced as bundle totals:
BUNDLE_PRICES = {1: 199, 2: 279, 3: 349}
UPSELL_PRICE = 99


class OrderItemIn(BaseModel):
    sku: str
    quantity: int
    is_upsell: bool = False

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, v: str) -> str:
        if v not in PRODUCT_CATALOG:
            raise ValueError(f"Unknown SKU: {v}")
        return v

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError("Quantity must be between 1 and 10")
        return v


class OrderIn(BaseModel):
    name: str
    phone: str
    items: list[OrderItemIn]
    browser_event_id: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not _SAUDI_PHONE_RE.match(v):
            raise ValueError("رقم الجوال يجب أن يبدأ بـ 05 ويتكون من 10 أرقام")
        return v

    @field_validator("items")
    @classmethod
    def validate_items_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("يجب أن يحتوي الطلب على منتج واحد على الأقل")
        return v

    @model_validator(mode="after")
    def validate_pricing(self) -> "OrderIn":
        # Separate regular items and upsell items
        regular_items = [i for i in self.items if not i.is_upsell]
        upsell_items = [i for i in self.items if i.is_upsell]

        # Each product group: validate bundle pricing
        # Group by SKU (main product)
        from collections import Counter
        sku_counter: Counter = Counter()
        for item in regular_items:
            sku_counter[item.sku] += item.quantity

        # We allow one or multiple SKUs; total qty drives the bundle price
        total_main_qty = sum(sku_counter.values())
        if total_main_qty not in BUNDLE_PRICES:
            raise ValueError(f"Quantity {total_main_qty} not supported. Choose 1, 2, or 3.")

        # Upsell: max 1 upsell item, price must be UPSELL_PRICE
        if len(upsell_items) > 1:
            raise ValueError("Only one upsell item is allowed per order")

        return self


class OrderItemOut(BaseModel):
    sku: str
    product_name: str
    quantity: int
    unit_price_sar: int
    line_total_sar: int
    is_upsell: bool

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    order_number: str
    name: str
    phone_local: str
    total_sar: int
    status: str
    created_at: datetime
    items: list[OrderItemOut]

    model_config = {"from_attributes": True}
