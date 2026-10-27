from fastapi import APIRouter

from . import (
    core,
    probe,
    secret,
    url_shtnr,
    webhook,
)

router = APIRouter()
router.include_router(core.router, tags=["core"])
router.include_router(url_shtnr.router, prefix="/url-shtnr", tags=["url-shtnr"])
router.include_router(secret.router, prefix="/secrets", tags=["secrets"])
router.include_router(webhook.router, prefix="/webhooks", tags=["webhooks"])
router.include_router(probe.router, prefix="/probe", tags=["network probe"])
