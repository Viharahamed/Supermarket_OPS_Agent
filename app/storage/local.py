"""Local filesystem storage backend implementation."""
from pathlib import Path
from typing import Union
from app.exceptions import (
    DocumentDeleteError,
    DocumentNotFoundError,
    DocumentReadError,
    DocumentWriteError,
    InvalidStoragePathError,
)
from app.storage.base import DocumentStorage
from app.storage.schemas import ArtifactResult


class LocalStorageBackend(DocumentStorage):
    """Local filesystem implementation of DocumentStorage interface.

    Works for local development and persistent Railway Volume mounts.
    Maintains security against path traversal and ensures atomic directory creation.
    """

    def __init__(self, base_dir: Union[str, Path]):
        self.base_dir = Path(base_dir).resolve()
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise DocumentWriteError(f"Failed to create storage directory '{self.base_dir}': {e}")

    def _validate_relative_path(self, relative_path: str) -> Path:
        """Validate relative_path against path traversal vulnerabilities."""
        if not relative_path or not relative_path.strip():
            raise InvalidStoragePathError(relative_path, "Empty path provided")
        if "\0" in relative_path:
            raise InvalidStoragePathError(relative_path, "Null byte in path")

        # Normalize backslashes to forward slashes for cross-platform checking
        normalized = relative_path.replace("\\", "/")

        if normalized.startswith("/"):
            raise InvalidStoragePathError(relative_path, "Absolute paths are not allowed")

        # Check for drive letter or colon in path (Windows drive letters or schemes)
        if ":" in normalized:
            raise InvalidStoragePathError(relative_path, "Drive letters or schemes are not allowed")

        p = Path(relative_path)
        if p.is_absolute():
            raise InvalidStoragePathError(relative_path, "Absolute paths are not allowed")

        if ".." in p.parts or ".." in normalized.split("/"):
            raise InvalidStoragePathError(relative_path, "Path traversal ('..') is not allowed")

        try:
            resolved = (self.base_dir / p).resolve()
            resolved.relative_to(self.base_dir)
        except ValueError:
            raise InvalidStoragePathError(relative_path, "Path resolves outside storage root directory")
        except Exception as e:
            raise InvalidStoragePathError(relative_path, str(e))

        return resolved

    def save(
        self,
        content: bytes,
        relative_path: str,
        artifact_type: str = "document",
        content_type: str = "application/octet-stream",
    ) -> ArtifactResult:
        target_path = self._validate_relative_path(relative_path)
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(content)
        except Exception as e:
            raise DocumentWriteError(f"Failed to write file '{target_path.name}': {e}")

        # Compute relative storage key
        rel_key = str(target_path.relative_to(self.base_dir)).replace("\\", "/")

        return ArtifactResult(
            artifact_type=artifact_type,
            file_name=target_path.name,
            file_path=str(target_path),
            relative_path=rel_key,
            content_type=content_type,
            size_bytes=len(content),
        )

    def read(self, relative_path: str) -> bytes:
        target_path = self._validate_relative_path(relative_path)
        if not target_path.is_file():
            raise DocumentNotFoundError(relative_path)
        try:
            return target_path.read_bytes()
        except Exception as e:
            raise DocumentReadError(f"Failed to read file '{relative_path}': {e}")

    def exists(self, relative_path: str) -> bool:
        target_path = self._validate_relative_path(relative_path)
        return target_path.is_file()

    def delete(self, relative_path: str) -> bool:
        target_path = self._validate_relative_path(relative_path)
        if not target_path.is_file():
            return False
        try:
            target_path.unlink()
            return True
        except Exception as e:
            raise DocumentDeleteError(f"Failed to delete file '{relative_path}': {e}")

    def get_path(self, relative_path: str) -> str:
        target_path = self._validate_relative_path(relative_path)
        return str(target_path)
