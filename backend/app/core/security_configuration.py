"""Checks that never print secret values or silently rotate provider credentials."""
from urllib.parse import urlsplit


def security_configuration_issues(settings):
    issues = []
    for name in ('SECRET_KEY', 'RAZORPAY_WEBHOOK_SECRET', 'RAZORPAY_PARTNER_WEBHOOK_SECRET'):
        value = getattr(settings, name, '')
        if len(value) < 32 or value.startswith('promptally-secret-key-change'):
            issues.append(f'{name} must be replaced with a random secret of at least 32 characters')
    if settings.TRUSTED_PROXY_CIDRS and len(settings.TRUSTED_PROXY_TOKEN) < 32:
        issues.append('Trusted proxy CIDRs require a random TRUSTED_PROXY_TOKEN of at least 32 characters')
    if not settings.RATE_LIMIT_ENABLED:
        issues.append('RATE_LIMIT_ENABLED must be true')
    if not settings.SITE_URL.startswith('https://'):
        issues.append('Production SITE_URL must use HTTPS')
    return issues
