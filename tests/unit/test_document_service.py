from dataclasses import dataclass, replace
from datetime import UTC, datetime

import pytest

from services.document import (
    DocumentDTO,
    DocumentNotFoundError,
    DocumentService,
    UnsupportedFileTypeError,
)

PDF = "application/pdf"


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.documents: dict[int, DocumentDTO] = {}
        self.deleted: list[int] = []
        self._next_id = 1

    async def get(self, document_id: int) -> DocumentDTO | None:
        return self.documents.get(document_id)

    async def list_for_project(self, project_id: int) -> list[DocumentDTO]:
        return [d for d in self.documents.values() if d.project_id == project_id]

    async def create(
        self,
        project_id: int,
        s3_key: str,
        filename: str,
        content_type: str,
        size_bytes: int,
        uploaded_by_id: int,
    ) -> DocumentDTO:
        now = datetime.now(UTC)
        document = DocumentDTO(
            id=self._next_id,
            project_id=project_id,
            s3_key=s3_key,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            uploaded_by_id=uploaded_by_id,
            created_at=now,
            updated_at=now,
        )
        self.documents[document.id] = document
        self._next_id += 1
        return document

    async def replace(
        self,
        document_id: int,
        s3_key: str,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> DocumentDTO:
        existing = self.documents.get(document_id)
        if existing is None:
            raise DocumentNotFoundError

        updated = replace(
            existing,
            s3_key=s3_key,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            updated_at=datetime.now(UTC),
        )
        self.documents[document_id] = updated
        return updated

    async def delete(self, document_id: int) -> None:
        self.deleted.append(document_id)
        self.documents.pop(document_id, None)


@dataclass
class StorageCall:
    action: str
    key: str


class FakeStorage:
    """Records every call in order, so the delete ordering can be asserted."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.calls: list[StorageCall] = []

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data
        self.calls.append(StorageCall("upload", key))

    def download(self, key: str) -> bytes:
        self.calls.append(StorageCall("download", key))
        return self.objects[key]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)
        self.calls.append(StorageCall("delete", key))


@pytest.fixture
def repository() -> FakeDocumentRepository:
    return FakeDocumentRepository()


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def service(repository: FakeDocumentRepository, storage: FakeStorage) -> DocumentService:
    return DocumentService(repository, storage)  # type: ignore[arg-type]


async def test_upload_stores_file_and_metadata(
    service: DocumentService, storage: FakeStorage
) -> None:
    # Arrange
    data = b"%PDF-1.4\ntest\n%%EOF"

    # Act
    document = await service.upload(
        project_id=3, user_id=7, filename="brief.pdf", content_type=PDF, data=data
    )

    # Assert
    assert document.filename == "brief.pdf"
    assert document.size_bytes == len(data)
    assert document.uploaded_by_id == 7
    assert storage.objects[document.s3_key] == data


async def test_upload_generates_key_not_derived_from_filename(
    service: DocumentService,
) -> None:
    # Arrange
    hostile_name = "../../etc/passwd.pdf"

    # Act
    document = await service.upload(
        project_id=3, user_id=7, filename=hostile_name, content_type=PDF, data=b"x"
    )

    # Assert
    assert document.s3_key.startswith("projects/3/")
    assert ".." not in document.s3_key
    assert document.filename == hostile_name


async def test_upload_gives_two_files_distinct_keys(service: DocumentService) -> None:
    # Act
    first = await service.upload(3, 7, "report.pdf", PDF, b"one")
    second = await service.upload(3, 7, "report.pdf", PDF, b"two")

    # Assert
    assert first.s3_key != second.s3_key


async def test_upload_rejects_unsupported_type(service: DocumentService) -> None:
    # Act / Assert
    with pytest.raises(UnsupportedFileTypeError):
        await service.upload(3, 7, "notes.txt", "text/plain", b"hello")


async def test_upload_does_not_store_file_when_type_is_rejected(
    service: DocumentService, storage: FakeStorage
) -> None:
    # Act
    with pytest.raises(UnsupportedFileTypeError):
        await service.upload(3, 7, "notes.txt", "text/plain", b"hello")

    # Assert
    assert storage.objects == {}
    assert storage.calls == []


async def test_get_content_returns_stored_bytes(service: DocumentService) -> None:
    # Arrange
    data = b"%PDF-1.4\ntest\n%%EOF"
    document = await service.upload(3, 7, "brief.pdf", PDF, data)

    # Act
    content = service.get_content(document)

    # Assert
    assert content.data == data
    assert content.filename == "brief.pdf"
    assert content.content_type == PDF


async def test_get_raises_when_document_is_missing(service: DocumentService) -> None:
    # Act / Assert
    with pytest.raises(DocumentNotFoundError):
        await service.get(999)


async def test_replace_keeps_id_and_updates_metadata(
    service: DocumentService,
) -> None:
    # Arrange
    original = await service.upload(3, 7, "brief.pdf", PDF, b"old content")
    new_data = b"new content here"

    # Act
    updated = await service.replace(original, "updated.pdf", PDF, new_data)

    # Assert
    assert updated.id == original.id
    assert updated.filename == "updated.pdf"
    assert updated.size_bytes == len(new_data)


async def test_replace_uploads_before_deleting_the_old_object(
    service: DocumentService, storage: FakeStorage
) -> None:
    # Arrange
    original = await service.upload(3, 7, "brief.pdf", PDF, b"old content")
    storage.calls.clear()

    # Act
    updated = await service.replace(original, "updated.pdf", PDF, b"new content")

    # Assert
    assert storage.calls == [
        StorageCall("upload", updated.s3_key),
        StorageCall("delete", original.s3_key),
    ]


async def test_replace_removes_the_previous_object(
    service: DocumentService, storage: FakeStorage
) -> None:
    # Arrange
    original = await service.upload(3, 7, "brief.pdf", PDF, b"old content")

    # Act
    updated = await service.replace(original, "updated.pdf", PDF, b"new content")

    # Assert
    assert original.s3_key not in storage.objects
    assert storage.objects[updated.s3_key] == b"new content"


async def test_replace_rejects_unsupported_type(service: DocumentService) -> None:
    # Arrange
    original = await service.upload(3, 7, "brief.pdf", PDF, b"content")

    # Act / Assert
    with pytest.raises(UnsupportedFileTypeError):
        await service.replace(original, "notes.txt", "text/plain", b"hello")


async def test_delete_removes_row_before_object(
    service: DocumentService,
    repository: FakeDocumentRepository,
    storage: FakeStorage,
) -> None:
    """DB first, storage second: an orphaned object beats a dangling row."""
    # Arrange
    document = await service.upload(3, 7, "brief.pdf", PDF, b"content")
    storage.calls.clear()

    # Act
    await service.delete(document)

    # Assert
    assert repository.deleted == [document.id]
    assert storage.calls == [StorageCall("delete", document.s3_key)]
    assert document.s3_key not in storage.objects


async def test_list_for_project_returns_only_that_projects_documents(
    service: DocumentService,
) -> None:
    # Arrange
    await service.upload(3, 7, "a.pdf", PDF, b"a")
    await service.upload(3, 7, "b.pdf", PDF, b"b")
    await service.upload(4, 7, "c.pdf", PDF, b"c")

    # Act
    documents = await service.list_for_project(3)

    # Assert
    assert [d.filename for d in documents] == ["a.pdf", "b.pdf"]
