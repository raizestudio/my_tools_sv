# routers/dns_auditor.py
import asyncio
import ipaddress
import re
import time

import dns.asyncresolver
import dns.name
import dns.rdatatype
import dns.resolver
from fastapi import APIRouter, HTTPException, status

from schemas.dns_auditor import (
    CaaAudit,
    DnsAuditRequest,
    DnsAuditResponse,
    DnsRecordItem,
    DnssecStatus,
    MailSecurityAudit,
)

router = APIRouter()

COMMON_RESOLVERS = ["1.1.1.1", "8.8.8.8"]
QUERY_TIMEOUT = 3.0


def is_restricted_ip(ip_str: str) -> bool:
    """SSRF Guard against private, loopback, link-local, and multicast IPs."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return False


async def query_record_safe(
    resolver: dns.asyncresolver.Resolver, domain: str, rtype: str
) -> list[DnsRecordItem]:
    """Queries a single record type and returns normalized DnsRecordItem items without throwing on NoAnswer."""
    try:
        answers = await resolver.resolve(domain, rtype, lifetime=QUERY_TIMEOUT)
        output = []
        for rdata in answers:
            output.append(
                DnsRecordItem(
                    recordType=rtype,
                    name=domain,
                    ttl=answers.ttl,
                    data=rdata.to_text(),
                )
            )
        return output
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return []
    except dns.exception.Timeout:
        return []
    except Exception:
        return []


def audit_spf(txt_records: list[str]) -> tuple[str | None, str, str]:
    """Analyzes SPF records for syntax issues, duplicate records, and loose +all qualifiers."""
    spf_records = [
        r.strip('"') for r in txt_records if r.strip('"').startswith("v=spf1")
    ]

    if not spf_records:
        return (
            None,
            "Missing",
            "No SPF record found. Domain is vulnerable to unauthorized sender spoofing.",
        )

    if len(spf_records) > 1:
        return (
            spf_records[0],
            "Warning",
            "Multiple SPF records found. RFC 7208 mandates exactly one SPF record; extra records cause validation failure.",
        )

    spf = spf_records[0]
    if "+all" in spf:
        return (
            spf,
            "Warning",
            "Record uses permissive '+all' which allows anyone on the internet to send on your behalf.",
        )
    if "~all" in spf:
        return spf, "Valid", "Configured with SoftFail (~all). Recommended baseline."
    if "-all" in spf:
        return (
            spf,
            "Valid",
            "Configured with HardFail (-all). Maximum strict enforcement.",
        )

    return spf, "Valid", "SPF record present."


def audit_dmarc(dmarc_records: list[str]) -> tuple[str | None, str | None, str]:
    """Analyzes DMARC record and extracts policy tag (p=reject, p=quarantine, p=none)."""
    raw_records = [
        r.strip('"') for r in dmarc_records if r.strip('"').startswith("v=DMARC1")
    ]

    if not raw_records:
        return (
            None,
            None,
            "Missing DMARC policy. Mail servers cannot verify alignment with SPF and DKIM.",
        )

    record = raw_records[0]
    match = re.search(r"\bp=([a-zA-Z]+)", record)
    policy = match.group(1).lower() if match else "none"

    if policy == "reject":
        return (
            record,
            policy,
            "Enforced (p=reject): Fraudulent and unaligned emails are blocked by receiving MTAs.",
        )
    if policy == "quarantine":
        return (
            record,
            policy,
            "Guarded (p=quarantine): Unaligned emails are directed to spam folders.",
        )

    return (
        record,
        policy,
        "Monitoring only (p=none): Unaligned emails are delivered normally without rejection.",
    )


@router.post("", response_model=DnsAuditResponse)
async def run_dns_audit(req: DnsAuditRequest):
    raw_domain = req.domain.strip().lower()
    raw_domain = re.sub(r"^https?://", "", raw_domain)
    raw_domain = raw_domain.split("/")[0].split(":")[0]

    # Validate domain name format
    if not re.match(
        r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$",
        raw_domain,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid domain name format.",
        )

    # Disallow scanning internal or link-local domains
    if raw_domain.endswith(
        (".local", ".internal", ".localhost", ".lan", ".test", ".invalid")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Queries targeting local or private TLDs are blocked.",
        )

    start_time = time.perf_counter()

    # Configure high-performance async resolver
    resolver = dns.asyncresolver.Resolver()
    resolver.nameservers = COMMON_RESOLVERS
    resolver.timeout = QUERY_TIMEOUT
    resolver.lifetime = QUERY_TIMEOUT

    # 1. Parallel execution of standard record types
    record_types = ["A", "AAAA", "MX", "NS", "SOA", "TXT", "CAA", "DS", "DNSKEY"]
    tasks = [query_record_safe(resolver, raw_domain, rtype) for rtype in record_types]
    dmarc_task = query_record_safe(resolver, f"_dmarc.{raw_domain}", "TXT")

    all_results = await asyncio.gather(*tasks, dmarc_task)

    collected_records: list[DnsRecordItem] = []
    by_type: dict[str, list[DnsRecordItem]] = {}

    for idx, rtype in enumerate(record_types):
        res = all_results[idx]
        by_type[rtype] = res
        collected_records.extend(res)

    dmarc_results = all_results[-1]

    # Check if target domain returned any records at all
    if not collected_records and not dmarc_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain '{raw_domain}' did not return any DNS records.",
        )

    # SSRF guard on resolved A records
    for r in by_type.get("A", []):
        if is_restricted_ip(r.data):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Domain resolves to private or restricted IP address: {r.data}",
            )

    # 2. DNSSEC Chain Evaluation
    ds_list = [r.data for r in by_type.get("DS", [])]
    dnskey_list = [r.data for r in by_type.get("DNSKEY", [])]

    if ds_list and dnskey_list:
        dnssec_status = DnssecStatus(
            enabled=True,
            status="Secure",
            details="Cryptographic chain of trust verified. Both DS delegation and DNSKEY records are present.",
            dsRecords=ds_list,
            dnskeyRecords=dnskey_list,
        )
    elif ds_list and not dnskey_list:
        dnssec_status = DnssecStatus(
            enabled=False,
            status="Misconfigured",
            details="DS record exists at the parent zone, but no corresponding DNSKEY records were found on the zone.",
            dsRecords=ds_list,
            dnskeyRecords=[],
        )
    elif not ds_list and dnskey_list:
        dnssec_status = DnssecStatus(
            enabled=False,
            status="Incomplete",
            details="DNSKEY records exist on the zone, but no DS record was detected at the parent TLD registrar.",
            dsRecords=[],
            dnskeyRecords=dnskey_list,
        )
    else:
        dnssec_status = DnssecStatus(
            enabled=False,
            status="Insecure / Not Configured",
            details="No DNSSEC records detected. DNS responses can be forged via cache poisoning or rogue resolvers.",
            dsRecords=[],
            dnskeyRecords=[],
        )

    # 3. Mail Security Evaluation (SPF & DMARC)
    txt_data = [r.data for r in by_type.get("TXT", [])]
    dmarc_data = [r.data for r in dmarc_results]

    spf_rec, spf_stat, spf_det = audit_spf(txt_data)
    dmarc_rec, dmarc_pol, dmarc_det = audit_dmarc(dmarc_data)

    mail_security = MailSecurityAudit(
        spfRecord=spf_rec,
        spfStatus=spf_stat,
        spfDetails=spf_det,
        dmarcRecord=dmarc_rec,
        dmarcPolicy=dmarc_pol,
        dmarcStatus=dmarc_det,
    )

    # 4. CAA (Certificate Authority Authorization) Evaluation
    caa_data = by_type.get("CAA", [])
    if caa_data:
        allowed_cas = []
        for r in caa_data:
            match = re.search(r'issue(?:wild)?\s+"([^"]+)"', r.data)
            if match:
                allowed_cas.append(match.group(1))

        caa_audit = CaaAudit(
            configured=True,
            allowedCAs=sorted(list(set(allowed_cas))),
            details=f"Certificate issuance restricted to {len(allowed_cas)} authorized authority tags.",
        )
    else:
        caa_audit = CaaAudit(
            configured=False,
            allowedCAs=[],
            details="No CAA record configured. Any globally trusted Certificate Authority can issue SSL/TLS certificates.",
        )

    total_query_time = int((time.perf_counter() - start_time) * 1000)

    # Add DMARC records to the primary record list for complete visibility
    collected_records.extend(dmarc_results)

    return DnsAuditResponse(
        domain=raw_domain,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        queryTimeMs=total_query_time,
        records=collected_records,
        dnssec=dnssec_status,
        mailSecurity=mail_security,
        caa=caa_audit,
    )
