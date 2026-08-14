from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from services.project import (
    OWNER,
    PARTICIPANT,
    NotProjectOwnerError,
    ProjectNotFoundError,
    ProjectService,
)


@dataclass
class FakeProject:
    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class FakeProjectRepository:
    """In-memory stand-in for ProjectRepository."""

    def __init__(self) -> None:
        self.projects: dict[int, FakeProject] = {}
        self.roles: dict[tuple[int, int], str] = {}  # (project_id, user_id) -> role
        self.documents: dict[int, list[int]] = {}
        self.document_keys: dict[int, list[str]] = {}
        self.deleted: list[int] = []
        self._next_id = 1

    async def get_role_id(self, role: str) -> int:
        return 1 if role == OWNER else 2

    async def create(self, name: str, description: str | None) -> FakeProject:
        now = datetime.now(UTC)
        project = FakeProject(self._next_id, name, description, now, now)
        self.projects[project.id] = project
        self._next_id += 1
        return project

    async def add_member(self, project_id: int, user_id: int, role_id: int) -> None:
        self.roles[(project_id, user_id)] = OWNER if role_id == 1 else PARTICIPANT

    async def get_role_name(self, project_id: int, user_id: int) -> str | None:
        return self.roles.get((project_id, user_id))

    async def get_owner_id(self, project_id: int) -> int:
        for (pid, uid), role in self.roles.items():
            if pid == project_id and role == OWNER:
                return uid
        raise AssertionError("no owner recorded")

    async def get_by_id(self, project_id: int) -> FakeProject | None:
        return self.projects.get(project_id)

    async def get_document_ids(self, project_id: int) -> list[int]:
        return self.documents.get(project_id, [])

    async def get_document_keys(self, project_id: int) -> list[str]:
        return self.document_keys.get(project_id, [])

    async def delete(self, project_id: int) -> None:
        self.deleted.append(project_id)
        self.projects.pop(project_id, None)

    async def refresh(self, project: FakeProject) -> None:
        return None


class FakeStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, key: str) -> None:
        self.deleted.append(key)


@pytest.fixture
def repository() -> FakeProjectRepository:
    return FakeProjectRepository()


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def service(repository: FakeProjectRepository, storage: FakeStorage) -> ProjectService:
    return ProjectService(repository, storage)  # type: ignore[arg-type]


async def test_create_records_caller_as_owner(
    service: ProjectService, repository: FakeProjectRepository
) -> None:
    # Act
    project = await service.create(user_id=7, name="Website redesign", description=None)

    # Assert
    assert project.role == OWNER
    assert project.owner_id == 7
    assert repository.roles[(project.id, 7)] == OWNER


async def test_get_raises_when_user_has_no_membership(service: ProjectService) -> None:
    # Arrange
    await service.create(user_id=7, name="Website redesign", description=None)

    # Act / Assert
    with pytest.raises(ProjectNotFoundError):
        await service.get(project_id=1, user_id=99)


async def test_get_returns_project_for_member(service: ProjectService) -> None:
    # Arrange
    created = await service.create(user_id=7, name="Website redesign", description=None)

    # Act
    project = await service.get(project_id=created.id, user_id=7)

    # Assert
    assert project.name == "Website redesign"
    assert project.role == OWNER


async def test_delete_raises_for_participant(
    service: ProjectService, repository: FakeProjectRepository
) -> None:
    # Arrange
    created = await service.create(user_id=7, name="Website redesign", description=None)
    repository.roles[(created.id, 8)] = PARTICIPANT

    # Act / Assert
    with pytest.raises(NotProjectOwnerError):
        await service.delete(project_id=created.id, user_id=8)


async def test_delete_raises_for_stranger(service: ProjectService) -> None:
    # Arrange
    created = await service.create(user_id=7, name="Website redesign", description=None)

    # Act / Assert
    with pytest.raises(ProjectNotFoundError):
        await service.delete(project_id=created.id, user_id=99)


async def test_delete_removes_stored_objects(
    service: ProjectService,
    repository: FakeProjectRepository,
    storage: FakeStorage,
) -> None:
    # Arrange
    created = await service.create(user_id=7, name="Website redesign", description=None)
    repository.document_keys[created.id] = ["projects/1/a.pdf", "projects/1/b.pdf"]

    # Act
    await service.delete(project_id=created.id, user_id=7)

    # Assert
    assert repository.deleted == [created.id]
    assert storage.deleted == ["projects/1/a.pdf", "projects/1/b.pdf"]


async def test_update_changes_name_and_description(service: ProjectService) -> None:
    # Arrange
    created = await service.create(user_id=7, name="Old name", description="Old")

    # Act
    updated = await service.update(
        project_id=created.id, user_id=7, name="New name", description="New"
    )

    # Assert
    assert updated.name == "New name"
    assert updated.description == "New"


async def test_update_raises_for_stranger(service: ProjectService) -> None:
    # Arrange
    created = await service.create(user_id=7, name="Website redesign", description=None)

    # Act / Assert
    with pytest.raises(ProjectNotFoundError):
        await service.update(project_id=created.id, user_id=99, name="Hijacked", description=None)
