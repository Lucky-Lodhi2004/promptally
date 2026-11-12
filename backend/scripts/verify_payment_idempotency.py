"""Exercise real PostgreSQL races and Redis locks in disposable local services.

Never uses DATABASE_URL or merchant credentials. Run from repository root:
    backend/venv/bin/python backend/scripts/verify_payment_idempotency.py
"""
import getpass
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fastapi import HTTPException
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request
from backend.app.core.config import settings
from backend.app.db.session import Base
from backend.app.models import User
from backend.app.models.marketplace import CheckoutAttempt, PendingCheckout, WebhookEvent
from backend.app.models.asset import Asset
from backend.app.models.enums import SellerGateway
from backend.app.services.idempotency import (
    claim_webhook, checkout_reference, idempotent_checkout, provider_mutation_started, redis_lock,
)


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


bin_dir = '/usr/lib/postgresql/16/bin/'
with tempfile.TemporaryDirectory(prefix='promptally-idempotency-') as directory:
    root = Path(directory)
    cluster = root / 'pg'
    port = free_port()
    redis_port = free_port()
    subprocess.run([bin_dir+'initdb', '-D', str(cluster), '-A', 'trust', '--no-locale', '-E', 'UTF8'],
                   check=True, stdout=subprocess.DEVNULL)
    subprocess.run([bin_dir+'pg_ctl', '-D', str(cluster), '-l', str(root/'postgres.log'),
                    '-o', f"-k {directory} -p {port} -c listen_addresses=''", '-w', 'start'],
                   check=True, stdout=subprocess.DEVNULL)
    redis_log = (root/'redis.log').open('w')
    redis_process = subprocess.Popen(['redis-server', '--bind', '127.0.0.1', '--port', str(redis_port),
        '--save', '', '--appendonly', 'no', '--dir', directory], stdout=redis_log, stderr=redis_log)
    engine = None
    try:
        settings.TRUSTED_PROXY_CIDRS = ['127.0.0.1/32']
        settings.REDIS_URL = f'redis://127.0.0.1:{redis_port}/0'
        redis = Redis.from_url(settings.REDIS_URL)
        for _ in range(100):
            try:
                if redis.ping(): break
            except Exception: time.sleep(.02)
        else: raise RuntimeError('Disposable Redis failed to start')
        engine = create_engine(f'postgresql+psycopg://{getpass.getuser()}@/postgres?host={directory}&port={port}')
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add_all([User(id='buyer', email='b@example.com', username='buyer', name='Buyer'),
                        User(id='seller', email='s@example.com', username='seller', name='Seller')])
            db.flush()
            db.add(Asset(id='asset', slug='prompt', seo_title='Prompt', short_description='Test',
                asset_type='PROMPT', raw_content='secret', file_name='prompt.md', file_extension='.md',
                author_id='seller', is_paid=True, price_cents=500))
            db.commit()

        # A duplicate insert waits for the first transaction; rollback permits retry.
        for commit in [True, False]:
            event = 'committed' if commit else 'rolled-back'
            started = threading.Event()
            def first():
                with Session(engine) as db:
                    assert claim_webhook(db, 'platform:razorpay', event)
                    started.set(); time.sleep(.2)
                    db.commit() if commit else db.rollback()
            def second():
                started.wait(3)
                with Session(engine) as db:
                    claimed = claim_webhook(db, 'platform:razorpay', event)
                    db.commit()
                    return claimed
            with ThreadPoolExecutor(2) as pool:
                a = pool.submit(first); b = pool.submit(second)
                assert b.result(timeout=5) is (not commit)
                a.result(timeout=5)

        calls = []
        @idempotent_checkout('purchase')
        def create(slug, request, db, current_user):
            provider_mutation_started()
            calls.append(checkout_reference())
            time.sleep(.08)  # Provider round trip.
            db.add(PendingCheckout(id=checkout_reference(), buyer_id='buyer', asset_id='asset',
                seller_id='seller', gateway=SellerGateway.RAZORPAY, provider_order_id='order_'+checkout_reference(),
                expected_amount_minor=500, currency='INR'))
            return {'payment_reference': checkout_reference(), 'gateway': 'razorpay'}
        def call(index):
            request = Request({'type': 'http', 'method': 'POST', 'path': '/',
                'client': ('127.0.0.1', 1234), 'headers': [(b'cf-ipcountry', b'IN'),
                    (b'idempotency-key', f'concurrent-key-{index}'.encode())]})
            with Session(engine) as db:
                try:
                    return create(slug='prompt', request=request, db=db, current_user=db.get(User, 'buyer'))
                except HTTPException as exc:
                    assert exc.status_code == 409
                    return None

        # Redis contention, then PostgreSQL-only contention (simulated Redis outage).
        for phase, use_redis in enumerate([True, False], start=1):
            with Session(engine) as db:
                db.query(PendingCheckout).delete()
                db.query(CheckoutAttempt).delete()
                db.commit()
            settings.REDIS_URL = f'redis://127.0.0.1:{redis_port}/0' if use_redis else ''
            with ThreadPoolExecutor(8) as pool:
                results = list(pool.map(call, range(8)))
            assert any(results)
            assert len(calls) == phase, calls
            assert len({r['payment_reference'] for r in results if r}) == 1
        with Session(engine) as db:
            assert db.query(PendingCheckout).count() == 1
            assert db.query(WebhookEvent).count() == 2

        # Exercise the real compare-and-delete Lua against a replacement lock.
        settings.REDIS_URL = f'redis://127.0.0.1:{redis_port}/0'
        scope = 'expired-owner'
        key = 'promptally:checkout:' + hashlib.sha256(scope.encode()).hexdigest()
        with redis_lock(scope):
            redis.delete(key)  # Simulate expiration while first worker is still running.
            redis.set(key, 'new-owner', nx=True, ex=60)
        assert redis.get(key) == b'new-owner'

        # A durable in-flight claim survives Redis state loss and rejects a new key.
        with Session(engine) as db:
            db.add(CheckoutAttempt(user_id='buyer', operation='purchase', resource='blocked',
                idempotency_key='worker-that-crashed', request_hash='0'*64, status='unknown'))
            db.commit()
        redis.flushdb()  # This Redis instance is private to this script.
        request = Request({'type': 'http', 'method': 'POST', 'path': '/',
            'client': ('127.0.0.1', 1234), 'headers': [(b'cf-ipcountry', b'IN'), (b'idempotency-key', b'new-key-after-crash')]})
        with Session(engine) as db:
            try:
                create(slug='blocked', request=request, db=db, current_user=db.get(User, 'buyer'))
            except HTTPException as exc:
                assert exc.status_code == 409
            else: raise AssertionError('Unknown outcome created another checkout')
        assert len(calls) == 2
        print('PASS: real PostgreSQL concurrent webhook commit/rollback, concurrent checkout claims, Redis and PostgreSQL fallback, ownership-safe lock release, Redis loss with durable unknown claim')
    finally:
        if engine: engine.dispose()
        redis_process.terminate(); redis_process.wait(timeout=5); redis_log.close()
        subprocess.run([bin_dir+'pg_ctl', '-D', str(cluster), '-m', 'immediate', '-w', 'stop'],
                       check=True, stdout=subprocess.DEVNULL)
