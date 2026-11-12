"""Real PostgreSQL concurrency checks; no application DB or SMTP credentials used."""
import getpass
from pathlib import Path
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from backend.app.db.session import Base
from backend.app.models import User
from backend.app.models.registration import SignupQuota, EmailOutbox
from backend.app.services.registration import reserve_signup
from backend.app.services.email_verification import create_challenge, verify_token
from backend.app.services.crypto import decrypt_secret
from backend.app.core.config import settings
from backend.app import worker
from cryptography.fernet import Fernet

bin_dir = '/usr/lib/postgresql/16/bin/'
with tempfile.TemporaryDirectory(prefix='promptally-registration-') as directory:
    cluster = Path(directory)/'pg'
    subprocess.run([bin_dir+'initdb', '-D', str(cluster), '-A', 'trust', '--no-locale', '-E', 'UTF8'],
                   check=True, stdout=subprocess.DEVNULL)
    subprocess.run([bin_dir+'pg_ctl', '-D', str(cluster), '-l', str(Path(directory)/'postgres.log'),
        '-o', f"-k {directory} -p 55443 -c listen_addresses=''", '-w', 'start'], check=True, stdout=subprocess.DEVNULL)
    engine = None
    try:
        settings.CREDENTIALS_ENCRYPTION_KEY = Fernet.generate_key().decode()
        settings.REDIS_URL = ''
        engine = create_engine(f'postgresql+psycopg://{getpass.getuser()}@/postgres?host={directory}&port=55443')
        Base.metadata.create_all(engine)
        def signup(index, same_device=False):
            with Session(engine) as db:
                try:
                    ip = f'192.0.2.{index+1}' if same_device else '192.0.2.1'
                    device = 'shared-device' if same_device else f'device-{index}'
                    reserve_signup(db, ip, device)
                    user = User(email=f'{same_device}-{index}@example.com', username=f'user{same_device}{index}',
                        name='Test', device_fingerprint=device, signup_ip=ip, email_verification_required=True)
                    db.add(user); db.flush()
                    create_challenge(db, user)
                    db.commit()
                    return True
                except HTTPException as exc:
                    assert exc.status_code == 403
                    db.rollback()
                    return False
        with ThreadPoolExecutor(12) as pool:
            assert sum(pool.map(signup, range(12))) == 2
        with Session(engine) as db:
            assert db.query(User).count() == 2
            assert db.query(EmailOutbox).count() == 2
            assert max(q.used for q in db.query(SignupQuota)) == 2
            row = db.query(EmailOutbox).first()
            token = decrypt_secret(row.token_enc)
            user_id = row.user_id
        def verify(_):
            with Session(engine) as db:
                try: verify_token(db, token); return True
                except HTTPException as exc:
                    assert exc.status_code == 400
                    return False
        with ThreadPoolExecutor(8) as pool:
            assert sum(pool.map(verify, range(8))) == 1
        with Session(engine) as db:
            assert db.get(User, user_id).email_verified_at is not None
            # Preserve lifetime quota counters even after account deletion.
            db.query(EmailOutbox).delete(); db.query(User).delete(); db.commit()
        assert not signup(99)
        # Different IPs still share the independent device cap.
        with ThreadPoolExecutor(12) as pool:
            assert sum(pool.map(lambda i: signup(i, True), range(2, 14))) == 2
        # Duplicate worker deliveries serialize on the user row and send once.
        sent = []
        worker.smtp_send = lambda *args: sent.append(args)
        with Session(engine) as db:
            outbox_id = db.query(EmailOutbox).filter_by(status='pending').first().id
        def deliver(_):
            with Session(engine) as db: worker.deliver_outbox(db, outbox_id)
        with ThreadPoolExecutor(6) as pool: list(pool.map(deliver, range(6)))
        assert len(sent) == 1
        print('PASS: concurrent PostgreSQL IP/device quotas, durable deletion-resistant counters, atomic one-use verification, concurrent email delivery deduplication')
    finally:
        if engine: engine.dispose()
        subprocess.run([bin_dir+'pg_ctl', '-D', str(cluster), '-m', 'immediate', '-w', 'stop'],
                       check=True, stdout=subprocess.DEVNULL)
