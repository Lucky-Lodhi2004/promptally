"""Read-only verification email setup check. Never prints secrets or sends mail."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import text
from redis import Redis
from backend.app.core.config import settings
from backend.app.db.session import engine
from backend.app.services.crypto import cipher
from backend.app.services.registration import quota_key
from alembic.config import Config
from alembic.script import ScriptDirectory


def main():
    checks = {
        'SMTP host configured': bool(settings.SMTP_HOST),
        'SMTP app password configured': bool(settings.SMTP_PASSWORD),
        'SMTP username/from configured': bool(settings.SMTP_USERNAME and settings.EMAIL_FROM),
        'SMTP TLS configured': settings.SMTP_SECURITY in {'starttls', 'ssl'},
        'Celery Redis broker configured': settings.CELERY_BROKER_URL.startswith(('redis://', 'rediss://')),
        'Rate limiting enabled': settings.RATE_LIMIT_ENABLED,
    }
    try: cipher(); checks['Encryption key valid'] = True
    except Exception: checks['Encryption key valid'] = False
    try:
        with Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1) as client:
            checks['Redis reachable'] = bool(client.ping())
    except Exception: checks['Redis reachable'] = False
    try:
        with engine.connect() as conn:
            head = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))).get_current_head()
            checks['Verification migration applied'] = conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == head
            count = conn.execute(text('SELECT used FROM signup_quotas WHERE key=:key'), {'key': quota_key('ip', '127.0.0.1')}).scalar_one_or_none() or 0
        print(f'Local proxy IP signup quota used: {count}/{settings.MAX_ACCOUNTS_PER_IP}')
    except Exception: checks['Verification migration applied'] = False
    for label, ok in checks.items(): print(f'{"OK" if ok else "MISSING"}: {label}')
    print('Read-only check: no SMTP authentication, email delivery, or worker-health test performed.')
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
