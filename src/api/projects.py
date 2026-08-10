from fastapi import APIRouter, HTTPException, Response, status

from api.deps import CurrentUser, ProjectServiceDep, SessionDep, UserRepositoryDep
from schemas.project import MemberRead, ProjectCreate, ProjectListItem, ProjectRead, ProjectUpdate
from services.project import AlreadyMemberError, NotProjectOwnerError, ProjectNotFoundError

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, user: CurrentUser, service: ProjectServiceDep, session: SessionDep
) -> ProjectRead:
    project = await service.create(user.id, payload.name, payload.description)
    await session.commit()
    return ProjectRead(**project.__dict__)


@router.get("/projects", response_model=list[ProjectListItem])
async def list_projects(
    user: CurrentUser,
    service: ProjectServiceDep,
) -> list[ProjectListItem]:
    projects = await service.list_for_user(user.id)
    return [ProjectListItem(**p.__dict__) for p in projects]


@router.get("/project/{project_id}/info", response_model=ProjectRead)
async def get_project(
    project_id: int,
    user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectRead:
    try:
        project = await service.get(project_id, user.id)
    except ProjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found") from None

    return ProjectRead(**project.__dict__)


@router.put("/project/{project_id}/info", response_model=ProjectRead)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    user: CurrentUser,
    service: ProjectServiceDep,
    session: SessionDep,
) -> ProjectRead:
    try:
        project = await service.update(project_id, user.id, payload.name, payload.description)
    except ProjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found") from None

    await session.commit()
    return ProjectRead(**project.__dict__)


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
    "/project/{project_id}/invite", response_model=MemberRead, status_code=status.HTTP_201_CREATED
)
async def invite_user(
    project_id: int,
    user: str,
    current_user: CurrentUser,
    service: ProjectServiceDep,
    users: UserRepositoryDep,
    session: SessionDep,
) -> MemberRead:
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
    return MemberRead(**member.__dict__)
