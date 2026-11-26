"""Best-effort server-side PostHog analytics.

Never raises into application code and stays completely inactive when
POSTHOG_API_KEY is empty (such as in isolated automated tests).
"""
import logging
import threading
from typing import Any, Dict, Optional

from backend.app.core.config import settings

try:
    from posthog import Posthog
except ImportError:  # pragma: no cover
    Posthog = None

log = logging.getLogger(__name__)
_lock = threading.Lock()
_client: Any = None
_client_key: Optional[str] = None
_client_host: Optional[str] = None


def _get_client() -> Any:
    global _client, _client_key, _client_host
    api_key = (settings.POSTHOG_API_KEY or "").strip()
    if not api_key or Posthog is None:
        return None
    host = (settings.POSTHOG_HOST or "https://us.i.posthog.com").strip()
    with _lock:
        if _client is None or _client_key != api_key or _client_host != host:
            if _client is not None:
                try:
                    _client.shutdown()
                except Exception:
                    pass
            _client = Posthog(project_api_key=api_key, host=host)
            _client_key = api_key
            _client_host = host
        return _client


def capture_event(
    distinct_id: str,
    event: str,
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """Queue a server-side PostHog event; failures are swallowed safely."""
    if not distinct_id or not event:
        return
    client = _get_client()
    if client is None:
        return
    try:
        props = {k: v for k, v in (properties or {}).items() if v is not None}
        props.setdefault("source", "backend")
        client.capture(event=event, distinct_id=str(distinct_id), properties=props)
    except Exception:
        log.debug("PostHog capture failed for event %s", event, exc_info=True)


def shutdown_analytics() -> None:
    """Flush and close the PostHog client on application shutdown."""
    global _client, _client_key, _client_host
    with _lock:
        client = _client
        _client = None
        _client_key = None
        _client_host = None
    if client is not None:
        try:
            client.shutdown()
        except Exception:
            log.debug("PostHog shutdown failed", exc_info=True)

