from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PortResult(BaseModel):
    port: int
    status: Literal["open", "closed", "filtered"]
    service: str
    latencyMs: int = Field(..., serialization_alias="latencyMs")
    banner: str | None = None

    class Config:
        populate_by_name = True


class ProbeRequest(BaseModel):
    target: str = Field(..., min_length=1, max_length=253)
    ports: list[int] = Field(..., min_length=1, max_length=20)

    @field_validator("ports")
    @classmethod
    def validate_ports(cls, ports: list[int]) -> list[int]:
        unique_ports = sorted(set(ports))
        for p in unique_ports:
            if p < 1 or p > 65535:
                raise ValueError(f"Port {p} is out of valid range (1-65535)")
        return unique_ports


class ProbeResponse(BaseModel):
    target: str
    resolvedIp: str = Field(..., serialization_alias="resolvedIp")
    timestamp: str
    results: list[PortResult]

    class Config:
        populate_by_name = True
