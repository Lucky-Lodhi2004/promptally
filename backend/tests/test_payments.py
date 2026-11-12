import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.models import Subscription, AssetPurchase
from backend.app.models.marketplace import SellerGatewayConfig, PendingCheckout, WebhookEvent
from backend.app.models.enums import SubscriptionStatus, UserTier, PurchaseStatus
from backend.app.services.crypto import decrypt_secret
from backend.app.services.geoip import detect_country
from backend.app.services.membership import is_pro
from backend.app.services.payments import verify_webhook


def auth(user): return {'Authorization':'Bearer '+create_access_token(user.id)}


@pytest.mark.parametrize('payment_status,remote_status,matching_reference,expected', [
    ('failed', 'failed', True, 200),
    ('succeeded', 'failed', True, 409),
    ('processing', 'failed', True, 409),
    ('failed', 'on_hold', True, 409),
    ('failed', 'active', True, 409),
    ('failed', 'failed', False, 409),
])
def test_retry_dodo_initial_failure_requires_provider_confirmation(
        client, users, db, provider, payment_status, remote_status, matching_reference, expected):
    calls, responses = provider
    buyer = users[1]
    headers = {**auth(buyer), 'CF-IPCountry': 'US'}
    assert client.post('/api/v1/billing/subscribe', headers=headers).status_code == 200
    sub = db.query(Subscription).filter_by(user_id=buyer.id).one()
    sub.status = SubscriptionStatus.PAST_DUE
    sub.gateway_subscription_id = 'failed-sub'
    old_reference = sub.checkout_reference
    db.commit()
    responses[('GET', 'dodo', '/checkouts/checkout_1')] = {'payment_status': payment_status}
    responses[('GET', 'dodo', '/subscriptions/failed-sub')] = {
        'status': remote_status, 'product_id': 'platform-product',
        'metadata': {'promptally_subscription_id': sub.id,
                     'promptally_checkout_reference': old_reference if matching_reference else 'other-checkout'},
    }
    responses[('POST', 'dodo', '/checkouts')] = {
        'session_id': 'checkout_2', 'checkout_url': 'https://checkout.dodopayments.com/fresh',
    }
    response = client.post('/api/v1/billing/subscribe', headers=headers)
    assert response.status_code == expected, response.text
    db.refresh(sub)
    assert not is_pro(buyer)
    assert db.query(Subscription).filter_by(user_id=buyer.id).count() == 1
    checkout_posts = [call for call in calls if call[:3] == ('POST', 'dodo', '/checkouts')]
    if expected == 200:
        assert response.json()['checkout_session_id'] == 'checkout_2'
        assert sub.checkout_reference != old_reference
        assert sub.status == SubscriptionStatus.PENDING
        assert len(checkout_posts) == 2
    else:
        assert sub.checkout_reference == old_reference
        assert sub.status == SubscriptionStatus.PAST_DUE
        assert len(checkout_posts) == 1


def signed(body, gateway, secret, event_id='event_1', stamp=None):
    raw=json.dumps(body,separators=(',',':')).encode()
    if gateway=='razorpay':
        headers={'x-razorpay-signature':hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest(),
                 'x-razorpay-event-id':event_id}
    else:
        stamp=str(stamp or int(time.time()))
        digest=hmac.new(base64.b64decode(secret.removeprefix('whsec_')),
                        event_id.encode()+b'.'+stamp.encode()+b'.'+raw,hashlib.sha256).digest()
        headers={'webhook-id':event_id,'webhook-timestamp':stamp,
                 'webhook-signature':'v1,'+base64.b64encode(digest).decode()}
    headers['Content-Type']='application/json'
    return raw,headers


def connect(client, seller, gateway):
    data={'gateway_type':gateway,'webhook_secret':'seller-hook','key_id':'seller-key','key_secret':'seller-secret'}
    if gateway=='dodo':
        data.update(api_key='seller-dodo-key',environment='test',webhook_secret='whsec_'+base64.b64encode(b'seller-dodo-hook').decode())
    response=client.post('/api/v1/sellers/connect',headers=auth(seller),json=data)
    assert response.status_code==200,response.text
    assert 'seller-secret' not in response.text and 'seller-dodo-key' not in response.text
    return data['webhook_secret']


