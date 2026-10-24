from fastapi import APIRouter

from . import (
    core,
    url_shtnr,
)

router = APIRouter()
router.include_router(core.router, tags=["Core"])
router.include_router(url_shtnr.router, prefix="/url-shtnr", tags=["UrlShtnr"])
