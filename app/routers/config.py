from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["config"])


@router.get("/config/public")
@router.get("/config/public/")
async def public_config():
    """Public pixel IDs only — never tokens. Frontend loads these at runtime."""
    return {
        "meta_pixel_id": settings.meta_pixel_id,
        "tiktok_pixel_id": settings.tiktok_pixel_id,
        "snap_pixel_id": settings.snap_pixel_id,
    }