@pytest.mark.parametrize('country,gateway,currency,amount',[('IN','razorpay','INR',8525),('US','dodo','USD',100)])
def test_subscription_checkout_is_pending(client,users,provider,db,country,gateway,currency,amount):
    buyer=users[1]
    response=client.post('/api/v1/billing/subscribe',headers={**auth(buyer),'CF-IPCountry':country})
    assert response.status_code==200,response.text
    data=response.json()
    assert (data['gateway'],data['currency'],data['amount'])==(gateway,currency,amount)
    assert data['status']=='pending'
    assert buyer.tier==UserTier.FREE and not is_pro(buyer)
    sub=db.query(Subscription).filter_by(user_id=buyer.id).one()
    assert sub.status==SubscriptionStatus.PENDING
    repeated = client.post('/api/v1/billing/subscribe', headers={**auth(buyer), 'CF-IPCountry': country})
    assert repeated.status_code == 200
    assert repeated.json() == data


def test_unknown_country_and_spoofed_headers_fail_closed(client,users,monkeypatch):
    monkeypatch.setattr(settings,'TRUSTED_PROXY_CIDRS',[])
    response=client.get('/api/v1/billing/quote',headers={'CF-IPCountry':'IN','X-Country-Code':'IN','X-Dev-Country':'IN'})
    assert response.status_code==503
    request=Request({'type':'http','client':('8.8.8.8',123),'headers':[(b'cf-ipcountry',b'IN')]})
    assert detect_country(request)==('ZZ',False)


@pytest.mark.parametrize('gateway',['razorpay','dodo'])
def test_platform_signed_activation_and_retry(client,users,provider,db,gateway):
    buyer=users[1];calls,responses=provider
    country='IN' if gateway=='razorpay' else 'US'
    assert client.post('/api/v1/billing/subscribe',headers={**auth(buyer),'CF-IPCountry':country}).status_code==200
    sub=db.query(Subscription).filter_by(user_id=buyer.id).one()
    end=datetime.now(timezone.utc)+timedelta(days=30)
    if gateway=='razorpay':
        event={'event':'subscription.charged','payload':{'subscription':{'entity':{'id':'sub_1'}},
               'payment':{'entity':{'status':'captured','amount':8525,'currency':'INR'}}}}
        remote={'id':'sub_1','plan_id':'plan_1','status':'active','current_end':int(end.timestamp())}
        secret=settings.RAZORPAY_WEBHOOK_SECRET
    else:
        meta={'promptally_subscription_id':sub.id,'promptally_checkout_reference':sub.checkout_reference}
        event={'type':'subscription.active','data':{'subscription_id':'sub_1','metadata':meta}}
        remote={'subscription_id':'sub_1','product_id':'platform-product','status':'active',
            'metadata':meta,'currency':'USD','recurring_pre_tax_amount':100,'next_billing_date':end.isoformat()}
        secret=settings.DODO_WEBHOOK_SECRET
    responses[('GET',gateway,'/subscriptions/sub_1')]=remote
    body,headers=signed(event,gateway,secret)
    for _ in range(2):
        response=client.post('/api/v1/webhooks/'+gateway,content=body,headers=headers)
        assert response.status_code==200,response.text
    assert is_pro(buyer) and buyer.tier==UserTier.PRO
    assert db.query(WebhookEvent).count()==1
    assert len([c for c in calls if c[0]=='GET' and c[2]=='/subscriptions/sub_1'])==1


@pytest.mark.parametrize('gateway',['razorpay','dodo'])
def test_missing_signature_rejected(client,gateway):
    assert client.post('/api/v1/webhooks/'+gateway,json={}).status_code==401


def test_expired_dodo_signature_rejected(client):
    body,headers=signed({'type':'subscription.active'},'dodo',settings.DODO_WEBHOOK_SECRET,stamp=int(time.time())-301)
    assert client.post('/api/v1/webhooks/dodo',content=body,headers=headers).status_code==401


