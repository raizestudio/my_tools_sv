from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from schemas.url_shtnr import ShortenRequest, ShortenResponse
from utils.crypto import generate_short_code
from utils.db import supabase_client

router = APIRouter()


@router.post(
    "/shorten", response_model=ShortenResponse, status_code=status.HTTP_201_CREATED
)
async def shorten_url(request: Request, payload: ShortenRequest):
    short_code = (
        payload.custom_code.strip() if payload.custom_code else generate_short_code()
    )

    # 2. Check if the code already exists
    existing = (
        supabase_client.table("urls")
        .select("id")
        .eq("short_code", short_code)
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Short code already in use. Please choose another.",
        )

    # 3. Store in Supabase
    record = {
        "original_url": str(payload.url),
        "short_code": short_code,
    }
    insert_res = supabase_client.table("urls").insert(record).execute()

    if not insert_res.data:
        raise HTTPException(status_code=500, detail="Failed to create short link.")

    full_short_url = str(request.url_for("redirect_to_url", short_code=short_code))

    return ShortenResponse(
        short_code=short_code,
        short_url=full_short_url,
        original_url=str(payload.url),
    )


@router.get("/{short_code}", name="redirect_to_url")
async def redirect_to_url(short_code: str):
    res = (
        supabase_client.table("urls")
        .select("id, original_url, clicks")
        .eq("short_code", short_code)
        .execute()
    )

    if not res.data:
        raise HTTPException(status_code=404, detail="URL not found")

    target = res.data[0]

    # Increment click count
    supabase_client.table("urls").update(
        {"clicks": target["clicks"] + 1}
    ).eq("id", target["id"]).execute()

    return {"original_url": target["original_url"]}
