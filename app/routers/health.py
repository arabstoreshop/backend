from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
@router.get("/health/")
@router.get("/healthz")
@router.get("/healthz/")
async def health():
    return {"status": "ok", "service": "naseem-api"}
