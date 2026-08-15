from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel

from api.deps import CurrentUser, DocumentServiceDep, ProjectServiceDep, SessionDep
from services.document import (
    DocumentDTO,
    DocumentNotFoundError,
    InvalidFileError,
    UnsupportedFileTypeError,
)
from services.project import ProjectNotFoundError


class DocumentResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by_id: int | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: DocumentDTO) -> "DocumentResponse":
        return cls(
            id=dto.id,
            project_id=dto.project_id,
            filename=dto.filename,
            content_type=dto.content_type,
            size_bytes=dto.size_bytes,
            uploaded_by_id=dto.uploaded_by_id,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


router = APIRouter(tags=["documents"])


@router.get("/project/{project_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    project_id: int, user: CurrentUser, projects: ProjectServiceDep, documents: DocumentServiceDep
) -> list[DocumentResponse]:
    try:
        await projects.get(project_id, user.id)
    except ProjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found") from None

    items = await documents.list_for_project(project_id)
    return [DocumentResponse.from_dto(d) for d in items]


@router.post(
    "/project/{project_id}/documents",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents(
    project_id: int,
    user: CurrentUser,
    projects: ProjectServiceDep,
    documents: DocumentServiceDep,
    session: SessionDep,
    files: Annotated[list[UploadFile], File()],
) -> list[DocumentResponse]:
    try:
        await projects.get(project_id, user.id)
    except ProjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found") from None

    try:
        documents.validate([(f.filename, f.content_type) for f in files])
    except InvalidFileError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid file") from None
    except UnsupportedFileTypeError:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported file type"
        ) from None

    created = []
    for file in files:
        data = await file.read()
        dto = await documents.upload(
            project_id, user.id, str(file.filename), str(file.content_type), data
        )
        created.append(DocumentResponse.from_dto(dto))

    await session.commit()
    return created


@router.get("/document/{document_id}")
async def download_document(
    document_id: int,
    user: CurrentUser,
    projects: ProjectServiceDep,
    documents: DocumentServiceDep,
) -> Response:
    try:
        document = await documents.get(document_id)
    except DocumentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found") from None

    try:
        await projects.get(document.project_id, user.id)
    except ProjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found") from None

    content = documents.get_content(document)
    return Response(
        content=content.data,
        media_type=content.content_type,
        headers={"Content-Disposition": f'attachment; filename="{content.filename}"'},
    )


@router.put("/document/{document_id}", response_model=DocumentResponse)
async def replace_document(
    document_id: int,
    user: CurrentUser,
    projects: ProjectServiceDep,
    documents: DocumentServiceDep,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    try:
        document = await documents.get(document_id)
    except DocumentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found") from None

    try:
        await projects.get(document.project_id, user.id)
    except ProjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found") from None

    try:
        documents.validate([(file.filename, file.content_type)])
    except InvalidFileError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid file") from None
    except UnsupportedFileTypeError:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported file type"
        ) from None

    data = await file.read()
    dto = await documents.replace(document, str(file.filename), str(file.content_type), data)

    await session.commit()
    return DocumentResponse.from_dto(dto)


@router.delete("/document/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    user: CurrentUser,
    projects: ProjectServiceDep,
    documents: DocumentServiceDep,
    session: SessionDep,
) -> Response:
    try:
        document = await documents.get(document_id)
    except DocumentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found") from None

    try:
        await projects.get(document.project_id, user.id)
    except ProjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found") from None

    await documents.delete(document)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
