from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import bcrypt
import jwt
from backend.app.config import get_settings
from backend.app.core.exceptions import AuthenticationError

settings = get_settings()


def get_password_hash(password: str) -> str:
    """
    Hashes a plaintext password using bcrypt with salt rounds.
    Bcrypt has a 72-byte max length limit; input is UTF-8 encoded.
    """
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError(
            f"Password exceeds bcrypt maximum length of 72 UTF-8 bytes (received {len(password_bytes)} bytes)."
        )
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against an existing bcrypt hash.
    Safe against timing attacks.
    """
    try:
        password_bytes = plain_password.encode("utf-8")
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Encodes a JWT access token signed with HMAC-SHA256 (HS256).
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": now,
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and cryptographically validates a JWT access token.
    Raises AuthenticationError if expired, malformed, or signature invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "iat", "sub"]}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Authentication token has expired. Please log in again.")
    except (jwt.InvalidTokenError, jwt.MissingRequiredClaimError) as exc:
        raise AuthenticationError(f"Invalid authentication token: {exc}.")
