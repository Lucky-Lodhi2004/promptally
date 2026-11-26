from backend.app.core.config import settings
from backend.app.services import analytics


def test_capture_event_noop_when_api_key_empty(monkeypatch):
    monkeypatch.setattr(settings, "POSTHOG_API_KEY", "")
    created = []
    monkeypatch.setattr(analytics, "Posthog", lambda **kw: created.append(kw))
    analytics.capture_event("user-1", "test_event", {"plan": "pro"})
    assert created == []


def test_capture_event_uses_v6_kwargs_and_swallows_errors(monkeypatch):
    calls = []
    shutdowns = []

    class FakePosthog:
        def __init__(self, project_api_key, host):
            self.project_api_key = project_api_key
            self.host = host

        def capture(self, *, event, distinct_id, properties):
            calls.append((event, distinct_id, properties))
            if event == "boom":
                raise RuntimeError("network down")

        def shutdown(self):
            shutdowns.append(True)

    monkeypatch.setattr(settings, "POSTHOG_API_KEY", "phc_test_key")
    monkeypatch.setattr(settings, "POSTHOG_HOST", "https://us.i.posthog.com")
    monkeypatch.setattr(analytics, "Posthog", FakePosthog)

    analytics.capture_event("user-42", "asset_published", {"slug": "my-skill", "empty": None})
    analytics.capture_event("user-42", "boom", {"ok": True})
    analytics.shutdown_analytics()

    assert calls == [
        ("asset_published", "user-42", {"slug": "my-skill", "source": "backend"}),
        ("boom", "user-42", {"ok": True, "source": "backend"}),
    ]
    assert shutdowns == [True]


def test_mcp_tool_call_emits_analytics_event(client, mcp_access, asset, monkeypatch):
    from backend.app.api.v1.endpoints import seo_aeo

    captured = []
    monkeypatch.setattr(seo_aeo, "capture_event", lambda uid, ev, props=None: captured.append((uid, ev, props)))

    resp = client.post(
        "/api/v1/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "search_promptally", "arguments": {"query": "Paid"}},
        },
    )
    assert resp.status_code == 200
    assert len(captured) == 1
    uid, ev, props = captured[0]
    assert uid == "buyer"
    assert ev == "mcp_tool_called"
    assert props["tool_name"] == "search_promptally"
    assert props["is_error"] is False

