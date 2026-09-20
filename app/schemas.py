import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator

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
    "NSM-SCLP-SER": {"name": "نسيم سكالب — سيروم", "slug": "naseem-scalp-serum", "line": "beauty"},
    "NSM-BARR-CRM": {"name": "نسيم بارير — كريم", "slug": "naseem-barrier-cream", "line": "beauty"},
    "NSM-RGRD-PTC": {"name": "نسيم ريغارد — باتش", "slug": "naseem-regard-patches", "line": "beauty"},
    "NSM-SCLP-GUM": {"name": "نسيم سكالب — جامي", "slug": "naseem-scalp-gummies", "line": "beauty"},
    "NSM-BARR-GUM": {"name": "نسيم بارير — جامي", "slug": "naseem-barrier-gummies", "line": "beauty"},
    "NSM-RGRD-GUM": {"name": "نسيم ريغارد — جامي", "slug": "naseem-regard-gummies", "line": "beauty"},
}

# Tiered pricing: qty → bundle total
BUNDLE_PRICES = {1: 199, 2: 279, 3: 349}
BEAUTY_BUNDLE_PRICES = {1: 199, 2: 279, 3: 388}
BEAUTY_SKUS = {sku for sku, meta in PRODUCT_CATALOG.items() if meta.get("line") == "beauty"}
UPSELL_PRICE = 99


class OrderItemIn(BaseModel):
    sku: str
    quantity: int
    is_upsell: bool = False

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 64:
            raise ValueError("Invalid SKU")
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
    city: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
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
        digits = re.sub(r"\D", "", v)
        if len(digits) < 6 or len(v) > 20:
            raise ValueError("أدخل رقم هاتف صحيح")
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

        from collections import defaultdict
        qty_by_sku: dict[str, int] = defaultdict(int)
        for item in regular_items:
            qty_by_sku[item.sku] += item.quantity

        skus = list(qty_by_sku)
        beauty = [s for s in skus if s in BEAUTY_SKUS]
        care = [s for s in skus if s not in BEAUTY_SKUS]
        if beauty and care:
            raise ValueError("لا يمكن جمع منتجات المغرب والسعودية في طلب واحد")

        for sku, qty in qty_by_sku.items():
            table = BEAUTY_BUNDLE_PRICES if sku in BEAUTY_SKUS else BUNDLE_PRICES
            if qty not in table:
                raise ValueError("اختر كمية 1 أو 2 أو 3 لكل منتج")

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
