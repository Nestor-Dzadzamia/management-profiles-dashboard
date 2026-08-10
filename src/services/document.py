import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Document
from storage import Storage

ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


@dataclass(frozen=True)
class DocumentDTO:
    id: int
    project_id: int
    s3_key: str
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by_id: int | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DocumentContent:
    filename: str
    content_type: str
    data: bytes


class DocumentNotFoundError(Exception):
    pass


class UnsupportedFileTypeError(Exception):
    pass


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_dto(document: Document) -> DocumentDTO:
        return DocumentDTO(
            id=document.id,
            project_id=document.project_id,
            s3_key=document.s3_key,
            filename=document.filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            uploaded_by_id=document.uploaded_by_id,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    async def get(self, document_id: int) -> DocumentDTO | None:
        document = await self._session.get(Document, document_id)
        return None if document is None else self._to_dto(document)

    async def list_for_project(self, project_id: int) -> list[DocumentDTO]:
        result = await self._session.execute(
            select(Document).where(Document.project_id == project_id).order_by(Document.id)
        )
        return [self._to_dto(d) for d in result.scalars().all()]

    async def create(
        self,
        project_id: int,
        s3_key: str,
        filename: str,
        content_type: str,
        size_bytes: int,
        uploaded_by_id: int,
    ) -> DocumentDTO:
        document = Document(
            project_id=project_id,
            s3_key=s3_key,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            uploaded_by_id=uploaded_by_id,
        )
        self._session.add(document)
        await self._session.flush()
        await self._session.refresh(document)
        return self._to_dto(document)

    async def replace(
        self,
        document_id: int,
        s3_key: str,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> DocumentDTO:
        document: Document | None = await self._session.get(Document, document_id)
        if document is None:
            raise DocumentNotFoundError

        document.s3_key = s3_key
        document.filename = filename
        document.content_type = content_type
        document.size_bytes = size_bytes
        await self._session.flush()
        await self._session.refresh(document)
        return self._to_dto(document)

    async def delete(self, document_id: int) -> None:
        await self._session.execute(delete(Document).where(Document.id == document_id))


class InvalidFileError(Exception):
    pass


class DocumentService:
    def __init__(self, documents: DocumentRepository, storage: Storage) -> None:
        self._documents = documents
        self._storage = storage

    @staticmethod
    def _extension_for(content_type: str) -> str:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise UnsupportedFileTypeError
        return ALLOWED_CONTENT_TYPES[content_type]

    @staticmethod
    def validate(files: list[tuple[str | None, str | None]]) -> None:
        """Reject the whole batch before anything is written to storage (Had leak here)"""
        for filename, content_type in files:
            if filename is None or content_type is None:
                raise InvalidFileError
            if content_type not in ALLOWED_CONTENT_TYPES:
                raise UnsupportedFileTypeError

    async def get(self, document_id: int) -> DocumentDTO:
        document = await self._documents.get(document_id)
        if document is None:
            raise DocumentNotFoundError
        return document

    async def list_for_project(self, project_id: int) -> list[DocumentDTO]:
        return await self._documents.list_for_project(project_id)

    async def upload(
        self, project_id: int, user_id: int, filename: str, content_type: str, data: bytes
    ) -> DocumentDTO:
        extension = self._extension_for(content_type)
        s3_key = f"projects/{project_id}/{uuid.uuid4().hex}.{extension}"
        self._storage.upload(s3_key, data, content_type)
        return await self._documents.create(
            project_id=project_id,
            s3_key=s3_key,
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            uploaded_by_id=user_id,
        )

    def get_content(self, document: DocumentDTO) -> DocumentContent:
        return DocumentContent(
            filename=document.filename,
            content_type=document.content_type,
            data=self._storage.download(document.s3_key),
        )

    async def replace(
        self, document: DocumentDTO, filename: str, content_type: str, data: bytes
    ) -> DocumentDTO:
        extension = self._extension_for(content_type)
        new_key = f"projects/{document.project_id}/{uuid.uuid4().hex}.{extension}"

        self._storage.upload(new_key, data, content_type)
        dto = await self._documents.replace(document.id, new_key, filename, content_type, len(data))
        self._storage.delete(document.s3_key)
        return dto

    async def delete(self, document: DocumentDTO) -> None:
        await self._documents.delete(document.id)
        self._storage.delete(document.s3_key)
