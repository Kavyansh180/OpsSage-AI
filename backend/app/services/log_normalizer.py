import re


class LogNormalizer:
    """
    Conservative log message normalizer for incident clustering and error signature generation.
    Replaces dynamic transient variables (UUIDs, IPs, timestamps, numeric IDs)
    while strictly preserving technical identifiers (exceptions, SQL codes, HTTP paths).
    """

    # 1. UUID Pattern: e.g. 123e4567-e89b-12d3-a456-426614174000
    UUID_REGEX = re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    )

    # 2. IP Address Pattern (with optional port): e.g. 192.168.1.1 or 10.0.0.5:8080
    IP_REGEX = re.compile(
        r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?::\d{1,5})?\b"
    )

    # 3. Hex memory addresses: e.g. 0x7fff5fbff820
    HEX_REGEX = re.compile(
        r"\b0x[0-9a-fA-F]+\b"
    )

    # 4. Embedded timestamps: e.g. 2026-11-02 10:30:45 or 10:30:45.123
    DATETIME_REGEX = re.compile(
        r"\b\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
    )
    TIME_ONLY_REGEX = re.compile(
        r"(?<=\s)\d{2}:\d{2}:\d{2}(?:\.\d+)?\b"
    )

    # 5. Entity ID patterns: e.g. "user 12345", "user_id=8912", "order #54321", "account: 9912"
    KEYWORD_ID_REGEX = re.compile(
        r"(?i)\b((?:user|account|customer|client|order|tenant|session|task|job|worker|process|id)(?:_id|_number)?)"
        r"([\s_:#=]+)\d+\b"
    )

    # 6. Standalone long numbers (5+ digits) that typically represent sequence IDs, timestamps, or tokens
    STANDALONE_NUMBER_REGEX = re.compile(
        r"(?<![A-Za-z\-_/])\b\d{5,}\b(?![A-Za-z\-_/])"
    )

    # 7. Multiple whitespace normalization
    WHITESPACE_REGEX = re.compile(r"\s+")

    @classmethod
    def _replace_standalone_numbers(cls, text: str) -> str:
        """
        Replaces arbitrary 5+ digit identifiers with <NUM> while strictly preserving:
        - Port numbers (e.g., 'port 54321', ':54321')
        - SQL / system error codes (e.g., 'error 23505', 'code 23505', 'sqlstate 23505')
        - Durations (e.g., '30000 ms', '60000ms', '120s')
        """
        def repl(m: re.Match) -> str:
            start, end = m.span()
            prefix = text[:start].lower()
            suffix = text[end:].lower()

            # 1. Preserve port numbers
            if re.search(r"(?:port[\s:=]+|:)$", prefix):
                return m.group(0)

            # 2. Preserve SQL error codes, errno, status codes
            if re.search(r"\b(?:error|code|errno|sqlstate|state|status)[\s:=]+$", prefix):
                return m.group(0)

            # 3. Preserve duration units
            if re.match(r"^\s*(?:ms|s|sec|seconds|min|minutes|hr|hours|us|ns)\b", suffix):
                return m.group(0)

            return "<NUM>"

        return cls.STANDALONE_NUMBER_REGEX.sub(repl, text)

    @classmethod
    def normalize(cls, message: str) -> str:
        """
        Applies conservative normalization rules to an input log message.
        Returns a normalized signature string.
        """
        if not message:
            return ""

        text = message.strip()

        # Step 1: Replace UUIDs
        text = cls.UUID_REGEX.sub("<UUID>", text)

        # Step 2: Replace IP addresses
        text = cls.IP_REGEX.sub("<IP>", text)

        # Step 3: Replace Hex addresses
        text = cls.HEX_REGEX.sub("<HEX>", text)

        # Step 4: Replace embedded timestamps and times
        text = cls.DATETIME_REGEX.sub("<TIMESTAMP>", text)
        text = cls.TIME_ONLY_REGEX.sub("<TIME>", text)

        # Step 5: Replace entity IDs (e.g., "user 12345" -> "user <ID>")
        text = cls.KEYWORD_ID_REGEX.sub(r"\1\2<ID>", text)

        # Step 6: Replace standalone long sequence numbers with smart preservation of ports, durations, SQL codes
        text = cls._replace_standalone_numbers(text)

        # Step 7: Collapse multiple spaces
        text = cls.WHITESPACE_REGEX.sub(" ", text).strip()

        return text
