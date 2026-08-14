import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://app:app@localhost:5434/dashboard_test"
os.environ["JWT_SECRET"] = "test-secret-json-web-token-12345"
os.environ["S3_ENDPOINT_URL"] = "http://localhost:9000"
os.environ["S3_ACCESS_KEY"] = "minioadmin"
os.environ["S3_SECRET_KEY"] = "minioadmin"
os.environ["S3_BUCKET"] = "test-documents"

from collections.abc import AsyncGenerator, Generator  # noqa: E402

import pytest  # noqa: E402
from httpx2 import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import NullPool  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import get_settings  # noqa: E402
from db.base import Base  # noqa: E402
from db.session import get_session  # noqa: E402
from main import app  # noqa: E402
from storage import get_s3_client  # noqa: E402


@pytest.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
        await connection.exec_driver_sql(
            "INSERT INTO roles (id, role) VALUES (1, 'owner'), (2, 'participant')"
        )

    yield async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


# was repeating register and login many times and decided to add this here, possible check
async def register_and_login(client: AsyncClient, login: str) -> dict[str, str]:
    """here I just create new account each time and return jtw"""
    await client.post(
        "/auth",
        json={
            "login": login,
            "password": "some_random_password_nestor",
            "repeat_password": "some_random_password_nestor",
        },
    )
    response = await client.post(
        "/login",
        json={
            "login": login,
            "password": "some_random_password_nestor",
        },
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(autouse=True)
def clean_bucket() -> Generator[None, None, None]:
    """to empty the bucket after each test"""
    client = get_s3_client()
    bucket = get_settings().s3_bucket

    yield
    response = client.list_objects_v2(Bucket=bucket)
    for obj in response.get("Contents", []):
        client.delete_object(Bucket=bucket, Key=obj["Key"])
