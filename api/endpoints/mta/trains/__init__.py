from fastapi import APIRouter
from .next_four import router as next_four_router
from .all_data import router as all_data_router

router = APIRouter(prefix="/trains", tags=["mta"])
router.include_router(next_four_router)
router.include_router(all_data_router)
