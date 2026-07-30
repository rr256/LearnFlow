"""API tests for the operational health endpoint (OPS-001)."""


def test_health_returns_ok_status(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_is_served_outside_the_versioned_api(client):
    """Health probes must not move when the API major version changes."""
    assert client.get("/api/v1/health").status_code == 404
