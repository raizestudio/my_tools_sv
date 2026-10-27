from fastapi import APIRouter

from . import (
    api_runner,
    core,
    dns_auditor,
    probe,
    secret,
    url_shtnr,
    url_tracer,
    webhook,
)

router = APIRouter()
router.include_router(core.router, tags=["Core"])
router.include_router(url_shtnr.router, prefix="/url-shtnr", tags=["URL Shortener"])
router.include_router(secret.router, prefix="/secrets", tags=["Secrets"])
router.include_router(webhook.router, prefix="/webhooks", tags=["Webhooks"])
router.include_router(probe.router, prefix="/probe", tags=["Network Probe"])
router.include_router(
    url_tracer.router, prefix="/url-trace", tags=["URL Tracel & Defanger"]
)
router.include_router(
    dns_auditor.router, prefix="/dns-audit", tags=["DNS & DNSSEC Auditor"]
)
router.include_router(
    api_runner.router, prefix="/http-runner", tags=["Stateless API Runner"]
)
