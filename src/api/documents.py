from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from api.deps import CurrentUser, DocumentServiceDep, ProjectServiceDep, SessionDep
from schemas.document import DocumentRead
from services.document import DocumentNotFoundError, InvalidFileError, UnsupportedFileTypeError
from services.project import ProjectNotFoundError

router = APIRouter(tags=["documents"])


@router.get("/project/{project_id}/documents", response_model=list[DocumentRead])
async def list_documents(
    project_id: int, user: CurrentUser, projects: ProjectServiceDep, documents: DocumentServiceDep
) -> list[DocumentRead]:
    try:
        await projects.get(project_id, user.id)
    except ProjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found") from None

    items = await documents.list_for_project(project_id)
    return [DocumentRead(**d.__dict__) for d in items]


@router.post(
    "/project/{project_id}/documents",
    response_model=list[DocumentRead],
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents(
    project_id: int,
    user: CurrentUser,
    projects: ProjectServiceDep,
    documents: DocumentServiceDep,
    session: SessionDep,
    files: Annotated[list[UploadFile], File()],
) -> list[DocumentRead]:
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
        created.append(DocumentRead(**dto.__dict__))

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


@router.put("/document/{document_id}", response_model=DocumentRead)
async def replace_document(
    document_id: int,
    user: CurrentUser,
    projects: ProjectServiceDep,
    documents: DocumentServiceDep,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> DocumentRead:
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
    return DocumentRead(**dto.__dict__)


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
