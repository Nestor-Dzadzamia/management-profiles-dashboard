from datetime import datetime

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from api.deps import CurrentUser, ProjectServiceDep, SessionDep, UserRepositoryDep
from services.project import (
    AlreadyMemberError,
    MemberDTO,
    NotProjectOwnerError,
    ProjectDTO,
    ProjectNotFoundError,
)


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class UpdateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    owner_id: int
    role: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: ProjectDTO) -> "ProjectResponse":
        return cls(
            id=dto.id,
            name=dto.name,
            description=dto.description,
            owner_id=dto.owner_id,
            role=dto.role,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class ProjectListResponse(ProjectResponse):
    document_ids: list[int]

    @classmethod
    def from_dto(cls, dto: ProjectDTO) -> "ProjectListResponse":
        return cls(
            id=dto.id,
            name=dto.name,
            description=dto.description,
            owner_id=dto.owner_id,
            role=dto.role,
            document_ids=dto.document_ids,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class MemberResponse(BaseModel):
    project_id: int
    user_id: int
    role: str
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: MemberDTO) -> "MemberResponse":
        return cls(
            project_id=dto.project_id,
            user_id=dto.user_id,
            role=dto.role,
            created_at=dto.created_at,
        )


router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: CreateProjectRequest,
    user: CurrentUser,
    service: ProjectServiceDep,
    session: SessionDep,
) -> ProjectResponse:
    project = await service.create(user.id, payload.name, payload.description)
    await session.commit()
    return ProjectResponse.from_dto(project)


@router.get("/projects", response_model=list[ProjectListResponse])
async def list_projects(
    user: CurrentUser,
    service: ProjectServiceDep,
) -> list[ProjectListResponse]:
    projects = await service.list_for_user(user.id)
    return [ProjectListResponse.from_dto(p) for p in projects]


@router.get("/project/{project_id}/info", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    try:
        project = await service.get(project_id, user.id)
    except ProjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found") from None

    return ProjectResponse.from_dto(project)


@router.put("/project/{project_id}/info", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    payload: UpdateProjectRequest,
    user: CurrentUser,
    service: ProjectServiceDep,
    session: SessionDep,
) -> ProjectResponse:
    try:
        project = await service.update(project_id, user.id, payload.name, payload.description)
    except ProjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found") from None

    await session.commit()
    return ProjectResponse.from_dto(project)


@router.delete("/project/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int, user: CurrentUser, service: ProjectServiceDep, session: SessionDep
) -> Response:
    try:
        await service.delete(project_id, user.id)
    except ProjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found") from None
    except NotProjectOwnerError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only The owner can delete the project"
        ) from None

    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/project/{project_id}/invite",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_user(
    project_id: int,
    user: str,
    current_user: CurrentUser,
    service: ProjectServiceDep,
    users: UserRepositoryDep,
    session: SessionDep,
) -> MemberResponse:
    invitee = await users.get_by_login(user)
    if invitee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from None

    try:
        member = await service.invite(project_id, current_user.id, invitee.id)
    except ProjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found") from None
    except NotProjectOwnerError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only The owner can invite") from None
    except AlreadyMemberError:
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already a member") from None

    await session.commit()
    return MemberResponse.from_dto(member)
