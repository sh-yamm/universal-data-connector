from fastapi import APIRouter

router = APIRouter()


# Quick liveness check — useful for Docker health checks and uptime monitors
@router.get("/health")
def health_check():
    return {"status": "ok"}
