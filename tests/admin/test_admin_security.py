import jwt
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.common.messages import AdminMessages
from app.core.config import settings
from app.main import app
from app.models.admin import Admin
from app.services.admin_auth_service import decrypt_admin_token, mint_admin_token


def test_admin_token_is_encrypted_jwe():
    from uuid import uuid4

    admin = Admin(id=uuid4(), email="ops@example.com")
    token = mint_admin_token(admin)

    # Compact JWE has five segments; a signed user JWT/JWS has three.
    assert token.count(".") == 4
    payload = decrypt_admin_token(token)
    assert payload["admin_id"] == str(admin.id)
    assert payload["token_type"] == "admin_session"


def test_regular_signed_jwt_cannot_access_admin_route():
    user_token = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000001"},
        "regular-user-secret-that-is-at-least-32-bytes",
        algorithm="HS256",
    )
    client = TestClient(app)
    response = client.get(
        f"{settings.ADMIN_ROUTE_PREFIX}/users",
        headers={"X-Admin-Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 404


def test_unauthenticated_admin_post_hides_validation_errors():
    client = TestClient(app)
    response = client.post(
        (
            f"{settings.ADMIN_ROUTE_PREFIX}/users/"
            "00000000-0000-0000-0000-000000000001/set-plan"
        ),
        json={},
    )
    assert response.status_code == 404


def test_admin_jwe_cannot_access_regular_user_route():
    from uuid import uuid4

    token = mint_admin_token(Admin(id=uuid4(), email="ops@example.com"))
    client = TestClient(app)
    response = client.get(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_admin_routes_are_absent_from_openapi():
    paths = app.openapi()["paths"]
    assert not any(
        path.startswith(settings.ADMIN_ROUTE_PREFIX)
        for path in paths
    )


@patch(
    "app.api.v1.routes.admin_auth_routes.request_admin_otp_in_background"
)
def test_admin_otp_request_uses_standard_generic_response(mock_send):
    client = TestClient(app)
    response = client.post(
        f"{settings.ADMIN_ROUTE_PREFIX}/auth/request-otp",
        json={"email": "unknown@example.com"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "message": AdminMessages.OTP_REQUESTED,
        "data": None,
        "code": 200,
    }
    mock_send.assert_called_once_with("unknown@example.com")
