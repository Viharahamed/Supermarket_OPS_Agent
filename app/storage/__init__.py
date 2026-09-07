"""Document Storage package for Kirana AI Agent."""

from app.storage.base import DocumentStorage
from app.storage.factory import get_storage, set_storage
from app.storage.local import LocalStorageBackend
from app.storage.schemas import ArtifactResult

__all__ = [
    "DocumentStorage",
    "LocalStorageBackend",
    "ArtifactResult",
    "get_storage",
    "set_storage",
]
