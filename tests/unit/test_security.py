from datetime import timedelta
import pytest
from backend.app.core.exceptions import AuthenticationError
from backend.app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


def test_password_hashing_and_verification():
    raw_password = "SecureDevOpsPassword!2026"
    hashed = get_password_hash(raw_password)

    # Hash should not equal raw password
    assert hashed != raw_password
    assert hashed.startswith("$2b$")

    # Verification should succeed for correct password
    assert verify_password(raw_password, hashed) is True

    # Verification should fail for incorrect password
    assert verify_password("WrongPassword123", hashed) is False


def test_password_72_byte_utf8_limit():
    """
    Bcrypt has a strict 72-byte limit. Multibyte UTF-8 characters (like emojis 4 bytes each)
    must be counted by bytes, not character count.
    """
    # 1. Exactly 72 ASCII bytes should succeed
    exact_72_ascii = "A" * 72
    hashed = get_password_hash(exact_72_ascii)
    assert verify_password(exact_72_ascii, hashed) is True

    # 2. 73 ASCII bytes should be rejected
    too_long_ascii = "A" * 73
    with pytest.raises(ValueError) as exc_info:
        get_password_hash(too_long_ascii)
    assert "exceeds bcrypt maximum length of 72 UTF-8 bytes" in str(exc_info.value)

    # 3. Multibyte characters: '🔒' is 4 bytes in UTF-8
    # 18 emojis = 18 * 4 = 72 bytes -> Valid
    valid_multibyte = "🔒" * 18
    assert len(valid_multibyte.encode("utf-8")) == 72
    hashed_mb = get_password_hash(valid_multibyte)
    assert verify_password(valid_multibyte, hashed_mb) is True

    # 19 emojis = 19 * 4 = 76 bytes (even though only 19 characters!) -> Must be rejected
    invalid_multibyte = "🔒" * 19
    assert len(invalid_multibyte.encode("utf-8")) == 76
    with pytest.raises(ValueError) as exc_info:
        get_password_hash(invalid_multibyte)
    assert "exceeds bcrypt maximum length of 72 UTF-8 bytes" in str(exc_info.value)


def test_jwt_token_creation_and_decoding():
    payload_data = {
        "sub": "user_12345",
        "email": "devops@company.com",
        "role": "engineer"
    }

    token = create_access_token(data=payload_data)
    assert isinstance(token, str)

    decoded = decode_access_token(token)
    assert decoded["sub"] == "user_12345"
    assert decoded["email"] == "devops@company.com"
    assert decoded["role"] == "engineer"
    assert "exp" in decoded
    assert "iat" in decoded


def test_jwt_token_expired():
    payload_data = {"sub": "user_expired", "role": "viewer"}
    # Create token already expired in the past
    token = create_access_token(data=payload_data, expires_delta=timedelta(seconds=-10))

    with pytest.raises(AuthenticationError) as exc_info:
        decode_access_token(token)

    assert "expired" in str(exc_info.value.message).lower()


def test_jwt_token_invalid_signature():
    valid_token = create_access_token(data={"sub": "user_tampered"})
    # Tamper with the signature
    parts = valid_token.split(".")
    tampered_sig = parts[2][:-1] + ("A" if parts[2][-1] != "A" else "B")
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    with pytest.raises(AuthenticationError) as exc_info:
        decode_access_token(tampered_token)

    assert "invalid authentication token" in str(exc_info.value.message).lower()


def test_jwt_missing_required_claims():
    """
    Token without required 'sub' claim should fail validation.
    """
    # Create token missing 'sub'
    token_missing_sub = create_access_token(data={"role": "admin"})

    with pytest.raises(AuthenticationError) as exc_info:
        decode_access_token(token_missing_sub)

    assert "missing" in str(exc_info.value.message).lower()
