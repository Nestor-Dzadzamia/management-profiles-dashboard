from app.core.security import create_access_token, verify_password
from app.db.models import User
from app.repositories.user import UserRepository


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
        return await self.register(login, password)

    async def authenticate(self, login: str, password: str) -> str:
        user = await self._users.get_by_login(login)

        if user is None or not verify_password(user.password_hash, password):
            raise InvalidCredentialsError

        return create_access_token(user_id=user.id)