def test_expired_membership_cannot_sell_or_create_collections(client,users,asset,db,provider):
    seller=users[0];seller.subscription.current_period_end=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    assert client.post('/api/v1/collections',headers=auth(seller),data={'title':'Expired'}).status_code==403
    assert client.post('/api/v1/assets/'+asset.slug+'/buy',headers={**auth(users[1]),'CF-IPCountry':'IN'}).status_code==409


@pytest.mark.parametrize('gateway',['razorpay','dodo'])
def test_direct_purchase_uses_seller_keys_and_only_signed_payment_unlocks(client,users,asset,db,provider,gateway):
    calls,responses=provider;seller,buyer=users
    secret=connect(client,seller,gateway)
    config=db.get(SellerGatewayConfig,seller.id)
    if gateway=='razorpay':
        assert config.razorpay_key_secret_enc!='seller-secret'
        assert decrypt_secret(config.razorpay_key_secret_enc)=='seller-secret'
    result=client.post('/api/v1/assets/'+asset.slug+'/buy',headers={**auth(buyer),'CF-IPCountry':'IN' if gateway=='razorpay' else 'US'})
    assert result.status_code==200,result.text
    assert db.query(AssetPurchase).count()==0
    assert client.get('/api/v1/assets/'+asset.slug,headers=auth(buyer)).json()['raw_content'] is None
    checkout=db.query(PendingCheckout).one()
    checkout_call=[c for c in calls if c[0]=='POST' and c[2] in ('/orders','/checkouts')][-1]
    assert checkout_call[3]['key']==('seller-key' if gateway=='razorpay' else 'seller-dodo-key')
    if gateway=='razorpay':
        event={'event':'order.paid','payload':{'payment':{'entity':{'id':'pay_1','order_id':'order_1'}}}}
        payment={'id':'pay_1','order_id':'order_1','status':'captured','captured':True,'amount':42625,'currency':'INR'}
    else:
        event={'type':'payment.succeeded','data':{'payment_id':'pay_1','checkout_session_id':'checkout_1'}}
        payment={'payment_id':'pay_1','checkout_session_id':'checkout_1','status':'succeeded',
            'total_amount':500,'currency':'USD','product_cart':[{'product_id':'seller-product','quantity':1}]}
    responses[('GET',gateway,'/payments/pay_1')]=payment
    body,headers=signed(event,gateway,secret)
    path=f'/api/v1/webhooks/{gateway}/{seller.id}'
    assert client.post(path,content=body).status_code==401
    for _ in range(2):
        response=client.post(path,content=body,headers=headers)
        assert response.status_code==200,response.text
    purchase=db.query(AssetPurchase).one()
    assert purchase.status==PurchaseStatus.COMPLETED and purchase.platform_fee_cents==0
    assert purchase.seller_payout_cents==checkout.expected_amount_minor
    assert client.get('/api/v1/assets/'+asset.slug,headers=auth(buyer)).json()['raw_content']=='SECRET PAYLOAD'
    assert client.get('/api/v1/assets/'+asset.slug+'/download',headers=auth(buyer)).content==b'SECRET PAYLOAD'
    # Buyer rights persist independently of the seller's subscription.
    seller.subscription.status=SubscriptionStatus.CANCELED;db.commit()
    assert client.get('/api/v1/assets/'+asset.slug+'/download',headers=auth(buyer)).status_code==200


@pytest.mark.parametrize('field,value',[('amount',1),('currency','USD'),('status','authorized'),('order_id','another-order')])
def test_wrong_payment_cannot_unlock(client,users,asset,provider,db,field,value):
    secret=connect(client,users[0],'razorpay')
    client.post('/api/v1/assets/'+asset.slug+'/buy',headers={**auth(users[1]),'CF-IPCountry':'IN'})
    event={'event':'order.paid','payload':{'payment':{'entity':{'id':'pay_1','order_id':'order_1'}}}}
    payment={'id':'pay_1','order_id':'order_1','status':'captured','captured':True,'amount':42625,'currency':'INR'}
    payment[field]=value;provider[1][('GET','razorpay','/payments/pay_1')]=payment
    body,headers=signed(event,'razorpay',secret)
    assert client.post('/api/v1/webhooks/razorpay/seller',content=body,headers=headers).status_code==400
    assert db.query(AssetPurchase).count()==0
    db.rollback()  # The request's dependency normally rolls back on close.
    assert db.query(WebhookEvent).count()==0


