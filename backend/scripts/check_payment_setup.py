"""Report local payment configuration without printing any secret values."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cryptography.fernet import Fernet
from backend.app.core.config import settings


def main():
    missing = []
    for name in ('RAZORPAY_KEY_ID', 'RAZORPAY_KEY_SECRET', 'RAZORPAY_WEBHOOK_SECRET',
                 'DODO_API_KEY', 'DODO_WEBHOOK_SECRET', 'DODO_PRODUCT_ID'):
        ok = bool(getattr(settings, name))
        print(f"{name}: {'configured' if ok else 'MISSING'}")
        if not ok: missing.append(name)
    try:
        Fernet(settings.CREDENTIALS_ENCRYPTION_KEY.encode())
        print('Credential encryption: configured')
    except (ValueError, TypeError):
        missing.append('CREDENTIALS_ENCRYPTION_KEY')
        print('Credential encryption: MISSING or invalid')
    country = bool(settings.TRUSTED_PROXY_CIDRS or (settings.GEOIP_DATABASE_PATH and Path(settings.GEOIP_DATABASE_PATH).is_file()))
    print(f"IP detection configuration: {'configured' if country else 'MISSING'}")
    if not country: missing.append('IP country configuration')
    print(f"Dodo environment: {settings.DODO_ENVIRONMENT}")
    print('Platform webhook URLs:')
    for provider in ('razorpay', 'dodo'):
        print(f"  {settings.SITE_URL.rstrip('/')}{settings.API_V1_STR}/webhooks/{provider}")
    print('Register these URLs in your merchant dashboards. Registration and merchant approval require sandbox verification.')
    from backend.app.services.seller_onboarding import oauth_ready, oauth_redirect_uri
    print(f"Seller Razorpay OAuth: {'configured (sandbox verification required)' if oauth_ready() else 'disabled; partner application settings missing'}")
    print(f"Seller OAuth redirect URI: {oauth_redirect_uri()}")
    print(f"Partner application webhook URL: {settings.SITE_URL.rstrip('/')}{settings.API_V1_STR}/webhooks/razorpay/partner")
    print('Dodo sellers can connect with an API key; webhook configuration is automatic.')
    print('Configuration incomplete.' if missing else 'Local configuration present. Verify live connectivity and signed sandbox events before activation.')
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
