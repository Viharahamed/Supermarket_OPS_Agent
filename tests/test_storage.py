"""Unit tests for app.storage document storage abstraction and local backend."""

from pathlib import Path
import pytest

from app.exceptions import (
    DocumentDeleteError,
    DocumentNotFoundError,
    DocumentReadError,
    DocumentStorageError,
    DocumentWriteError,
    InvalidStoragePathError,
)
from app.storage.factory import get_storage, set_storage
from app.storage.local import LocalStorageBackend
from app.storage.schemas import ArtifactResult


@pytest.fixture
def temp_storage(tmp_path: Path):
    """Fixture providing a clean LocalStorageBackend rooted in pytest tmp_path."""
    storage = LocalStorageBackend(base_dir=tmp_path)
    set_storage(storage)
    yield storage
    set_storage(None)


def test_storage_save_and_read_binary(temp_storage: LocalStorageBackend):
    """1 & 2. Save binary data and read binary data back intact."""
    binary_content = bytes([0x00, 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0xFF])
    rel_path = "test_binary.bin"

    result = temp_storage.save(
        content=binary_content,
        relative_path=rel_path,
        artifact_type="test_artifact",
        content_type="application/octet-stream",
    )

    assert isinstance(result, ArtifactResult)
    assert result.file_name == "test_binary.bin"
    assert result.size_bytes == len(binary_content)
    assert result.artifact_type == "test_artifact"
    assert result.content_type == "application/octet-stream"

    read_bytes = temp_storage.read(rel_path)
    assert read_bytes == binary_content


def test_storage_exists_and_delete(temp_storage: LocalStorageBackend):
    """3 & 4. Test exists, delete, and missing artifact behavior."""
    rel_path = "sample.pdf"
    content = b"%PDF-1.4 sample content"

    assert not temp_storage.exists(rel_path)

    temp_storage.save(content, rel_path, artifact_type="invoice_pdf")
    assert temp_storage.exists(rel_path)

    # Delete existing
    assert temp_storage.delete(rel_path) is True
    assert not temp_storage.exists(rel_path)

    # Delete non-existing returns False
    assert temp_storage.delete(rel_path) is False

    # Reading non-existing raises DocumentNotFoundError
    with pytest.raises(DocumentNotFoundError):
        temp_storage.read(rel_path)


def test_storage_nested_directory_creation(temp_storage: LocalStorageBackend):
    """5. Create nested subdirectories safely."""
    nested_path = "invoices/2026/09/invoice_1001.pdf"
    content = b"%PDF-1.4 nested pdf"

    result = temp_storage.save(content, nested_path)
    assert temp_storage.exists(nested_path)
    assert temp_storage.read(nested_path) == content
    assert "invoices" in result.relative_path


def test_storage_reject_null_bytes(temp_storage: LocalStorageBackend):
    """Reject null bytes in relative paths."""
    with pytest.raises(InvalidStoragePathError):
        temp_storage.save(b"test", "file\0.pdf")


def test_storage_reject_absolute_paths(temp_storage: LocalStorageBackend):
    """7. Reject absolute paths (/etc/passwd, C:\\Windows\\System32)."""
    with pytest.raises(InvalidStoragePathError):
        temp_storage.save(b"test", "/etc/passwd")

    with pytest.raises(InvalidStoragePathError):
        temp_storage.save(b"test", "C:\\Windows\\System32\\cmd.exe")


def test_storage_reject_parent_traversal_forward_slash(temp_storage: LocalStorageBackend):
    """8. Reject ../ path traversal."""
    with pytest.raises(InvalidStoragePathError):
        temp_storage.save(b"test", "../secret.txt")

    with pytest.raises(InvalidStoragePathError):
        temp_storage.save(b"test", "invoices/../../secret.txt")


def test_storage_reject_parent_traversal_backslash(temp_storage: LocalStorageBackend):
    """9. Reject ..\\ path traversal."""
    with pytest.raises(InvalidStoragePathError):
        temp_storage.save(b"test", "..\\secret.txt")

    with pytest.raises(InvalidStoragePathError):
        temp_storage.save(b"test", "invoices\\..\\..\\secret.txt")


def test_storage_binary_content_preservation(temp_storage: LocalStorageBackend):
    """10. Verify exact binary content matches byte-for-byte."""
    raw_data = bytes(range(256))
    temp_storage.save(raw_data, "bytes_256.dat")
    assert temp_storage.read("bytes_256.dat") == raw_data


def test_storage_deterministic_regeneration_overwrite(temp_storage: LocalStorageBackend):
    """11. Verify same filename regeneration overwrites safely."""
    path = "invoices/invoice_1001.pdf"
    v1_content = b"%PDF-1.4 Version 1"
    v2_content = b"%PDF-1.4 Version 2 Updated"

    temp_storage.save(v1_content, path)
    assert temp_storage.read(path) == v1_content

    # Regenerate same invoice number
    temp_storage.save(v2_content, path)
    assert temp_storage.read(path) == v2_content


def test_storage_get_path_and_factory(tmp_path: Path):
    """12 & 13. Test get_path and get_storage factory with custom dir."""
    custom_dir = tmp_path / "custom_docs"
    storage = get_storage("local", base_dir=str(custom_dir))

    res = storage.save(b"hello", "doc.txt")
    assert Path(res.file_path).exists()
    assert storage.get_path("doc.txt") == str(Path(res.file_path))


def test_storage_unsupported_type():
    """Test factory raises error on unsupported storage backend type."""
    with pytest.raises(DocumentStorageError):
        get_storage("s3_cloud_storage")