def test_paid_content_private_cache_markdown_and_archives(client,users,asset):
    assert 'SECRET PAYLOAD' not in client.get('/api/v1/assets/'+asset.slug+'.md').text
    assert client.get('/api/v1/assets/'+asset.slug+'/download').status_code==403
    response=client.get('/api/v1/assets/'+asset.slug,headers=auth(users[0]))
    assert response.json()['raw_content']=='SECRET PAYLOAD'
    assert response.headers['cache-control']=='private, no-store'
    assert client.get('/uploads/archives/private.md').status_code==404


def test_seller_must_connect_region_gateway(client,users,asset,provider):
    connect(client,users[0],'razorpay')
    assert client.post('/api/v1/assets/'+asset.slug+'/buy',headers={**auth(users[1]),'CF-IPCountry':'US'}).status_code==409


def test_cancel_calls_provider_and_keeps_paid_period(client,users,provider):
    provider[1][('POST','razorpay','/subscriptions/sub_existing/cancel')]={'id':'sub_existing','status':'active'}
    response=client.post('/api/v1/billing/cancel',headers=auth(users[0]))
    assert response.status_code==200,response.text
    assert is_pro(users[0]) and users[0].subscription.cancel_at_period_end
    assert provider[0][-1][3]['payload']=={'cancel_at_cycle_end':1}


def test_google_unsigned_fallback_is_disabled(client,monkeypatch):
    monkeypatch.setattr(settings,'GOOGLE_CLIENT_ID','')
    response=client.post('/api/v1/auth/google',json={'credential':'a.eyJlbWFpbCI6ImFkbWluQGV4YW1wbGUuY29tIn0.c'})
    assert response.status_code==503


def test_paid_publishing_creates_product_in_seller_account(client,users,asset,provider,db):
    import base64
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
    connect(client,users[0],'dodo')
    response=client.post('/api/v1/assets',headers=auth(users[0]),data={
        'heading':'New premium artifact','section_slug':'prompts','category_slug':'system-base-contexts',
        'raw_text':'A private prompt with useful content','is_paid':'true','price_usd':'3.00'},
        files={'image':('preview.png',png,'image/png')})
    assert response.status_code==201,response.text
    from backend.app.models import Asset
    saved=db.get(Asset,response.json()['asset_id'])
    assert saved.price_cents==300 and saved.price_inr_paise==25575
    assert saved.seller_dodo_product_id=='seller-product'
    call=[c for c in provider[0] if c[0]=='POST' and c[2]=='/products'][-1]
    assert call[3]['key']=='seller-dodo-key'
    assert call[3]['payload']['price']['price']==300


def test_razorpay_activation_without_captured_charge_never_grants_pro(client,users,provider,db):
    buyer=users[1]
    client.post('/api/v1/billing/subscribe',headers={**auth(buyer),'CF-IPCountry':'IN'})
    provider[1][('GET','razorpay','/subscriptions/sub_1')]={'id':'sub_1','plan_id':'plan_1','status':'active',
        'current_end':int((datetime.now(timezone.utc)+timedelta(days=30)).timestamp())}
    event={'event':'subscription.activated','payload':{'subscription':{'entity':{'id':'sub_1'}}}}
    body,headers=signed(event,'razorpay',settings.RAZORPAY_WEBHOOK_SECRET)
    assert client.post('/api/v1/webhooks/razorpay',content=body,headers=headers).status_code==200
    assert not is_pro(buyer)


