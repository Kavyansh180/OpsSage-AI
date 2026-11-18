import pytest
from backend.app.core.exceptions import (
    AppException,
    DatabaseConnectionError,
    ResourceNotFoundError,
    AuthenticationError,
    AuthorizationError,
)


def test_exception_hierarchy():
    exc = ResourceNotFoundError("Incident INC-101 not found", details={"id": "INC-101"})
    assert isinstance(exc, AppException)
    assert exc.status_code == 404
    assert exc.message == "Incident INC-101 not found"
    assert exc.details == {"id": "INC-101"}

    db_exc = DatabaseConnectionError("Timeout connecting to Atlas")
    assert db_exc.status_code == 503

    auth_exc = AuthenticationError()
    assert auth_exc.status_code == 401

    perm_exc = AuthorizationError()
    assert perm_exc.status_code == 403
