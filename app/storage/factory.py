"""Factory module for instantiating document storage backends."""
from typing import Optional
from app.config import get_settings
from app.exceptions import DocumentStorageError
from app.storage.base import DocumentStorage
from app.storage.local import LocalStorageBackend

_global_storage_instance: Optional[DocumentStorage] = None


def get_storage(storage_type: Optional[str] = None, base_dir: Optional[str] = None) -> DocumentStorage:
    """Retrieve or create the document storage backend based on application settings or custom args.

    Args:
        storage_type: Optional storage backend type ('local'). If None, uses settings.document_storage.
        base_dir: Optional base directory override. If None, uses settings.local_document_dir.

    Returns:
        DocumentStorage instance.
    """
    global _global_storage_instance

    # If explicit parameters are provided, return a specific new instance
    if storage_type is not None or base_dir is not None:
        settings = get_settings()
        stype = (storage_type or settings.document_storage).lower().strip()
        sdir = base_dir or settings.local_document_dir
        if stype == "local":
            return LocalStorageBackend(base_dir=sdir)
        raise DocumentStorageError(f"Unsupported storage backend type: '{stype}'")

    # Otherwise return/cache global instance
    if _global_storage_instance is None:
        settings = get_settings()
        stype = settings.document_storage.lower().strip()
        sdir = settings.local_document_dir
        if stype == "local":
            _global_storage_instance = LocalStorageBackend(base_dir=sdir)
        else:
            raise DocumentStorageError(f"Unsupported storage backend type: '{stype}'")

    return _global_storage_instance


def set_storage(storage: Optional[DocumentStorage]) -> None:
    """Override or reset the global storage instance (primarily for unit tests)."""
    global _global_storage_instance
    _global_storage_instance = storage
