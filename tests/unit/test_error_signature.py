from backend.app.services.error_signature import ErrorSignatureGenerator


def test_error_signature_is_deterministic():
    sig1 = ErrorSignatureGenerator.generate(
        service_name="payment-service",
        environment="production",
        normalized_message="Connection timeout for user <ID> to host <IP>"
    )
    sig2 = ErrorSignatureGenerator.generate(
        service_name="payment-service",
        environment="production",
        normalized_message="Connection timeout for user <ID> to host <IP>"
    )
    assert sig1 == sig2
    assert len(sig1) == 64  # SHA-256 hex string


def test_error_signature_ignores_severity():
    """
    CRUCIAL: The signature generator must NOT include severity level,
    allowing ERROR and CRITICAL logs representing the same failure to group together.
    """
    sig1 = ErrorSignatureGenerator.generate(
        service_name="order-service",
        environment="production",
        normalized_message="Database pool connection timeout after 30000 ms"
    )
    sig2 = ErrorSignatureGenerator.generate(
        service_name="order-service",
        environment="production",
        normalized_message="Database pool connection timeout after 30000 ms"
    )
    assert sig1 == sig2


def test_error_signature_distinguishes_environment():
    """
    Production and staging identical errors must produce different signatures.
    """
    sig_prod = ErrorSignatureGenerator.generate(
        service_name="auth-service",
        environment="production",
        normalized_message="Token signature validation failed"
    )
    sig_staging = ErrorSignatureGenerator.generate(
        service_name="auth-service",
        environment="staging",
        normalized_message="Token signature validation failed"
    )
    assert sig_prod != sig_staging


def test_error_signature_distinguishes_service_names():
    sig_svc_a = ErrorSignatureGenerator.generate(
        service_name="billing-service",
        environment="production",
        normalized_message="NullPointerException in payment gateway"
    )
    sig_svc_b = ErrorSignatureGenerator.generate(
        service_name="shipping-service",
        environment="production",
        normalized_message="NullPointerException in payment gateway"
    )
    assert sig_svc_a != sig_svc_b


def test_error_signature_distinguishes_failures():
    sig1 = ErrorSignatureGenerator.generate(
        service_name="payment-service",
        environment="production",
        normalized_message="SQL error 23505: duplicate key value"
    )
    sig2 = ErrorSignatureGenerator.generate(
        service_name="payment-service",
        environment="production",
        normalized_message="HTTP 504 Gateway Timeout from upstream"
    )
    assert sig1 != sig2


def test_error_signature_case_and_whitespace_insensitivity():
    sig1 = ErrorSignatureGenerator.generate(
        service_name="  Payment-Service  ",
        environment="PRODUCTION",
        normalized_message="Redis connection reset   "
    )
    sig2 = ErrorSignatureGenerator.generate(
        service_name="payment-service",
        environment="production",
        normalized_message="Redis connection reset"
    )
    assert sig1 == sig2
