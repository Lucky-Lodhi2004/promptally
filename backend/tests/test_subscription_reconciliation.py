from datetime import datetime, timedelta, timezone
import pytest
from backend.app.models import Subscription
from backend.app.services.membership import is_pro
from backend.app.core.config import settings
from backend.tests.test_payments import auth, signed


@pytest.fixture
def paid_subscription(client, users, provider, db):
    buyer = users[1]
    assert client.post('/api/v1/billing/subscribe', headers={**auth(buyer), 'CF-IPCountry': 'IN'}).status_code == 200
    sub = db.query(Subscription).filter_by(user_id=buyer.id).one()
    start = int(datetime.now(timezone.utc).timestamp())
    end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
    remote = {'id': 'sub_1', 'plan_id': 'plan_1', 'status': 'active',
              'current_start': start, 'current_end': end,
              'notes': {'promptally_subscription_id': sub.id, 'promptally_checkout_reference': sub.checkout_reference}}
    invoice = {'id': 'inv_1', 'payment_id': 'pay_1', 'subscription_id': 'sub_1',
               'status': 'paid', 'amount': 8525, 'amount_paid': 8525, 'currency': 'INR',
               'billing_start': start, 'billing_end': end}
    payment = {'id': 'pay_1', 'invoice_id': 'inv_1', 'status': 'captured', 'captured': True,
               'amount': 8525, 'currency': 'INR', 'amount_refunded': 0}
    provider[1].update({
        ('GET', 'razorpay', '/subscriptions/sub_1'): remote,
        ('GET', 'razorpay', '/invoices?subscription_id=sub_1&count=100&skip=0'): {'items': [invoice]},
        ('GET', 'razorpay', '/payments/pay_1'): payment,
    })
    return buyer, sub, remote, invoice, payment


def test_status_check_recovers_paid_subscription_without_webhook(client, paid_subscription, provider):
    buyer, sub, *_ = paid_subscription
    assert not is_pro(buyer)
    result = client.post('/api/v1/billing/verify', headers=auth(buyer))
    assert result.status_code == 200, result.text
    assert result.json()['is_pro'] and result.json()['subscription']['status'] == 'ACTIVE'
    assert is_pro(buyer)
    calls = len(provider[0])
    assert client.post('/api/v1/billing/verify', headers=auth(buyer)).json()['is_pro']
    assert len(provider[0]) == calls  # Already active; no duplicate provider work.


def test_activation_event_recovers_capture_even_without_payment_entity(client, paid_subscription):
    buyer, *_ = paid_subscription
    event = {'event': 'subscription.activated', 'payload': {'subscription': {'entity': {'id': 'sub_1'}}}}
    body, headers = signed(event, 'razorpay', settings.RAZORPAY_WEBHOOK_SECRET)
    assert client.post('/api/v1/webhooks/razorpay', content=body, headers=headers).status_code == 200
    assert is_pro(buyer)


@pytest.mark.parametrize('scenario', ['no-invoice', 'old-cycle', 'wrong-subscription', 'wrong-reference',
    'invoice-amount', 'invoice-currency', 'authorized', 'refunded', 'payment-amount', 'wrong-invoice'])
def test_unverified_payment_never_activates_pro(client, paid_subscription, provider, scenario):
    buyer, sub, remote, invoice, payment = paid_subscription
    if scenario == 'no-invoice':
        provider[1][('GET', 'razorpay', '/invoices?subscription_id=sub_1&count=100&skip=0')] = {'items': []}
    elif scenario == 'old-cycle': invoice['billing_end'] -= 86400
    elif scenario == 'wrong-subscription': invoice['subscription_id'] = 'another-sub'
    elif scenario == 'wrong-reference': remote['notes']['promptally_checkout_reference'] = 'another-reference'
    elif scenario == 'invoice-amount': invoice['amount_paid'] = 1
    elif scenario == 'invoice-currency': invoice['currency'] = 'USD'
    elif scenario == 'authorized': payment['status'] = 'authorized'
    elif scenario == 'refunded': payment['amount_refunded'] = 1
    elif scenario == 'payment-amount': payment['amount'] = 1
    elif scenario == 'wrong-invoice': payment['invoice_id'] = 'inv_other'
    result = client.post('/api/v1/billing/verify', headers=auth(buyer))
    assert result.status_code == 200 and not result.json()['is_pro']
    assert not is_pro(buyer)


def test_verify_only_checks_authenticated_users_subscription(client, paid_subscription, users, provider):
    buyer, *_ = paid_subscription
    calls = len(provider[0])
    assert client.post('/api/v1/billing/verify').status_code == 401
    assert client.post('/api/v1/billing/verify', headers=auth(users[0])).json()['is_pro']
    assert len(provider[0]) == calls
    assert not is_pro(buyer)
