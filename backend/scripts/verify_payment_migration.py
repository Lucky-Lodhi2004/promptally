"""Verify upgrading a populated legacy schema in a disposable PostgreSQL cluster."""
import os
import subprocess
import tempfile
from pathlib import Path
import sys
import getpass
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from alembic.config import Config
from alembic import command
from backend.app.db.session import Base
from backend.app.core.config import settings
from backend.app.models import User, Asset, Subscription, AssetPurchase
from backend.app.models.enums import UserTier, AssetType, SubscriptionGateway, SubscriptionStatus
from datetime import datetime, timezone, timedelta

bin_dir='/usr/lib/postgresql/16/bin/'
with tempfile.TemporaryDirectory(prefix='promptally-migration-') as directory:
    cluster=Path(directory)/'pg'
    subprocess.run([bin_dir+'initdb','-D',str(cluster),'-A','trust','--no-locale','-E','UTF8'],check=True,stdout=subprocess.DEVNULL)
    subprocess.run([bin_dir+'pg_ctl','-D',str(cluster),'-l',str(Path(directory)/'postgres.log'),
        '-o',f"-k {directory} -p 55439 -c listen_addresses=''",'-w','start'],check=True,stdout=subprocess.DEVNULL)
    try:
        url=f'postgresql+psycopg://{getpass.getuser()}@/postgres?host={directory}&port=55439'
        engine=create_engine(url)
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            seller=User(id='s',email='s@example.com',username='seller',name='Seller',tier=UserTier.PRO, signup_ip='192.0.2.10', device_fingerprint='legacy-seller')
            buyer=User(id='b',email='b@example.com',username='buyer',name='Buyer', signup_ip='192.0.2.10', device_fingerprint='legacy-buyer')
            db.add_all([seller,buyer]);db.flush()
            asset=Asset(id='a',slug='test',seo_title='Test',short_description='Test',asset_type=AssetType.PROMPT,
                        raw_content='secret',file_name='test.md',file_extension='.md',author_id='s',is_paid=True,price_cents=500)
            db.add(asset);db.flush()
            db.add(Subscription(user_id='s',gateway=SubscriptionGateway.PADDLE,gateway_subscription_id='sub_pad_demo',
                status=SubscriptionStatus.ACTIVE,current_period_end=datetime.now(timezone.utc)+timedelta(days=30)))
            db.add(AssetPurchase(buyer_id='b',asset_id='a',seller_id='s',amount_cents=500,seller_payout_cents=500,
                                status='COMPLETED'))
            db.commit()
        # Recreate the state before the previously unfinished BYOG migration.
        with engine.begin() as conn:
            for table in ('mcp_oauth_tokens','mcp_oauth_grants','mcp_oauth_authorizations','mcp_oauth_clients','email_outbox','email_challenges','signup_quotas','checkout_attempts','seller_oauth_states','pending_checkouts','seller_gateway_configs','webhook_events'):
                conn.execute(text(f'DROP TABLE {table} CASCADE'))
            conn.execute(text('DROP TYPE sellergateway'))
            conn.execute(text('DROP TYPE checkoutstatus'))
            columns={'users':['email_verified_at','email_verification_required','token_version','login_failure_count','login_locked_until'], 'subscriptions':['provider_customer_id','expected_amount_minor','checkout_reference','checkout_session_id','checkout_url','last_event_at'],
                     'assets':['price_inr_paise','seller_dodo_product_id','deleted_at','display_priority'],
                     'asset_purchases':['provider','provider_payment_id','currency']}
            for table,names in columns.items():
                for name in names:
                    conn.execute(text(f'ALTER TABLE {table} DROP COLUMN {name} CASCADE'))
            conn.execute(text('ALTER TABLE subscriptions ALTER COLUMN gateway TYPE varchar USING gateway::text'))
            conn.execute(text('DROP TYPE subscriptiongateway'))
            conn.execute(text("CREATE TYPE subscriptiongateway AS ENUM ('RAZORPAY','PADDLE')"))
            conn.execute(text('ALTER TABLE subscriptions ALTER COLUMN gateway TYPE subscriptiongateway USING gateway::subscriptiongateway'))
            conn.execute(text('ALTER TABLE subscriptions ALTER COLUMN status TYPE varchar USING status::text'))
            conn.execute(text('DROP TYPE subscriptionstatus'))
            conn.execute(text("CREATE TYPE subscriptionstatus AS ENUM ('ACTIVE','PAST_DUE','CANCELED','TRIALING')"))
            conn.execute(text('ALTER TABLE subscriptions ALTER COLUMN status TYPE subscriptionstatus USING status::subscriptionstatus'))
        settings.DATABASE_URL=url
        config=Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
        command.stamp(config,'689d7008f55c')
        command.upgrade(config,'f4b91c2d7001')
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO seller_gateway_configs (seller_id, razorpay_key_id, razorpay_key_secret_enc, razorpay_webhook_secret_enc, razorpay_verified_at, dodo_environment) VALUES ('s', 'legacy-key', 'encrypted-legacy-key', 'encrypted-hook', now(), 'test')"))
        command.upgrade(config,'head')
        with engine.connect() as conn:
            assert conn.execute(text('SELECT count(*) FROM assets')).scalar()==1
            assert conn.execute(text('SELECT status FROM asset_purchases')).scalar()=='PENDING'
            assert conn.execute(text('SELECT status FROM subscriptions')).scalar()=='CANCELED'
            assert conn.execute(text("SELECT tier FROM users WHERE id='s'")).scalar()=='FREE'
            labels=conn.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_type.oid=enumtypid WHERE typname='subscriptiongateway'")).scalars().all()
            assert 'DODO' in labels
            row=conn.execute(text("SELECT razorpay_key_secret_enc, razorpay_account_id FROM seller_gateway_configs WHERE seller_id='s'")).one()
            assert row == ('encrypted-legacy-key', None)
            assert conn.execute(text('SELECT count(*) FROM seller_oauth_states')).scalar()==0
            assert conn.execute(text('SELECT count(*) FROM email_outbox')).scalar()==0
            assert conn.execute(text("SELECT used FROM signup_quotas WHERE kind='ip'")).scalar_one()==2
            assert conn.execute(text('SELECT count(*) FROM users WHERE email_verification_required')).scalar()==0
            assert conn.execute(text('SELECT count(*) FROM users WHERE email_verified_at IS NOT NULL')).scalar()==0
        with Session(engine) as db:
            assert db.get(Asset,'a').price_inr_paise==0
            db.query(Subscription).first().status=SubscriptionStatus.PENDING
            db.commit()
        print('PASS: populated PostgreSQL legacy migration, Dodo/PENDING enums, preserved assets, invalidated unverified entitlements, ORM compatibility')
        engine.dispose()
    finally:
        subprocess.run([bin_dir+'pg_ctl','-D',str(cluster),'-m','immediate','-w','stop'],check=True,stdout=subprocess.DEVNULL)
