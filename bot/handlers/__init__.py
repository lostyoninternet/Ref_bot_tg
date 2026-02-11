from aiogram import Router

from .start import router as start_router
from .cabinet import router as cabinet_router
from .referral import router as referral_router
from .tips import router as tips_router
from .admin import router as admin_router


def get_all_routers() -> list[Router]:
    """Return all routers for registration."""
    return [
        start_router,
        cabinet_router,
        referral_router,
        tips_router,
        admin_router,
    ]
