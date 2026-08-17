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
        f"/project/{project_id}/documents", files={"file": PDF}, headers=owner_token
    )

    # Assert
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "test.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(PDF[1])
    assert body["project_id"] == project_id
    assert "s3_key" not in body


async def test_upload_rejects_unsupported_type(client: AsyncClient) -> None:
    # Arrange
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)

    # Act
    response = await client.post(
        f"/project/{project_id}/documents",
        files={"file": ("test.txt", b"hello", "text/plain")},
        headers=owner_token,
    )

    # Assert
    assert response.status_code == 415


async def test_list_documents_returns_uploaded_ones(client: AsyncClient) -> None:
    # Arrange
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)

    await client.post(f"/project/{project_id}/documents", files={"file": PDF}, headers=owner_token)

    # Act
    response = await client.get(f"project/{project_id}/documents", headers=owner_token)

    # Assert
    assert response.status_code == 200
    body = response.json()[0]
    assert body["filename"] == "test.pdf"


async def test_project_lists_document_ids(client: AsyncClient) -> None:
    # Arrange
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)
    uploaded = await client.post(
        f"/project/{project_id}/documents", files={"file": PDF}, headers=owner_token
    )
    document_id = uploaded.json()["id"]

    # Act
    response = await client.get("/projects", headers=owner_token)

    # Assert
    project = next(p for p in response.json() if p["id"] == project_id)
    assert project["document_ids"] == [document_id]


async def test_download_returns_file_content(client: AsyncClient) -> None:
    # Arrange
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)
    uploaded = await client.post(
        f"/project/{project_id}/documents", files={"file": PDF}, headers=owner_token
    )
    document_id = uploaded.json()["id"]

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
        f"/project/{project_id}/documents", files={"file": PDF}, headers=owner_token
    )
    document_id = uploaded.json()["id"]
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
        f"/project/{project_id}/documents", files={"file": PDF}, headers=owner_token
    )
    document_id = upload.json()["id"]

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
        f"/project/{project_id}/documents", files={"file": PDF}, headers=owner_token
    )
    document_id = upload.json()["id"]

    # Act
    download = await client.get(f"/document/{document_id}", headers=non_member)
    delete = await client.delete(f"/document/{document_id}", headers=non_member)

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
        f"/project/{project_id}/documents", files={"file": PDF}, headers=participant
    )

    # Assert
    assert response.status_code == 201


async def test_deleting_project_removes_its_documents(client: AsyncClient) -> None:
    # Arrange
    owner_token = await register_and_login(client, "nestor")
    project_id = await _create_project(client, owner_token)
    upload = await client.post(
        f"/project/{project_id}/documents", files={"file": PDF}, headers=owner_token
    )
    document_id = upload.json()["id"]

    # Act
    remove = await client.delete(f"/project/{project_id}", headers=owner_token)

    # Assert
    assert remove.status_code == 204
    download = await client.get(f"/document/{document_id}", headers=owner_token)
    assert download.status_code == 404
