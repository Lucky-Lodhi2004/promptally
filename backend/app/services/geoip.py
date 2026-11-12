"""Resolve country from a trusted ingress or a local MaxMind country database."""
import ipaddress
import hmac
from fastapi import Request, HTTPException
from backend.app.core.config import settings


def _trusted_peer(request: Request) -> bool:
    try:
        peer = ipaddress.ip_address(request.client.host)
        token = settings.TRUSTED_PROXY_TOKEN
        supplied = request.headers.get('X-Proxy-Token', '')
        return bool(token and hmac.compare_digest(supplied.encode(), token.encode())
                    and any(peer in ipaddress.ip_network(cidr) for cidr in settings.TRUSTED_PROXY_CIDRS))
    except (ValueError, AttributeError):
        return False


def get_client_ip(request: Request) -> str:
    peer = request.client.host if request.client else ""
    if _trusted_peer(request):
        # The trusted ingress must overwrite these headers, never append user input.
        candidate = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Real-IP")
        if candidate:
            try:
                return str(ipaddress.ip_address(candidate.strip()))
            except ValueError:
                return peer
    return peer


def detect_country(request: Request):
    if _trusted_peer(request):
        country = request.headers.get("CF-IPCountry", "").upper()
        if len(country) == 2 and country.isalpha() and country not in {"XX", "ZZ", "T1"}:
            return country, country == "IN"
    try:
        ip = ipaddress.ip_address(get_client_ip(request))
        if ip.is_global and settings.GEOIP_DATABASE_PATH:
            import geoip2.database
            with geoip2.database.Reader(settings.GEOIP_DATABASE_PATH) as reader:
                code = reader.country(str(ip)).country.iso_code
                if code:
                    return code, code == "IN"
    except (ValueError, OSError, ImportError):
        pass
    except Exception as exc:
        # GeoIP misses are normal, other programming errors should propagate.
        from geoip2.errors import AddressNotFoundError
        if not isinstance(exc, AddressNotFoundError):
            raise
    return "ZZ", False


def checkout_country(request: Request):
    country, india = detect_country(request)
    if country == "ZZ":
        raise HTTPException(503, "Cannot verify IP country. Configure trusted ingress or the GeoIP database.")
    return country, india
