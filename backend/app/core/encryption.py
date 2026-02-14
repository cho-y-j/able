from cryptography.fernet import Fernet, MultiFernet
from functools import lru_cache
from app.config import get_settings


class KeyVault:
    """Manages Fernet encryption for API keys stored in the database."""

    def __init__(self):
        settings = get_settings()
        if not settings.encryption_key:
            raise RuntimeError(
                "ENCRYPTION_KEY environment variable is required. "
                "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        keys = [Fernet(settings.encryption_key.encode())]
        self._fernet = MultiFernet(keys)

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        return self._fernet.decrypt(ciphertext).decode("utf-8")

    def rotate(self, ciphertext: bytes) -> bytes:
        return self._fernet.rotate(ciphertext)


@lru_cache(maxsize=1)
def get_vault() -> KeyVault:
    return KeyVault()
