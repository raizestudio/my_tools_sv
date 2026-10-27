from pydantic import BaseModel, Field


class HopItem(BaseModel):
    hop: int
    url: str
    statusCode: int = Field(..., serialization_alias="statusCode")
    statusText: str = Field(..., serialization_alias="statusText")
    latencyMs: int = Field(..., serialization_alias="latencyMs")
    server: str | None = None
    contentType: str | None = Field(None, serialization_alias="contentType")
    location: str | None = None
    resolvedIp: str = Field(..., serialization_alias="resolvedIp")


class TraceRequest(BaseModel):
    url: str = Field(..., min_length=4, max_length=2048)
    userAgentProfile: str = Field(
        "desktop", pattern="^(desktop|googlebot|slackbot|curl)$"
    )


class TraceResponse(BaseModel):
    inputUrl: str = Field(..., serialization_alias="inputUrl")
    finalUrl: str = Field(..., serialization_alias="finalUrl")
    cleanUrl: str = Field(..., serialization_alias="cleanUrl")
    defangedUrl: str = Field(..., serialization_alias="defangedUrl")
    pageTitle: str | None = Field(None, serialization_alias="pageTitle")
    totalDurationMs: int = Field(..., serialization_alias="totalDurationMs")
    totalHops: int = Field(..., serialization_alias="totalHops")
    strippedParams: list[str] = Field(..., serialization_alias="strippedParams")
    hops: list[HopItem]

    class Config:
        populate_by_name = True
