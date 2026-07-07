from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def client(mock_connectors):
    from ragframework.api.main import create_app
    app = create_app()
    return TestClient(app)


class TestHealth:
    def test_health_returns_ok(self, client):
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestReady:
    def test_ready_returns_ok_when_healthy(self, client):
        response = client.get("/v1/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_ready_returns_503_when_vector_store_unhealthy(self, mock_connectors):
        mock_vs, _ = mock_connectors
        mock_vs._healthy = False

        from ragframework.api.main import create_app
        app = create_app()
        client = TestClient(app)
        response = client.get("/v1/ready")
        assert response.status_code == 503
        data = response.json()
        assert "vector store" in data.get("detail", "").lower()

    def test_ready_returns_503_when_llm_fails(self, mock_connectors):
        mock_vs, mock_llm = mock_connectors
        orig_generate = mock_llm._generate

        def broken_generate(*a, **kw):
            raise RuntimeError("LLM down")

        mock_llm._generate = broken_generate

        from ragframework.api.main import create_app
        app = create_app()
        client = TestClient(app)
        response = client.get("/v1/ready")
        assert response.status_code == 503
        data = response.json()
        assert "LLM" in data.get("detail", "")
