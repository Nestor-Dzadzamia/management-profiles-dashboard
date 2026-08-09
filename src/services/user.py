from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import create_access_token, hash_password, verify_password
from db.models import User


@dataclass(frozen=True)
class UserDTO:
    id: int
    login: str
    created_at: datetime


@dataclass(frozen=True)
class UserCredentialsDTO:
    id: int
    login: str
    password_hash: str


class LoginTakenError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_dto(user: User) -> UserDTO:
        return UserDTO(id=user.id, login=user.login, created_at=user.created_at)

    async def get_by_login(self, login: str) -> UserCredentialsDTO | None:
        result = await self._session.execute(select(User).where(User.login == login))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return UserCredentialsDTO(id=user.id, login=user.login, password_hash=user.password_hash)

    async def get_by_id(self, user_id: int) -> UserDTO | None:
        user = await self._session.get(User, user_id)
        return None if user is None else self._to_dto(user)

    async def create(self, login: str, password_hash: str) -> UserDTO:
        user = User(login=login, password_hash=password_hash)
        self._session.add(user)
        await self._session.flush()
        return self._to_dto(user)


class AuthService:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def register(self, login: str, password: str) -> UserDTO:
        if await self._users.get_by_login(login) is not None:
            raise LoginTakenError
        return await self._users.create(login, hash_password(password))

    async def authenticate(self, login: str, password: str) -> str:
        user = await self._users.get_by_login(login)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError
        return create_access_token(user.id)
