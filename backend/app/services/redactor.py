import re
from typing import List, Pattern, Tuple


class SecretRedactor:
    """
    Sanitizes log messages, stack traces, and evidence before sending to external LLM providers.
    Redacts credentials, tokens, connection strings, and sensitive keys while preserving
    technical diagnostics, exception types, HTTP endpoints, and error codes.
    """

    _PATTERNS: List[Tuple[Pattern[str], str]] = [
        # 1. Private Keys (RSA, EC, OpenSSH, etc.)
        (
            re.compile(
                r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
                re.IGNORECASE,
            ),
            "[REDACTED_PRIVATE_KEY]",
        ),
        # 2. Database & Network connection strings with credentials (e.g. postgresql://user:pass@host:5432/db)
        (
            re.compile(
                r"(?i)\b([a-zA-Z][a-zA-Z0-9+.-]*://)([^:@\s\r\n]+):([^@\s\r\n]+)@",
            ),
            r"\1[REDACTED_USER]:[REDACTED_PASSWORD]@",
        ),
        # 3. JWT Tokens (header.payload.signature)
        (
            re.compile(
                r"\bey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
            ),
            "[REDACTED_JWT]",
        ),
        # 4. Bearer tokens (e.g. "Bearer a8f2b...")
        (
            re.compile(
                r"(?i)\b(bearer\s+)([A-Za-z0-9_\-\.]{15,})\b"
            ),
            r"\1[REDACTED_TOKEN]",
        ),
        # 5. Google / Gemini API keys (AIza...)
        (
            re.compile(
                r"\bAIza[0-9A-Za-z\-_]{30,40}\b"
            ),
            "[REDACTED_API_KEY]",
        ),
        # 6. OpenAI API keys (sk-...)
        (
            re.compile(
                r"\bsk-[A-Za-z0-9\-_]{20,}\b"
            ),
            "[REDACTED_API_KEY]",
        ),
        # 7. AWS Access Key IDs
        (
            re.compile(
                r"\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b"
            ),
            "[REDACTED_AWS_KEY]",
        ),
        # 8. Key-Value credential pairs (e.g. password="secret", api_key: "abc12345", etc.)
        (
            re.compile(
                r"""(?i)(["']?(?:api[_-]?key|client[_-]?secret|secret|password|passwd|pwd|auth[_-]?token|access[_-]?token)["']?\s*[:=]\s*["']?)([^"'\s,;]{4,})(["']?)"""
            ),
            r"\1[REDACTED_SECRET]\3",
        ),
    ]

    @classmethod
    def redact(cls, text: str) -> Tuple[str, int]:
        """
        Scans and sanitizes the given text.
        Returns:
            Tuple of (sanitized_text, total_redactions_count)
        """
        if not text:
            return text, 0

        total_redactions = 0
        sanitized = text

        for pattern, replacement in cls._PATTERNS:
            sanitized, count = pattern.subn(replacement, sanitized)
            total_redactions += count

        return sanitized, total_redactions

    @classmethod
    def redact_text(cls, text: str) -> str:
        """
        Convenience helper returning only the redacted string.
        """
        sanitized, _ = cls.redact(text)
        return sanitized
