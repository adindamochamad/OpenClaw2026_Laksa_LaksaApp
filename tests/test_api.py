from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    """Endpoint /health harus selalu merespons JSON status."""
    respon = client.get("/health")
    assert respon.status_code == 200
    badan = respon.json()
    assert badan.get("status") in ("ok", "degraded")


def test_root():
    respon = client.get("/")
    assert respon.status_code == 200
    assert respon.json().get("service") == "laksa"
