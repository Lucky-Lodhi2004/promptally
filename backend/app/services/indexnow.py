import logging
import httpx
from typing import List, Union
from urllib.parse import urlsplit
from backend.app.core.config import settings

logger = logging.getLogger("promptally.indexnow")

INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"

async def submit_urls_to_indexnow(urls: Union[str, List[str]]) -> bool:
    """
    Submits newly created or modified URLs to IndexNow for instant search engine indexing.
    Called asynchronously via FastAPI BackgroundTasks.
    """
    if isinstance(urls, str):
        url_list = [urls]
    else:
        url_list = urls

    if not url_list:
        return False

    payload = {
        "host": urlsplit(settings.SITE_URL).hostname,
        "key": settings.INDEXNOW_KEY,
        "keyLocation": f"{settings.SITE_URL}/{settings.INDEXNOW_KEY}.txt",
        "urlList": url_list
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(INDEXNOW_ENDPOINT, json=payload)
            if resp.status_code in (200, 202):
                logger.info(f"IndexNow submitted {len(url_list)} URLs successfully.")
                return True
            else:
                logger.warning(f"IndexNow returned status {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Failed to submit to IndexNow: {e}")
        return False

