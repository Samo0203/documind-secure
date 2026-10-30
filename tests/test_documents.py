import io


def test_list_documents_empty(client, auth_headers):
    resp = client.get("/api/v1/documents", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["documents"] == []


def test_list_documents_unauthenticated(client):
    resp = client.get("/api/v1/documents")
    assert resp.status_code == 401


def test_upload_txt_document(client, auth_headers):
    txt_content = b"This is a test document.\nIt has some content for testing purposes."
    resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("test.txt", io.BytesIO(txt_content), "text/plain")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["original_filename"] == "test.txt"
    assert data["file_type"] == "txt"
    assert data["status"] in ("pending", "processing", "ready", "failed")
    return data["id"]


def test_upload_invalid_file_type(client, auth_headers):
    resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("malicious.exe", io.BytesIO(b"binary content"), "application/octet-stream")},
    )
    assert resp.status_code == 415


def test_upload_empty_file(client, auth_headers):
    resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert resp.status_code == 400


def test_get_document_not_found(client, auth_headers):
    resp = client.get("/api/v1/documents/nonexistent-id", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_document(client, auth_headers):
    # First upload
    txt_content = b"Document to be deleted."
    upload = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("delete_me.txt", io.BytesIO(txt_content), "text/plain")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    # Then delete
    del_resp = client.delete(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    # Verify it's gone
    get_resp = client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_access_other_user_document(client):
    """User B should not be able to access User A's document."""
    # Register User A
    client.post("/api/v1/auth/register", json={
        "email": "usera@example.com", "password": "Password123"
    })
    resp_a = client.post("/api/v1/auth/login", json={
        "email": "usera@example.com", "password": "Password123"
    })
    headers_a = {"Authorization": f"Bearer {resp_a.json()['access_token']}"}

    # Register User B
    client.post("/api/v1/auth/register", json={
        "email": "userb@example.com", "password": "Password123"
    })
    resp_b = client.post("/api/v1/auth/login", json={
        "email": "userb@example.com", "password": "Password123"
    })
    headers_b = {"Authorization": f"Bearer {resp_b.json()['access_token']}"}

    # User A uploads a document
    upload = client.post(
        "/api/v1/documents/upload",
        headers=headers_a,
        files={"file": ("private.txt", io.BytesIO(b"Secret content"), "text/plain")},
    )
    doc_id = upload.json()["id"]

    # User B tries to access it
    resp = client.get(f"/api/v1/documents/{doc_id}", headers=headers_b)
    assert resp.status_code == 403
