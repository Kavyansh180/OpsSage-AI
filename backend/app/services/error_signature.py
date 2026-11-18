import hashlib


class ErrorSignatureGenerator:
    """
    Deterministic error signature generator for failure clustering.
    Produces a canonical SHA-256 hash from service name, environment, and normalized message.
    Explicitly omits severity level to allow cross-severity failure escalation under one signature.
    """

    @classmethod
    def generate(
        cls,
        service_name: str,
        environment: str,
        normalized_message: str
    ) -> str:
        """
        Generates a 64-character hexadecimal SHA-256 signature.
        """
        clean_service = (service_name or "unknown-service").lower().strip()
        clean_env = (environment or "production").lower().strip()
        clean_msg = (normalized_message or "").strip()

        canonical_payload = f"{clean_service}|{clean_env}|{clean_msg}"
        return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
