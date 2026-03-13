from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.runs import router as runs_router
from app.api.routes.skills import router as skills_router

router = APIRouter()
router.include_router(admin_router, prefix="/admin", tags=["admin"])
router.include_router(skills_router, prefix="/skills", tags=["skills"])
router.include_router(conversations_router, prefix="/conversations", tags=["conversations"])
router.include_router(runs_router, prefix="/runs", tags=["runs"])
