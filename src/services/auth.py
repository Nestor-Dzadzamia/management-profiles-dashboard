from auth import create_access_token, hash_password, verify_password
from db.models import User
from repositories.user import UserRepository


class LoginTakenError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def register(self, login: str, password: str) -> User:
        if await self._users.get_by_login(login) is not None:
            raise LoginTakenError

        return await self._users.create(login, hash_password(password))

    async def authenticate(self, login: str, password: str) -> str:
        user = await self._users.get_by_login(login)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError

        return create_access_token(user.id)
