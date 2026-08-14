import pytest

from services.document import (
    ALLOWED_CONTENT_TYPES,
    DocumentService,
    InvalidFileError,
    UnsupportedFileTypeError,
)

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_validate_accepts_pdf() -> None:
    # Arrange
    files: list[tuple[str | None, str | None]] = [("report.pdf", PDF)]

    # Act
    DocumentService.validate(files)

    # Assert
    # no exception means the batch is acceptable


def test_validate_accepts_docx() -> None:
    # Arrange
    files: list[tuple[str | None, str | None]] = [("notes.docx", DOCX)]

    # Act / Assert
    DocumentService.validate(files)


def test_validate_accepts_mixed_batch() -> None:
    # Arrange
    files: list[tuple[str | None, str | None]] = [("report.pdf", PDF), ("notes.docx", DOCX)]

    # Act / Assert
    DocumentService.validate(files)


def test_validate_rejects_plain_text() -> None:
    # Arrange
    files: list[tuple[str | None, str | None]] = [("notes.txt", "text/plain")]

    # Act / Assert
    with pytest.raises(UnsupportedFileTypeError):
        DocumentService.validate(files)


def test_validate_rejects_whole_batch_if_one_file_is_bad() -> None:
    # Arrange
    files: list[tuple[str | None, str | None]] = [
        ("report.pdf", PDF),
        ("virus.exe", "application/x-msdownload"),
    ]

    # Act / Assert
    with pytest.raises(UnsupportedFileTypeError):
        DocumentService.validate(files)


def test_validate_rejects_missing_filename() -> None:
    # Arrange
    files: list[tuple[str | None, str | None]] = [(None, PDF)]

    # Act / Assert
    with pytest.raises(InvalidFileError):
        DocumentService.validate(files)


def test_validate_rejects_missing_content_type() -> None:
    # Arrange
    files: list[tuple[str | None, str | None]] = [("report.pdf", None)]

    # Act / Assert
    with pytest.raises(InvalidFileError):
        DocumentService.validate(files)


def test_allowed_content_types_map_to_extensions() -> None:
    # Assert
    assert ALLOWED_CONTENT_TYPES[PDF] == ".pdf"
    assert ALLOWED_CONTENT_TYPES[DOCX] == ".docx"
