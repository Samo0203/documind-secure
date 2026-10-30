def test_query_unauthenticated(client):
    resp = client.post("/api/v1/query", json={"question": "What is this about?"})
    assert resp.status_code == 401


def test_query_no_documents(client, auth_headers):
    """Querying with no uploaded documents should return a graceful message."""
    resp = client.post(
        "/api/v1/query",
        headers=auth_headers,
        json={"question": "What is the main topic?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert isinstance(data["sources"], list)
    # Answer should explain no docs found (not an error)
    assert len(data["answer"]) > 0


def test_query_invalid_document_id(client, auth_headers):
    """Querying with a document_id that belongs to another user should be forbidden."""
    resp = client.post(
        "/api/v1/query",
        headers=auth_headers,
        json={
            "question": "Summarize this.",
            "document_ids": ["00000000-0000-0000-0000-000000000000"],
        },
    )
    assert resp.status_code == 403


def test_query_too_short_question(client, auth_headers):
    resp = client.post(
        "/api/v1/query",
        headers=auth_headers,
        json={"question": "Hi"},
    )
    assert resp.status_code == 422


def test_query_response_schema(client, auth_headers):
    """Response must have 'answer' and 'sources' fields."""
    resp = client.post(
        "/api/v1/query",
        headers=auth_headers,
        json={"question": "What are the key findings?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "sources" in data
    assert isinstance(data["sources"], list)
