# backend/hashing.py
from passlib.context import CryptContext

# OWASP recommends >= 310,000 rounds for PBKDF2-SHA256
_pwd = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
    pbkdf2_sha256__default_rounds=310_000,
)

class Hash:
    @staticmethod
    def encrypt(password: str) -> str:
        # optional hard cap to prevent DoS via huge inputs
        return _pwd.hash(password[:4096])

    @staticmethod
    def verify(plain_password: str, hashed_password: str) -> bool:
        return _pwd.verify(plain_password, hashed_password)

    @staticmethod
    def needs_update(hashed_password: str) -> bool:
        return _pwd.needs_update(hashed_password)