def test_out_of_order_subscription_event_uses_current_provider_state(client,users,provider):
    seller=users[0]
    provider[1][('GET','razorpay','/subscriptions/sub_existing')]={'id':'sub_existing','plan_id':None,'status':'cancelled'}
    event={'event':'subscription.charged','payload':{'subscription':{'entity':{'id':'sub_existing'}},
        'payment':{'entity':{'status':'captured','amount':100,'currency':'USD'}}}}
    body,headers=signed(event,'razorpay',settings.RAZORPAY_WEBHOOK_SECRET)
    assert client.post('/api/v1/webhooks/razorpay',content=body,headers=headers).status_code==200
    assert not is_pro(seller)


def test_local_mmdb_lookup_uses_actual_ip(client,monkeypatch):
    from backend.app.services.geoip import detect_country
    from types import SimpleNamespace
    import geoip2.database
    seen=[]
    class Reader:
        def __init__(self,path): seen.append(path)
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def country(self,ip):
            seen.append(ip)
            return SimpleNamespace(country=SimpleNamespace(iso_code='IN'))
    monkeypatch.setattr(geoip2.database,'Reader',Reader)
    monkeypatch.setattr(settings,'GEOIP_DATABASE_PATH','/test/GeoLite2-Country.mmdb')
    request=Request({'type':'http','client':('8.8.8.8',123),'headers':[(b'cf-ipcountry',b'US')]})
    assert detect_country(request)==('IN',True)
    assert seen==['/test/GeoLite2-Country.mmdb','8.8.8.8']


def test_forged_dodo_signature_and_webhook_body_tampering(client):
    body,headers=signed({'type':'subscription.active'},'dodo',settings.DODO_WEBHOOK_SECRET)
    assert client.post('/api/v1/webhooks/dodo',content=body+b' ',headers=headers).status_code==401


def test_provider_adapter_never_exposes_error_body(monkeypatch):
    import httpx
    from backend.app.services.payments import gateway_request
    original=httpx.Client
    seen=[]
    def handle(request):
        seen.append(request)
        return httpx.Response(401,json={'error':'secret-sensitive-provider-body'})
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(handle)))
    with pytest.raises(HTTPException) as err:
        gateway_request('POST','razorpay','/orders',key='seller-key',secret='seller-secret',payload={'amount':500})
    assert err.value.status_code==502
    assert 'secret-sensitive' not in err.value.detail
    assert seen[0].url.host=='api.razorpay.com'
    assert seen[0].headers['authorization']=='Basic '+base64.b64encode(b'seller-key:seller-secret').decode()


def test_fx_feed_rounding_and_cache(client,monkeypatch):
    import httpx
    from backend.app.services import payments
    monkeypatch.setattr(settings,'USD_TO_INR_RATE','')
    monkeypatch.setattr(payments,'_fx_cache',(0,0))
    original=httpx.Client
    calls=[]
    def handle(request):
        calls.append(request)
        assert request.url.params['base']=='USD' and request.url.params['symbols']=='INR'
        return httpx.Response(200,json={'rates':{'INR':85.255}})
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(handle)))
    assert payments.inr_paise()==8526
    assert payments.inr_paise(500)==42628
    assert len(calls)==1


def test_fx_feed_failure_does_not_guess_price(client,monkeypatch):
    import httpx
    from backend.app.services import payments
    monkeypatch.setattr(settings,'USD_TO_INR_RATE','')
    monkeypatch.setattr(payments,'_fx_cache',(0,0))
    original=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(lambda request:httpx.Response(503))))
    with pytest.raises(HTTPException) as error:
        payments.inr_paise()
    assert error.value.status_code==503


def test_pending_subscription_returns_resume_fields(client, users, provider):
    headers={**auth(users[1]),'CF-IPCountry':'IN'}
    started=client.post('/api/v1/billing/subscribe',headers=headers)
    assert started.status_code==200
    resumed=client.get('/api/v1/billing/subscription',headers=headers).json()
    assert resumed['is_pro'] is False
    assert resumed['subscription']['status']=='PENDING'
    assert resumed['subscription']['subscription_id']==started.json()['subscription_id']
    assert resumed['subscription']['key_id']==started.json()['key_id']
    assert resumed['subscription']['checkout_url']==started.json()['checkout_url']
