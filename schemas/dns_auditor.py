from pydantic import BaseModel, Field


class DnsRecordItem(BaseModel):
    recordType: str = Field(..., serialization_alias="recordType")
    name: str
    ttl: int
    data: str


class DnssecStatus(BaseModel):
    enabled: bool
    status: str  # "Secure", "Insecure / Not Configured", "Misconfigured"
    details: str
    dsRecords: list[str] = Field(default_factory=list, serialization_alias="dsRecords")
    dnskeyRecords: list[str] = Field(
        default_factory=list, serialization_alias="dnskeyRecords"
    )


class MailSecurityAudit(BaseModel):
    spfRecord: str | None = Field(None, serialization_alias="spfRecord")
    spfStatus: str = Field(
        ..., serialization_alias="spfStatus"
    )  # "Valid", "Warning", "Missing"
    spfDetails: str = Field(..., serialization_alias="spfDetails")
    dmarcRecord: str | None = Field(None, serialization_alias="dmarcRecord")
    dmarcPolicy: str | None = Field(
        None, serialization_alias="dmarcPolicy"
    )  # "reject", "quarantine", "none"
    dmarcStatus: str = Field(..., serialization_alias="dmarcStatus")


class CaaAudit(BaseModel):
    configured: bool
    allowedCAs: list[str] = Field(default_factory=list, serialization_alias="allowedCAs")
    details: str


class DnsAuditRequest(BaseModel):
    domain: str = Field(..., min_length=2, max_length=253)


class DnsAuditResponse(BaseModel):
    domain: str
    timestamp: str
    queryTimeMs: int = Field(..., serialization_alias="queryTimeMs")
    records: list[DnsRecordItem]
    dnssec: DnssecStatus
    mailSecurity: MailSecurityAudit = Field(..., serialization_alias="mailSecurity")
    caa: CaaAudit

    class Config:
        populate_by_name = True
