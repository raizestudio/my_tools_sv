from fastapi import APIRouter, Request

from config import Settings

router = APIRouter()
settings = Settings()


@router.get("/")
async def root(request: Request):
    return {"detail": "I'm tired boss.", "name": settings.app_name}


@router.get("/health")
async def health(request: Request):
    return {"detail": "We good.", "version": settings.app_version}
