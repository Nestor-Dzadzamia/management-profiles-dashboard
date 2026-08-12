from httpx2 import AsyncClient


async def test_register_returns_created_user(client: AsyncClient) -> None:
    # Arrange
    payload = {
        "login": "nestor",
        "password": "supersecret1",
        "repeat_password": "supersecret1",
    }

    # Act
    response = await client.post("/auth", json=payload)

    # Assert
    assert response.status_code == 201
    body = response.json()
    assert body["login"] == "nestor"
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_rejects_duplicate_login(client: AsyncClient) -> None:
    # Arrange
    payload = {
        "login": "nestor",
        "password": "supersecret1",
        "repeat_password": "supersecret1",
    }
    await client.post("/auth", json=payload)

    # Act
    response = await client.post("/auth", json=payload)

    # Assert
    assert response.status_code == 409


async def test_register_rejects_mismatched_passwords(client: AsyncClient) -> None:
    # Arrange
    payload = {
        "login": "nestor",
        "password": "supersecret1",
        "repeat_password": "different1",
    }

    # Act
    response = await client.post("/auth", json=payload)

    # Assert
    assert response.status_code == 422


async def test_login_returns_token(client: AsyncClient) -> None:
    # Arrange
    await client.post(
        "/auth",
        json={
            "login": "nestor",
            "password": "supersecret1",
            "repeat_password": "supersecret1",
        },
    )

    # Act
    response = await client.post("/login", json={"login": "nestor", "password": "supersecret1"})

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert body["access_token"]


async def test_login_rejects_wrong_password(client: AsyncClient) -> None:
    # Arrange
    await client.post(
        "/auth",
        json={
            "login": "nestor",
            "password": "supersecret1",
            "repeat_password": "supersecret1",
        },
    )

    # Act
    response = await client.post("/login", json={"login": "nestor", "password": "wrongpassword"})

    # Assert
    assert response.status_code == 401


async def test_login_rejects_unknown_user(client: AsyncClient) -> None:
    # Act
    response = await client.post("/login", json={"login": "nobody", "password": "supersecret1"})

    # Assert
    assert response.status_code == 401


async def test_projects_requires_authentication(client: AsyncClient) -> None:
    # Act
    response = await client.get("/projects")

    # Assert
    assert response.status_code == 401
