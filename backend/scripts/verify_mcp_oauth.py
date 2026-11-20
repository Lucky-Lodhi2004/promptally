"""Verify MCP migration and concurrent token exchange on disposable PostgreSQL.

Never connects to the configured application database or Google. Requires local
PostgreSQL 16 binaries. Run with ENVIRONMENT=development DATABASE_URL=sqlite://.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
import getpass
import hashlib
import faulthandler
from pathlib import Path
import socket
import signal
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.db.session import Base, get_db
from backend.app.main import app
from backend.app.models import User
from backend.app.models.mcp_oauth import MCPClient, MCPAuthorization, MCPGrant, MCPToken


def main():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit('Verification interrupted'))
    faulthandler.dump_traceback_later(20)
    binaries = Path('/usr/lib/postgresql/16/bin')
    with tempfile.TemporaryDirectory(prefix='promptally-mcp-oauth-') as directory:
        root = Path(directory)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        subprocess.run([str(binaries / 'initdb'), '-D', str(root / 'pg'), '-A', 'trust',
                        '--no-locale', '-E', 'UTF8'], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([str(binaries / 'pg_ctl'), '-D', str(root / 'pg'), '-l', str(root / 'pg.log'),
                        '-o', f"-k {directory} -p {port} -c listen_addresses=''", '-w', 'start'],
                       check=True, stdout=subprocess.DEVNULL)
        engine = None
        try:
            settings.DATABASE_URL = f'postgresql+psycopg://{getpass.getuser()}@/postgres?host={directory}&port={port}'
            settings.SITE_URL = 'https://testserver'
            settings.RATE_LIMIT_ENABLED = False
            settings.REDIS_URL = ''
            engine = create_engine(settings.DATABASE_URL, connect_args={'options': '-c lock_timeout=5000 -c statement_timeout=10000'})
            mcp_tables = {m.__tablename__ for m in (MCPClient, MCPAuthorization, MCPGrant, MCPToken)}
            Base.metadata.create_all(engine, tables=[t for t in Base.metadata.sorted_tables if t.name not in mcp_tables])
            with Session(engine) as db:
                db.add(User(id='test-google-user', email='user@example.com', name='Test', username='test',
                            google_sub='mock-google-subject', email_verification_required=False))
                db.commit()
            config = Config('backend/alembic.ini')
            command.stamp(config, 'd14e53c74005')
            command.upgrade(config, 'head')
            assert mcp_tables <= set(inspect(engine).get_table_names())
            with Session(engine) as db:
                assert db.get(User, 'test-google-user').google_sub == 'mock-google-subject'
            print('PASS migration and account preservation', flush=True)

            def isolated_db():
                with Session(engine) as db:
                    yield db
            app.dependency_overrides[get_db] = isolated_db
            verifier = 'v' * 64
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
            callback = 'http://127.0.0.1:8765/callback'

            with TestClient(app, base_url='https://testserver') as client:
                cid = client.post('/api/v1/oauth/register', json={'client_name': 'Race test',
                    'redirect_uris': [callback]}).json()['client_id']
                response = client.get('/api/v1/oauth/authorize', params={
                    'client_id': cid, 'redirect_uri': callback, 'response_type': 'code',
                    'code_challenge': challenge, 'code_challenge_method': 'S256',
                    'resource': 'https://testserver/api/v1/mcp'}, follow_redirects=False)
                handle = parse_qs(urlsplit(response.headers['location']).query)['request'][0]
                client.cookies.set('access_token', create_access_token('test-google-user'))
                approved = client.post('/api/v1/oauth/requests/' + handle, json={'approved': True})
                code = parse_qs(urlsplit(approved.json()['redirect_url']).query)['code'][0]
                print('PASS browser authorization', flush=True)

                def exchange(_):
                    return client.post('/api/v1/oauth/token', data={
                        'client_id': cid, 'grant_type': 'authorization_code', 'code': code,
                        'redirect_uri': callback, 'code_verifier': verifier,
                        'resource': 'https://testserver/api/v1/mcp'})
                with ThreadPoolExecutor(4) as pool:
                    responses = list(pool.map(exchange, range(4)))
                assert sorted(r.status_code for r in responses) == [200, 400, 400, 400]
                print('PASS concurrent code redemption', flush=True)
                tokens = next(r.json() for r in responses if r.status_code == 200)
                with Session(engine) as db:
                    assert db.query(MCPGrant).count() == 1 and db.query(MCPToken).count() == 1

                def refresh(_):
                    return client.post('/api/v1/oauth/token', data={
                        'client_id': cid, 'grant_type': 'refresh_token', 'refresh_token': tokens['refresh_token'],
                        'resource': 'https://testserver/api/v1/mcp'})
                with ThreadPoolExecutor(4) as pool:
                    responses = list(pool.map(refresh, range(4)))
                assert sorted(r.status_code for r in responses) == [200, 400, 400, 400]
                print('PASS concurrent refresh rotation', flush=True)
                renewed = next(r.json() for r in responses if r.status_code == 200)
                result = client.post('/api/v1/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
                                     headers={'Authorization': 'Bearer ' + renewed['access_token']})
                assert result.status_code == 401  # Refresh reuse revokes the entire grant.
            command.downgrade(config, 'd14e53c74005')
            assert not mcp_tables & set(inspect(engine).get_table_names())
            print('PostgreSQL migration, account preservation, concurrent code redemption and refresh replay checks passed.')
        finally:
            faulthandler.cancel_dump_traceback_later()
            app.dependency_overrides.clear()
            if engine:
                engine.dispose()
            subprocess.run([str(binaries / 'pg_ctl'), '-D', str(root / 'pg'), '-m', 'immediate', '-w', 'stop'],
                           check=True, stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
