"""
MaxMind GeoIP2 Insights API integration for IP-based fraud prevention.

Checks:
- Country must be Saudi Arabia (SA)
- Rejects VPN / proxy / Tor / hosting-provider IPs
- Rejects high-risk IPs (risk score > threshold)
- Whitelisted phone numbers bypass all checks
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

WHITELISTED_PHONES: set[str] = {
    "0550000022",
}

_ALLOWED_COUNTRIES = {"SA"}
_MAX_RISK_SCORE = 50.0


class IPCheckResult:
    def __init__(
        self,
        allowed: bool,
        reason: str = "",
        country: str = "",
        risk_score: float = 0.0,
        is_vpn: bool = False,
        is_proxy: bool = False,
        is_tor: bool = False,
        is_hosting: bool = False,
    ):
        self.allowed = allowed
        self.reason = reason
        self.country = country
        self.risk_score = risk_score
        self.is_vpn = is_vpn
        self.is_proxy = is_proxy
        self.is_tor = is_tor
        self.is_hosting = is_hosting


def _is_whitelisted_phone(phone: str) -> bool:
    normalized = phone.strip().replace(" ", "")
    return normalized in WHITELISTED_PHONES


async def check_ip(ip: str, phone: Optional[str] = None) -> IPCheckResult:
    """
    Verify an IP address using MaxMind GeoIP2 Insights API.
    Returns IPCheckResult with allowed=True if the request should proceed.
    """
    if phone and _is_whitelisted_phone(phone):
        logger.info("Phone %s is whitelisted — bypassing IP check", phone[:4] + "****")
        return IPCheckResult(allowed=True, reason="whitelisted_phone")

    if not settings.maxmind_account_id or not settings.maxmind_license_key:
        logger.warning("MaxMind credentials not configured — allowing request")
        return IPCheckResult(allowed=True, reason="maxmind_not_configured")

    if not ip or ip in ("127.0.0.1", "::1", "testclient"):
        if settings.environment == "development":
            logger.info("Local/test IP in dev mode — allowing")
            return IPCheckResult(allowed=True, reason="local_dev")
        return IPCheckResult(allowed=False, reason="invalid_ip")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://geoip.maxmind.com/geoip/v2.1/insights/{ip}",
                auth=(settings.maxmind_account_id, settings.maxmind_license_key),
            )

        if resp.status_code == 401:
            logger.error("MaxMind auth failed — check credentials")
            return IPCheckResult(allowed=True, reason="maxmind_auth_error")

        if resp.status_code != 200:
            logger.error("MaxMind API error %s: %s", resp.status_code, resp.text[:200])
            return IPCheckResult(allowed=True, reason="maxmind_api_error")

        data = resp.json()

        country_iso = data.get("country", {}).get("iso_code", "")
        traits = data.get("traits", {})
        risk = data.get("risk_score", 0.0)

        is_vpn = traits.get("is_anonymous_vpn", False)
        is_proxy = traits.get("is_anonymous_proxy", False) or traits.get("is_public_proxy", False)
        is_tor = traits.get("is_tor_exit_node", False)
        is_hosting = traits.get("is_hosting_provider", False)

        result = IPCheckResult(
            allowed=True,
            country=country_iso,
            risk_score=risk,
            is_vpn=is_vpn,
            is_proxy=is_proxy,
            is_tor=is_tor,
            is_hosting=is_hosting,
        )

        if country_iso not in _ALLOWED_COUNTRIES:
            result.allowed = False
            result.reason = f"country_blocked:{country_iso}"
            logger.warning("IP %s blocked — country %s not in allowed list", ip, country_iso)
            return result

        if is_vpn or is_proxy or is_tor:
            result.allowed = False
            flags = []
            if is_vpn:
                flags.append("VPN")
            if is_proxy:
                flags.append("Proxy")
            if is_tor:
                flags.append("Tor")
            result.reason = f"suspicious_network:{','.join(flags)}"
            logger.warning("IP %s blocked — %s detected", ip, ", ".join(flags))
            return result

        if is_hosting:
            result.allowed = False
            result.reason = "hosting_provider"
            logger.warning("IP %s blocked — hosting/datacenter IP", ip)
            return result

        if risk > _MAX_RISK_SCORE:
            result.allowed = False
            result.reason = f"high_risk_score:{risk}"
            logger.warning("IP %s blocked — risk score %.1f exceeds threshold", ip, risk)
            return result

        logger.info("IP %s allowed — country=%s risk=%.1f", ip, country_iso, risk)
        return result

    except httpx.TimeoutException:
        logger.error("MaxMind API timeout for IP %s — allowing request", ip)
        return IPCheckResult(allowed=True, reason="maxmind_timeout")
    except Exception as e:
        logger.error("MaxMind check failed for IP %s: %s — allowing request", ip, str(e))
        return IPCheckResult(allowed=True, reason=f"maxmind_error:{str(e)}")
