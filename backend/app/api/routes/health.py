from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health_check() -> dict[str, object]:
    settings = get_settings()
    return {"status": "ok", "service": settings.app_name, "organisms": ["c_elegans", "drosophila", "human"]}
