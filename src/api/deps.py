from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from auth import decode_access_token
from db.session import get_session
from services.document import DocumentRepository, DocumentService
from services.project import ProjectRepository, ProjectService
from services.user import AuthService, UserDTO, UserRepository
from storage import Storage

bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


def get_auth_service(users: UserRepositoryDep) -> AuthService:
    return AuthService(users)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    users: UserRepositoryDep,
) -> UserDTO:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    user = await users.get_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    return user


CurrentUser = Annotated[UserDTO, Depends(get_current_user)]


def get_project_repository(session: SessionDep) -> ProjectRepository:
    return ProjectRepository(session)


def get_storage() -> Storage:
    return Storage()


StorageDep = Annotated[Storage, Depends(get_storage)]


ProjectRepositoryDep = Annotated[ProjectRepository, Depends(get_project_repository)]


def get_project_service(projects: ProjectRepositoryDep, storage: StorageDep) -> ProjectService:
    return ProjectService(projects, storage)


ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]


def get_document_repository(session: SessionDep) -> DocumentRepository:
    return DocumentRepository(session)


DocumentRepositoryDep = Annotated[DocumentRepository, Depends(get_document_repository)]


def get_document_service(documents: DocumentRepositoryDep, storage: StorageDep) -> DocumentService:
    return DocumentService(documents, storage)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
