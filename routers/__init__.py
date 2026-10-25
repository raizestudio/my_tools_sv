from fastapi import APIRouter

from . import (
    core,
    secret,
    url_shtnr,
)

router = APIRouter()
router.include_router(core.router, tags=["core"])
router.include_router(url_shtnr.router, prefix="/url-shtnr", tags=["url-shtnr"])
router.include_router(secret.router, prefix="/secrets", tags=["secrets"])
