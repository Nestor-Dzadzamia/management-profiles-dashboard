from datetime import UTC, datetime

import pytest

from auth import decode_access_token
from services.user import (
    AuthService,
    InvalidCredentialsError,
    LoginTakenError,
    UserCredentialsDTO,
    UserDTO,
)


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, UserCredentialsDTO] = {}
        self._next_id = 1

    async def get_by_login(self, login: str) -> UserCredentialsDTO | None:
        return self.users.get(login)

    async def get_by_id(self, user_id: int) -> UserDTO | None:
        for user in self.users.values():
            if user.id == user_id:
                return UserDTO(id=user.id, login=user.login, created_at=datetime.now(UTC))
        return None

    async def create(self, login: str, password_hash: str) -> UserDTO:
        user = UserCredentialsDTO(id=self._next_id, login=login, password_hash=password_hash)
        self.users[login] = user
        self._next_id += 1
        return UserDTO(id=user.id, login=login, created_at=datetime.now(UTC))


@pytest.fixture
def repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def service(repository: FakeUserRepository) -> AuthService:
    return AuthService(repository)  # type: ignore[arg-type]


async def test_register_creates_user(service: AuthService) -> None:
    # Act
    user = await service.register("nestor", "some_random_password")

    # Assert
    assert user.login == "nestor"
    assert user.id == 1


async def test_register_stores_hash_not_plaintext(
    service: AuthService, repository: FakeUserRepository
) -> None:
    # Arrange
    password = "some_random_password"

    # Act
    await service.register("nestor", password)

    # Assert
    stored = repository.users["nestor"].password_hash
    assert stored != password
    assert password not in stored


async def test_register_rejects_duplicate_login(service: AuthService) -> None:
    # Arrange
    await service.register("nestor", "some_random_password")

    # Act / Assert
    with pytest.raises(LoginTakenError):
        await service.register("nestor", "another_password")


async def test_authenticate_returns_token_for_valid_credentials(
    service: AuthService,
) -> None:
    # Arrange
    user = await service.register("nestor", "some_random_password")

    # Act
    token = await service.authenticate("nestor", "some_random_password")

    # Assert
    assert decode_access_token(token) == user.id


async def test_authenticate_rejects_wrong_password(service: AuthService) -> None:
    # Arrange
    await service.register("nestor", "some_random_password")

    # Act / Assert
    with pytest.raises(InvalidCredentialsError):
        await service.authenticate("nestor", "a_different_password")


async def test_authenticate_rejects_unknown_login(service: AuthService) -> None:
    # Act / Assert
    with pytest.raises(InvalidCredentialsError):
        await service.authenticate("nobody", "some_random_password")


async def test_authenticate_uses_same_error_for_both_failures(
    service: AuthService,
) -> None:
    """Unknown login and wrong password must be indistinguishable."""
    # Arrange
    await service.register("nestor", "some_random_password")

    # Act
    unknown = None
    wrong = None
    try:
        await service.authenticate("nobody", "some_random_password")
    except Exception as exc:
        unknown = type(exc)
    try:
        await service.authenticate("nestor", "wrong_password")
    except Exception as exc:
        wrong = type(exc)

    # Assert
    assert unknown is wrong is InvalidCredentialsError
