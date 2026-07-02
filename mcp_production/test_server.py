import pytest

import mcp_production.server as server


@pytest.fixture(autouse=True)
def reset_globals(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "API_TOKEN", "test-token")
    monkeypatch.setattr(server, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(server, "RATE_LIMIT_PER_MIN", 3)
    monkeypatch.setattr(server, "ALLOWED_HTTP_HOSTS", {"jsonplaceholder.typicode.com"})
    server.token_buckets.clear()
    server._init_db()


def test_get_query_params_handles_lists_and_scalars():
    result = server.get_query_params(
        {"symbol": ["BTC-USD", "ETH-USD"], "account_number": "1234", "skip": None}
    )
    assert result == "?symbol=BTC-USD&symbol=ETH-USD&account_number=1234"


def test_upsert_customer_then_list_customers():
    created = server.upsert_customer(
        {"name": "Alice", "email": "alice@example.com", "status": "active"},
        token="test-token",
    )
    assert created["email"] == "alice@example.com"
    assert created["status"] == "active"

    listed = server.list_customers(limit=10, token="test-token")
    assert listed["count"] == 1
    assert listed["items"][0]["email"] == "alice@example.com"


def test_upsert_customer_rejects_invalid_email():
    with pytest.raises(ValueError, match="email"):
        server.upsert_customer(
            {"name": "Alice", "email": "alice", "status": "active"},
            token="test-token",
        )


def test_unauthorized_token_is_rejected():
    with pytest.raises(PermissionError, match="Unauthorized"):
        server.list_customers(limit=5, token="wrong-token")


def test_rate_limit_exceeded():
    server.list_customers(limit=1, token="test-token")
    server.list_customers(limit=1, token="test-token")
    server.list_customers(limit=1, token="test-token")
    with pytest.raises(RuntimeError, match="Rate limit exceeded"):
        server.list_customers(limit=1, token="test-token")


def test_fetch_json_with_mocked_http(monkeypatch):
    class MockResponse:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"hello": "world"}

    def mock_get(url, timeout, allow_redirects):
        assert url == "https://jsonplaceholder.typicode.com/todos/1"
        assert timeout == server.REQUEST_TIMEOUT_SEC
        assert allow_redirects is False
        return MockResponse()

    monkeypatch.setattr(server.requests, "get", mock_get)
    result = server.fetch_json("https://jsonplaceholder.typicode.com/todos/1", token="test-token")
    assert result["status_code"] == 200
    assert result["data"] == {"hello": "world"}

