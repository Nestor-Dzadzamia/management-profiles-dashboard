from httpx2 import AsyncClient

from tests.conftest import register_and_login

PDF = ("test.pdf", b"%PDF-1.4\ntest\n%%EOF", "application/pdf")
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def _create_project(client: AsyncClient, token: dict[str, str]) -> int:
    response = await client.post(
        "/projects",
        json={
            "name": "random name",
            "description": "random description",
        },
        headers=token,
    )

    return int(response.json()["id"])


async def test_upload_document_returns_metadata(client: AsyncClient) -> None:
    # Arrange
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)

    # Act
    response = await client.post(
        f"/project/{project_id}/documents", files={"files": PDF}, headers=owner_token
    )

    # Assert
    assert response.status_code == 201
    body = response.json()
    assert len(body) == 1
    assert body[0]["filename"] == "test.pdf"
    assert body[0]["content_type"] == "application/pdf"
    assert body[0]["size_bytes"] == len(PDF[1])
    assert body[0]["project_id"] == project_id
    assert "s3_key" not in body[0]


async def test_upload_rejects_unsupported_type(client: AsyncClient) -> None:
    # Arrange
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)

    # Act
    response = await client.post(
        f"/project/{project_id}/documents",
        files={"files": ("test.txt", b"hello", "text/plain")},
        headers=owner_token,
    )

    # Assert
    assert response.status_code == 415


async def test_list_documents_returns_uploaded_ones(client: AsyncClient) -> None:
    # Arrange
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)

    await client.post(f"/project/{project_id}/documents", files={"files": PDF}, headers=owner_token)

    # Act
    response = await client.get(f"project/{project_id}/documents", headers=owner_token)

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["filename"] == "test.pdf"


async def test_project_lists_document_ids(client: AsyncClient) -> None:
    # Arrange
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)
    uploaded = await client.post(
        f"/project/{project_id}/documents", files={"files": PDF}, headers=owner_token
    )
    document_id = uploaded.json()[0]["id"]

    # Act
    response = await client.get("/projects", headers=owner_token)

    print(response.json())
    # Assert
    project = next(p for p in response.json() if p["id"] == project_id)
    assert project["document_ids"] == [document_id]


async def test_download_returns_file_content(client: AsyncClient) -> None:
    # Arrange
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)
    uploaded = await client.post(
        f"/project/{project_id}/documents", files={"files": PDF}, headers=owner_token
    )
    document_id = uploaded.json()[0]["id"]

    # Act
    response = await client.get(f"/document/{document_id}", headers=owner_token)

    # Assert
    assert response.status_code == 200
    assert response.content == PDF[1]
    assert "test.pdf" in response.headers["content-disposition"]


async def test_replace_document_keeps_id(client: AsyncClient) -> None:
    # Arrange
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)
    uploaded = await client.post(
        f"/project/{project_id}/documents", files={"files": PDF}, headers=owner_token
    )
    document_id = uploaded.json()[0]["id"]
    new_content = b"%PDF-1.4\nreplaced content here\n%%EOF"

    # Act
    response = await client.put(
        f"/document/{document_id}",
        files={"file": ("updated.pdf", new_content, "application/pdf")},
        headers=owner_token,
    )

    # Assert
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == document_id
    assert body["filename"] == "updated.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(new_content)

    downloaded = await client.get(f"/document/{document_id}", headers=owner_token)
    assert downloaded.content == new_content


async def test_delete_document_removes_it(client: AsyncClient) -> None:
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)
    upload = await client.post(
        f"/project/{project_id}/documents", files={"files": PDF}, headers=owner_token
    )
    document_id = upload.json()[0]["id"]

    response = await client.delete(f"/document/{document_id}", headers=owner_token)

    # Assert
    assert response.status_code == 204
    listing = await client.get(f"/project/{project_id}/documents", headers=owner_token)
    assert listing.json() == []


async def test_non_member_cannot_access_document(client: AsyncClient) -> None:
    owner_token = await register_and_login(client, "nestor")
    non_member = await register_and_login(client, "nonmember")
    project_id = await _create_project(client, owner_token)
    upload = await client.post(
        f"/project/{project_id}/documents", files={"files": PDF}, headers=owner_token
    )
    docuemnt_id = upload.json()[0]["id"]

    # Act
    download = await client.get(f"/document/{docuemnt_id}", headers=non_member)
    delete = await client.delete(f"/document/{docuemnt_id}", headers=non_member)

    # Assert
    assert download.status_code == 404
    assert delete.status_code == 404


async def test_participant_can_upload(client: AsyncClient) -> None:
    # Arrange
    owner_token = await register_and_login(client, "nestor")
    participant = await register_and_login(client, "participant")
    project_id = await _create_project(client, owner_token)
    invite = await client.post(
        f"/project/{project_id}/invite?user=participant",
        headers=owner_token,
    )
    assert invite.status_code == 201

    # Act
    response = await client.post(
        f"/project/{project_id}/documents", files={"files": PDF}, headers=participant
    )

    # Assert
    assert response.status_code == 201


async def test_upload_multiple_documents(client: AsyncClient) -> None:
    # Assert
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)

    # Act
    upload = await client.post(
        f"/project/{project_id}/documents",
        files=[
            ("files", ("test1.pdf", b"%PDF-1.4\nsome content here\n%%EOF", "application/pdf")),
            ("files", ("test2.pdf", b"%PDF-1.4\nsome content here\n%%EOF", "application/pdf")),
        ],
        headers=owner_token,
    )

    # Assert
    assert upload.status_code == 201
    assert len(upload.json()) == 2


async def test_deleting_project_removes_its_documents(client: AsyncClient) -> None:
    # Arrange
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)
    upload = await client.post(
        f"/project/{project_id}/documents", files={"files": PDF}, headers=owner_token
    )
    document_id = upload.json()[0]["id"]

    # Act
    remove = await client.delete(f"/project/{project_id}", headers=owner_token)

    # Assert
    assert remove.status_code == 204
    download = await client.get(f"/document/{document_id}", headers=owner_token)
    assert download.status_code == 404
