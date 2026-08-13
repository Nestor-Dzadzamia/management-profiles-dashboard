from httpx2 import AsyncClient

from tests.integration.conftest import register_and_login


async def test_create_project_makes_caller_owner(client: AsyncClient) -> None:
    # Arrange
    token = await register_and_login(client, "nestor")

    # Act
    response = await client.post(
        "/projects",
        json={"name": "Random", "description": "Random"},
        headers=token,
    )

    # Assert
    assert response.status_code == 201
    body = response.json()

    assert body["name"] == "Random"
    assert body["description"] == "Random"
    assert body["role"] == "owner"
    assert isinstance(body["owner_id"], int)


async def test_list_projects_returns_only_accessible_ones(client: AsyncClient) -> None:
    # Arrange
    owner = await register_and_login(client, "nestor")
    other = await register_and_login(client, "giorgi")
    await client.post(
        "/projects",
        json={"name": "Random", "description": None},
        headers=owner,
    )

    # Act
    response = await client.get("/projects", headers=other)

    # Assert
    assert response.status_code == 200
    assert response.json() == []


async def test_non_member_gets_404_when_accessing_others_project(client: AsyncClient) -> None:
    # Arrange
    owner = await register_and_login(client, "nestor")
    user = await register_and_login(client, "giorgi")

    project = await client.post(
        "/projects",
        json={"name": "Random", "description": None},
        headers=owner,
    )

    project_id = project.json()["id"]

    # Act
    response = await client.get(f"/projects/{project_id}/info", headers=user)
    assert response.status_code == 404


async def test_update_project_changes_details(client: AsyncClient) -> None:
    # Arrange
    owner = await register_and_login(client, "nestor")

    project = await client.post(
        "/projects",
        json={"name": "Random", "description": None},
        headers=owner,
    )
    project_id = project.json()["id"]

    # Act
    response = await client.put(
        f"/project/{project_id}/info",
        json={"name": "new name", "description": "new description"},
        headers=owner,
    )

    # Assert
    assert response.status_code == 200
    body = response.json()

    assert body["name"] == "new name"
    assert body["description"] == "new description"
    assert body["id"] == project_id


async def test_owner_can_delete_project(client: AsyncClient) -> None:
    # Arrange
    owner = await register_and_login(client, "nestor")
    project = await client.post(
        "/projects",
        json={"name": "Random", "description": None},
        headers=owner,
    )
    project_id = project.json()["id"]

    # Act
    response = await client.delete(f"/project/{project_id}", headers=owner)

    # Assert
    assert response.status_code == 204
    remaining_projects = await client.get("/projects", headers=owner)
    assert remaining_projects.json() == []


async def test_invite_grants_participant_access(client: AsyncClient) -> None:
    # Arrange
    owner = await register_and_login(client, "nestor")
    participant = await register_and_login(client, "giorgi")
    project = await client.post(
        "/projects",
        json={"name": "Random", "description": None},
        headers=owner,
    )
    project_id = project.json()["id"]

    # Act
    invite_response = await client.post(f"/project/{project_id}/invite?user=giorgi", headers=owner)

    # Assert
    assert invite_response.status_code == 201
    assert invite_response.json()["role"] == "participant"

    participant_request = await client.get(f"/project/{project_id}/info", headers=participant)
    assert participant_request.status_code == 200
    assert participant_request.json()["role"] == "participant"


async def test_participant_can_update_but_not_delete(client: AsyncClient) -> None:
    # Arrange
    owner = await register_and_login(client, "nestor")
    participant = await register_and_login(client, "giorgi")
    project = await client.post(
        "/projects",
        json={"name": "Random", "description": None},
        headers=owner,
    )
    project_id = project.json()["id"]
    await client.post(f"/project/{project_id}/invite?user=giorgi", headers=owner)

    # Act
    update = await client.put(
        f"/project/{project_id}/info",
        json={"name": "new name", "description": "new description"},
        headers=participant,
    )
    delete = await client.delete(f"/project/{project_id}", headers=participant)

    # Assert
    assert update.status_code == 200
    assert delete.status_code == 403


async def test_participant_cannot_invite(client: AsyncClient) -> None:
    # Arrange
    owner = await register_and_login(client, "nestor")
    guest = await register_and_login(client, "giorgi")
    await register_and_login(client, "anna")
    created = await client.post(
        "/projects",
        json={"name": "Website redesign", "description": None},
        headers=owner,
    )
    project_id = created.json()["id"]
    await client.post(f"/project/{project_id}/invite?user=giorgi", headers=owner)

    # Act
    response = await client.post(f"/project/{project_id}/invite?user=anna", headers=guest)

    # Assert
    assert response.status_code == 403


async def test_invite_twice_conflicts(client: AsyncClient) -> None:
    # Arrange
    owner = await register_and_login(client, "nestor")
    await register_and_login(client, "giorgi")
    created = await client.post(
        "/projects",
        json={"name": "Website redesign", "description": None},
        headers=owner,
    )
    project_id = created.json()["id"]
    await client.post(f"/project/{project_id}/invite?user=giorgi", headers=owner)

    # Act
    response = await client.post(f"/project/{project_id}/invite?user=giorgi", headers=owner)

    # Assert
    assert response.status_code == 409


async def test_invite_unknown_user_returns_404(client: AsyncClient) -> None:
    # Arrange
    owner = await register_and_login(client, "nestor")
    created = await client.post(
        "/projects",
        json={"name": "Website redesign", "description": None},
        headers=owner,
    )
    project_id = created.json()["id"]

    # Act
    response = await client.post(f"/project/{project_id}/invite?user=nobody", headers=owner)

    # Assert
    assert response.status_code == 404
