import hashlib
import ipaddress
import re
from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from backend.app.core.config import settings
from backend.app.models.registration import SignupQuota
from backend.app.services.geoip import get_client_ip


def quota_key(kind, value):
    return hashlib.sha256(f'{kind}:{value}'.encode()).hexdigest()


def registration_identity(request, supplied=None):
    header = request.headers.get('X-Device-Fingerprint', '')
    if supplied and header and supplied != header:
        raise HTTPException(400, 'Device fingerprint values do not match')
    fingerprint = supplied or header
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{6,128}', fingerprint):
        raise HTTPException(400, 'A valid device fingerprint is required for signup')
    ip = get_client_ip(request)
    try:
        parsed = ipaddress.ip_address(ip)
        ip = str(parsed.ipv4_mapped or parsed) if isinstance(parsed, ipaddress.IPv6Address) else str(parsed)
    except ValueError:
        raise HTTPException(503, 'Cannot determine signup IP address') from None
    return ip, fingerprint


def reserve_signup(db, ip, fingerprint):
    """Lock quota rows in deterministic order; commit counters with the new user.

    No expiry/decrement: the policy limits successful account creations, including
    unverified accounts. Deleting a user or restarting Redis does not reset it.
    """
    entries = [('ip', ip, settings.MAX_ACCOUNTS_PER_IP),
               ('device', fingerprint, settings.MAX_ACCOUNTS_PER_DEVICE)]
    entries.sort(key=lambda entry: quota_key(entry[0], entry[1]))
    insert = pg_insert if db.get_bind().dialect.name == 'postgresql' else sqlite_insert
    for kind, value, limit in entries:
        key = quota_key(kind, value)
        db.execute(insert(SignupQuota).values(key=key, kind=kind, used=0).on_conflict_do_nothing(index_elements=['key']))
        quota = db.query(SignupQuota).filter_by(key=key).with_for_update().one()
        if quota.used >= limit:
            raise HTTPException(403, f'Registration blocked: Maximum of {limit} accounts allowed per {kind}.')
        quota.used += 1
        db.flush()
