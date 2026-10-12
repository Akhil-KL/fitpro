import os
import tempfile

# Configure before the app is imported.
_tmp = tempfile.mkdtemp(prefix="fitpro-test-")
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "sqlite://",
        "AUTO_CREATE_TABLES": "true",
        "AUTH_MODE": "local",
        "JWT_SECRET": "test-secret-test-secret-test-secret",
        "OPENAI_API_KEY": "",
        "STORAGE_BACKEND": "local",
        "LOCAL_STORAGE_DIR": os.path.join(_tmp, "storage"),
        "CHAT_RATE_LIMIT_PER_MINUTE": "1000",
    }
)

import pytest  # noqa: E402


def _install_test_hasher_if_needed() -> None:
    """Use the real Argon2 hasher when installed; otherwise a test-only stand-in (never used in the app)."""
    try:
        import argon2  # noqa: F401

        return
    except ImportError:
        pass
    import hashlib
    import hmac

    from app.core import security

    class _TestHasher:
        def hash(self, pw: str) -> str:
            salt = os.urandom(8).hex()
            return f"test${salt}${hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), 1000).hex()}"

        def verify(self, pw: str, h: str) -> bool:
            _, salt, digest = h.split("$")
            return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 1000).hex(), digest)

    security._password_hasher = lambda: _TestHasher()  # type: ignore[assignment]


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.core.deps import chat_limiter
    from app.db.session import configure_engine

    _install_test_hasher_if_needed()
    configure_engine("sqlite://")
    chat_limiter._hits.clear()
    from app.main import app

    with TestClient(app) as c:
        yield c


def register(client, email="vikas@example.com", password="supersecret1"):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def auth(client):
    headers = register(client)
    r = client.put(
        "/api/v1/profile",
        headers=headers,
        json={"name": "Vikas", "age": 21, "gender": "male", "height_cm": 175, "current_weight_kg": 70,
              "activity_level": "moderate", "fitness_goal": "gain_muscle", "target_weight_kg": 75,
              "timezone": "Asia/Kolkata"},
    )
    assert r.status_code == 200, r.text
    return headers
