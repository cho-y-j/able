import asyncio
import logging
import httpx
from datetime import datetime, timedelta, timezone
from app.integrations.kis.constants import REAL_BASE_URL, PAPER_BASE_URL, TOKEN_PATH

logger = logging.getLogger("able.kis.auth")

# Global token cache: (app_key, is_paper) → {"token", "expires", "lock"}
_token_cache: dict[tuple[str, bool], dict] = {}


class KISTokenManager:
    """Manages KIS API access tokens with global cross-instance caching.

    KIS enforces a strict rate limit of 1 token request per minute.
    This manager uses a module-level cache keyed by (app_key, is_paper)
    so that all KISClient instances sharing the same credentials reuse
    a single token without redundant OAuth calls.
    """

    def __init__(self, app_key: str, app_secret: str, is_paper: bool = True):
        self.app_key = app_key
        self.app_secret = app_secret
        self.is_paper = is_paper
        self.base_url = PAPER_BASE_URL if is_paper else REAL_BASE_URL
        self._cache_key = (app_key, is_paper)

    async def get_token(self) -> str:
        entry = _token_cache.get(self._cache_key)

        # Return cached token if still valid
        if entry and entry["token"] and entry["expires"] > datetime.now(timezone.utc):
            return entry["token"]

        # Ensure only one coroutine fetches a new token at a time
        if not entry or "lock" not in entry:
            _token_cache[self._cache_key] = {
                "token": None,
                "expires": datetime.min.replace(tzinfo=timezone.utc),
                "lock": asyncio.Lock(),
            }
            entry = _token_cache[self._cache_key]

        async with entry["lock"]:
            # Double-check after acquiring lock (another coroutine may have refreshed)
            if entry["token"] and entry["expires"] > datetime.now(timezone.utc):
                return entry["token"]

            logger.info("Requesting new KIS token for %s (paper=%s)", self.app_key[:8], self.is_paper)
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}{TOKEN_PATH}",
                    json={
                        "grant_type": "client_credentials",
                        "appkey": self.app_key,
                        "appsecret": self.app_secret,
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

            token = data["access_token"]
            # KIS tokens are valid for ~24h. Refresh 1 hour before expiry.
            expires_at = datetime.now(timezone.utc) + timedelta(hours=23)

            entry["token"] = token
            entry["expires"] = expires_at

            logger.info("KIS token cached, expires at %s", expires_at.isoformat())
            return token

    @property
    def headers(self) -> dict:
        entry = _token_cache.get(self._cache_key)
        token = entry["token"] if entry else None
        return {
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "content-type": "application/json; charset=utf-8",
        }


def clear_token_cache():
    """Clear the global token cache. Useful for testing or key rotation."""
    _token_cache.clear()
    logger.info("KIS token cache cleared")
