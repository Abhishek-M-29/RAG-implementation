from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def client(mock_connectors):
    from ragframework.api.main import create_app
    app = create_app()
    return TestClient(app)


class TestQueryFlow:
    def test_query_returns_sse_stream(self, client):
        response = client.post(
            "/v1/query",
            json={"query": "unique stream test q1", "session_id": "sess-1"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        events = response.text.strip().split("\n\n")
        assert len(events) >= 2

        data_lines = [e for e in events if e.startswith("data: ")]
        assert len(data_lines) >= 2

    def test_query_events_have_expected_structure(self, client):
        response = client.post(
            "/v1/query",
            json={"query": "unique event structure q2", "session_id": "sess-2"},
        )
        import json
        events = response.text.strip().split("\n\n")
        parsed = []
        for e in events:
            if e.startswith("data: "):
                parsed.append(json.loads(e[6:]))

        token_events = [p for p in parsed if p["type"] == "token"]
        meta_events = [p for p in parsed if p["type"] == "metadata"]
        assert len(token_events) >= 1
        assert len(meta_events) == 1
        assert meta_events[0]["cached"] is False

    def test_same_query_caches_result(self, client):
        import json
        r1 = client.post(
            "/v1/query",
            json={"query": "unique cache roundtrip q3", "session_id": "sess-3"},
        )
        assert r1.status_code == 200
        e1 = [json.loads(e[6:]) for e in r1.text.strip().split("\n\n") if e.startswith("data: ")]
        m1 = [p for p in e1 if p["type"] == "metadata"][0]
        assert m1["cached"] is False

        r2 = client.post(
            "/v1/query",
            json={"query": "unique cache roundtrip q3", "session_id": "sess-3"},
        )
        assert r2.status_code == 200
        e2 = [json.loads(e[6:]) for e in r2.text.strip().split("\n\n") if e.startswith("data: ")]
        m2 = [p for p in e2 if p["type"] == "metadata"][0]
        assert m2["cached"] is True

    def test_different_query_cache_miss(self, client):
        import json
        r1 = client.post("/v1/query", json={"query": "unique first q4", "session_id": "sess-4"})
        r2 = client.post("/v1/query", json={"query": "unique second q5", "session_id": "sess-4"})
        assert r1.status_code == 200
        assert r2.status_code == 200
        e1 = [json.loads(e[6:]) for e in r1.text.strip().split("\n\n") if e.startswith("data: ")]
        e2 = [json.loads(e[6:]) for e in r2.text.strip().split("\n\n") if e.startswith("data: ")]
        m1 = [p for p in e1 if p["type"] == "metadata"][0]
        m2 = [p for p in e2 if p["type"] == "metadata"][0]
        assert m1["cached"] is False
        assert m2["cached"] is False

    def test_query_rejects_missing_fields(self, client):
        response = client.post("/v1/query", json={})
        assert response.status_code == 422

    def test_query_rejects_invalid_json(self, client):
        response = client.post("/v1/query", data="not json", headers={"Content-Type": "application/json"})
        assert response.status_code == 422
