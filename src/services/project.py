from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Document, Project, ProjectMember, Role

OWNER = "owner"
PARTICIPANT = "participant"


@dataclass(frozen=True)
class ProjectDTO:
    id: int
    name: str
    description: str | None
    owner_id: int
    role: str
    document_ids: list[int]
    created_at: datetime
    updated_at: datetime


class ProjectNotFoundError(Exception):
    """The project doesn't exist, or the caller has no access to it."""


class NotProjectOwnerError(Exception):
    pass


class UserNotFoundedError(Exception):
    pass


class AlreadyMemberError(Exception):
    pass


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_role_id(self, role: str) -> int:
        result = await self._session.execute(select(Role.id).where(Role.role == role))
        return result.scalar_one()

    async def create(self, name: str, description: str | None) -> Project:
        project = Project(name=name, description=description)
        self._session.add(project)
        await self._session.flush()
        return project

    async def add_member(self, project_id: int, user_id: int, role_id: int) -> None:
        self._session.add(ProjectMember(project_id=project_id, user_id=user_id, role_id=role_id))
        await self._session.flush()

    async def get_role_name(self, project_id: int, user_id: int) -> str | None:
        """The caller's role in this project, or None if they have no access."""
        result = await self._session.execute(
            select(Role.role)
            .join(ProjectMember, ProjectMember.role_id == Role.id)
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_owner_id(self, project_id: int) -> int:
        result = await self._session.execute(
            select(ProjectMember.user_id)
            .join(Role, Role.id == ProjectMember.role_id)
            .where(ProjectMember.project_id == project_id, Role.role == OWNER)
        )
        return result.scalar_one()

    async def get_by_id(self, project_id: int) -> Project | None:
        return await self._session.get(Project, project_id)

    async def list_with_roles(self, user_id: int) -> list[tuple[Project, str]]:
        result = await self._session.execute(
            select(Project, Role.role)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .join(Role, Role.id == ProjectMember.role_id)
            .where(ProjectMember.user_id == user_id)
            .order_by(Project.id)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def get_document_ids(self, project_id: int) -> list[int]:
        result = await self._session.execute(
            select(Document.id).where(Document.project_id == project_id).order_by(Document.id)
        )
        return list(result.scalars().all())

    async def delete(self, project_id: int) -> None:
        await self._session.execute(delete(Project).where(Project.id == project_id))

    async def refresh(self, project: Project) -> None:
        await self._session.flush()
        await self._session.refresh(project)

    async def get_membership(self, project_id: int, user_id: int) -> ProjectMember | None:
        return await self._session.get(ProjectMember, (user_id, project_id))


@dataclass(frozen=True)
class MemberDTO:
    project_id: int
    user_id: int
    role: str
    created_at: datetime


class ProjectService:
    def __init__(self, projects: ProjectRepository) -> None:
        self._projects = projects

    async def _to_dto(self, project: Project, role: str) -> ProjectDTO:
        return ProjectDTO(
            id=project.id,
            name=project.name,
            description=project.description,
            owner_id=await self._projects.get_owner_id(project.id),
            role=role,
            document_ids=await self._projects.get_document_ids(project.id),
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    async def _require_access(self, project_id: int, user_id: int) -> str:
        role = await self._projects.get_role_name(project_id, user_id)
        if role is None:
            raise ProjectNotFoundError
        return role

    async def create(self, user_id: int, name: str, description: str | None) -> ProjectDTO:
        project = await self._projects.create(name, description)
        owner_role_id = await self._projects.get_role_id(OWNER)
        await self._projects.add_member(project.id, user_id, owner_role_id)
        return await self._to_dto(project, OWNER)

    async def get(self, project_id: int, user_id: int) -> ProjectDTO:
        role = await self._require_access(project_id, user_id)
        project = await self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError
        return await self._to_dto(project, role)

    async def list_for_user(self, user_id: int) -> list[ProjectDTO]:
        return [
            await self._to_dto(project, role)
            for project, role in await self._projects.list_with_roles(user_id)
        ]

    async def update(
        self, project_id: int, user_id: int, name: str, description: str | None
    ) -> ProjectDTO:
        role = await self._require_access(project_id, user_id)
        project = await self._projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError

        project.name = name
        project.description = description
        await self._projects.refresh(project)
        return await self._to_dto(project, role)

    async def delete(self, project_id: int, user_id: int) -> None:
        role = await self._require_access(project_id, user_id)
        if role != OWNER:
            raise NotProjectOwnerError
        await self._projects.delete(project_id)

    async def invite(self, project_id: int, ower_id: int, invitee_id: int) -> MemberDTO:
        role = await self._require_access(project_id, ower_id)
        if role != OWNER:
            raise NotProjectOwnerError

        if await self._projects.get_membership(project_id, invitee_id) is not None:
            raise AlreadyMemberError

        participant_role_id = await self._projects.get_role_id(PARTICIPANT)
        await self._projects.add_member(project_id, invitee_id, participant_role_id)

        membership = await self._projects.get_membership(project_id, invitee_id)
        assert membership is not None

        return MemberDTO(
            project_id=project_id,
            user_id=invitee_id,
            role=PARTICIPANT,
            created_at=membership.created_at,
        )
