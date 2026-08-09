from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_login(self, login: str) -> User | None:
        result = await self._session.execute(select(User).where(User.login == login))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def create(self, login: str, password_hash: str) -> User:
        user = User(login=login, password_hash=password_hash)
        self._session.add(user)
        await self._session.flush()
        return user
