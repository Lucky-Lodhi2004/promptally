"""Exercise cancellation with isolated storage and mocked provider responses."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from backend.app.api.v1.endpoints import billing
from backend.app.models.enums import SubscriptionGateway, SubscriptionStatus
from backend.app.services.membership import is_pro


@pytest.fixture
def cancellation(db, users, monkeypatch):
    user = users[0]
    sub = user.subscription
    calls = []
    response = {}

    def request(method, gateway, path, payload=None):
        calls.append((method, gateway, path, payload))
        if isinstance(response.get("error"), Exception):
            raise response["error"]
        return response

    monkeypatch.setattr(billing, "platform_request", request)
    return db, user, sub, calls, response


@pytest.mark.parametrize("gateway", ["razorpay", "dodo"])
def test_schedule_preserves_paid_period_and_repeat_does_not_charge_provider(cancellation, gateway):
    db, user, sub, calls, remote = cancellation
    sub.gateway = SubscriptionGateway(gateway.upper())
    end = sub.current_period_end
    key = "id" if gateway == "razorpay" else "subscription_id"
    remote.update({key: sub.gateway_subscription_id, "status": "active", "cancel_at_next_billing_date": True})
    db.commit()

    assert billing.cancel_subscription(db, user).status == "success"
    assert is_pro(user) and sub.cancel_at_period_end
    assert sub.current_period_end == end
    expected_payload = {"cancel_at_cycle_end": 1} if gateway == "razorpay" else {"cancel_at_next_billing_date": True}
    assert calls == [("POST" if gateway == "razorpay" else "PATCH", gateway,
                      f"/subscriptions/{sub.gateway_subscription_id}" + ("/cancel" if gateway == "razorpay" else ""), expected_payload)]
    assert billing.cancel_subscription(db, user).status == "success"
    assert len(calls) == 1
    sub.current_period_end = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert not is_pro(user)


@pytest.mark.parametrize("gateway", ["razorpay", "dodo"])
@pytest.mark.parametrize("bad_response", ["wrong-id", "missing-status", "not-cancelled", "provider-error"])
def test_unconfirmed_cancellation_does_not_change_local_access(cancellation, gateway, bad_response):
    db, user, sub, calls, remote = cancellation
    sub.gateway = SubscriptionGateway(gateway.upper())
    key = "id" if gateway == "razorpay" else "subscription_id"
    remote.update({key: sub.gateway_subscription_id, "status": "active", "cancel_at_next_billing_date": True})
    if bad_response == "wrong-id":
        remote[key] = "another-subscription"
    elif bad_response == "missing-status":
        remote.pop("status")
    elif bad_response == "not-cancelled":
        if gateway == "dodo":
            remote["cancel_at_next_billing_date"] = False
        else:
            remote["status"] = "halted"
    else:
        remote["error"] = HTTPException(502, "Provider unavailable")
    db.commit()

    with pytest.raises(HTTPException) as error:
        billing.cancel_subscription(db, user)
    assert error.value.status_code == 502
    assert not sub.cancel_at_period_end
    assert sub.status == SubscriptionStatus.ACTIVE and is_pro(user)


@pytest.mark.parametrize("gateway", ["razorpay", "dodo"])
def test_unpaid_subscription_is_cancelled_immediately(cancellation, gateway):
    db, user, sub, calls, remote = cancellation
    sub.gateway = SubscriptionGateway(gateway.upper())
    sub.status = SubscriptionStatus.PAST_DUE
    key = "id" if gateway == "razorpay" else "subscription_id"
    remote.update({key: sub.gateway_subscription_id, "status": "cancelled"})
    db.commit()

    assert billing.cancel_subscription(db, user).status == "success"
    assert sub.status == SubscriptionStatus.CANCELED
    assert not sub.cancel_at_period_end and not is_pro(user)
    assert calls[-1][-1] == ({"cancel_at_cycle_end": 0} if gateway == "razorpay" else {"status": "cancelled"})
    billing.cancel_subscription(db, user)
    assert len(calls) == 1


def test_pending_checkout_without_subscription_stays_bound(cancellation):
    db, user, sub, calls, remote = cancellation
    sub.gateway = SubscriptionGateway.DODO
    sub.status = SubscriptionStatus.PENDING
    sub.gateway_subscription_id = None
    sub.checkout_session_id = "pending-checkout"
    db.commit()
    with pytest.raises(HTTPException) as error:
        billing.cancel_subscription(db, user)
    assert error.value.status_code == 409
    assert sub.checkout_session_id == "pending-checkout"
    assert sub.status == SubscriptionStatus.PENDING
    assert not calls


@pytest.mark.parametrize("gateway", ["razorpay", "dodo"])
def test_terminal_webhook_clears_scheduled_flag(cancellation, gateway):
    db, user, sub, calls, remote = cancellation
    sub.gateway = SubscriptionGateway(gateway.upper())
    sub.cancel_at_period_end = True
    sub.gateway_plan_id = "plan"
    sub.checkout_reference = "reference"
    remote.update({"status": "cancelled", "plan_id": "plan", "product_id": "plan",
                   "metadata": {"promptally_checkout_reference": "reference"},
                   "currency": "USD", "recurring_pre_tax_amount": 100})
    db.commit()
    event = ({"event": "subscription.cancelled", "payload": {"subscription": {"entity": {"id": sub.gateway_subscription_id}}}}
             if gateway == "razorpay" else
             {"type": "subscription.cancelled", "data": {"subscription_id": sub.gateway_subscription_id}})
    billing.apply_subscription_event(db, gateway, event)
    assert sub.status == SubscriptionStatus.CANCELED
    assert not sub.cancel_at_period_end and not is_pro(user)
