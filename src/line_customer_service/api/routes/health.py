"""Process health endpoint without external service dependencies."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def health_check() -> dict[str, str]:
    """Report that the HTTP application can respond to a request."""
    return {"status": "ok"}
