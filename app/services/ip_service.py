import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class IPCheckResult:
    allowed: bool
    country: str = ""
    risk_score: float = 0.0
    reason: str = ""


async def check_ip(ip: str, phone: str = "") -> IPCheckResult:
    """
    Check client IP for fraud/VPN/location using MaxMind GeoIP2 Insights.
    If MaxMind credentials are not configured, allow all requests.
    """
    if not settings.restrict_orders_to_saudi:
        return IPCheckResult(allowed=True, country="", risk_score=0.0)

    if not settings.maxmind_account_id or not settings.maxmind_license_key:
        return IPCheckResult(allowed=True, country="SA", risk_score=0.0)

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://geoip.maxmind.com/geoip/v2.1/insights/{ip}",
                auth=(settings.maxmind_account_id, settings.maxmind_license_key),
                timeout=5.0,
            )

        if resp.status_code != 200:
            logger.warning("MaxMind API returned %d for IP=%s", resp.status_code, ip)
            return IPCheckResult(allowed=True, country="", risk_score=0.0)

        data = resp.json()
        country = data.get("country", {}).get("iso_code", "")
        risk_score = data.get("risk_score", 0.0)
        traits = data.get("traits", {})
        is_vpn = traits.get("is_anonymous_vpn", False)
        is_proxy = traits.get("is_anonymous_proxy", False)

        if is_vpn or is_proxy:
            return IPCheckResult(
                allowed=False,
                country=country,
                risk_score=risk_score,
                reason="vpn_detected",
            )

        if country and country != "SA":
            return IPCheckResult(
                allowed=False,
                country=country,
                risk_score=risk_score,
                reason="outside_saudi",
            )

        if risk_score > 80:
            return IPCheckResult(
                allowed=False,
                country=country,
                risk_score=risk_score,
                reason="high_risk_score",
            )

        return IPCheckResult(allowed=True, country=country, risk_score=risk_score)

    except Exception as e:
        logger.error("IP check failed for %s: %s", ip, str(e))
        return IPCheckResult(allowed=True, country="", risk_score=0.0)
