import httpx
from datetime import datetime, timezone
from app.integrations.kis.constants import REAL_BASE_URL, PAPER_BASE_URL, TOKEN_PATH


class KISTokenManager:
    """Manages KIS API access tokens with caching."""

    def __init__(self, app_key: str, app_secret: str, is_paper: bool = True):
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = PAPER_BASE_URL if is_paper else REAL_BASE_URL
        self._token: str | None = None
        self._token_expires: datetime | None = None

    async def get_token(self) -> str:
        if self._token and self._token_expires and datetime.now(timezone.utc) < self._token_expires:
            return self._token

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

        self._token = data["access_token"]
        # Token expires in ~24h, refresh at 23h
        self._token_expires = datetime.now(timezone.utc).replace(hour=23, minute=0, second=0)
        return self._token

    @property
    def headers(self) -> dict:
        return {
            "authorization": f"Bearer {self._token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "content-type": "application/json; charset=utf-8",
        }
