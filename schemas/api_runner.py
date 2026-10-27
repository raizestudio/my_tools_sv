from pydantic import BaseModel, Field

MAX_TIMEOUT_SECONDS = 25.0


class TimingBreakdown(BaseModel):
    dnsMs: int = Field(..., serialization_alias="dnsMs")
    ttfbMs: int = Field(..., serialization_alias="ttfbMs")
    downloadMs: int = Field(..., serialization_alias="downloadMs")
    totalMs: int = Field(..., serialization_alias="totalMs")


class HeaderItem(BaseModel):
    key: str
    value: str


class ApiRunRequest(BaseModel):
    method: str = Field(..., pattern="^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$")
    url: str = Field(..., min_length=4, max_length=4096)
    headers: list[HeaderItem] = Field(default_factory=list)
    body: str | None = None
    timeoutSeconds: float = Field(10.0, ge=1.0, le=MAX_TIMEOUT_SECONDS)


class ApiRunResponse(BaseModel):
    statusCode: int = Field(..., serialization_alias="statusCode")
    statusText: str = Field(..., serialization_alias="statusText")
    timing: TimingBreakdown
    headers: list[HeaderItem]
    body: str
    isJson: bool = Field(..., serialization_alias="isJson")
    isTruncated: bool = Field(..., serialization_alias="isTruncated")
    sizeBytes: int = Field(..., serialization_alias="sizeBytes")

    class Config:
        populate_by_name = True
