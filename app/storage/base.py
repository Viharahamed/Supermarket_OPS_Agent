"""Abstract base class interface for document storage backends."""
from abc import ABC, abstractmethod
from app.storage.schemas import ArtifactResult


class DocumentStorage(ABC):
    """Abstract interface defining standard document storage operations.

    This abstraction decouples document generation (PDF/PPTX) and delivery
    (Telegram, API) from the underlying storage mechanism (Local FS, Railway Volume,
    or future Object Storage).
    """

    @abstractmethod
    def save(
        self,
        content: bytes,
        relative_path: str,
        artifact_type: str = "document",
        content_type: str = "application/octet-stream",
    ) -> ArtifactResult:
        """Save binary content to storage at relative_path.

        Args:
            content: Raw binary content to store.
            relative_path: Safe relative path/filename within storage root.
            artifact_type: Description of artifact ('invoice_pdf', 'sales_pptx', etc.).
            content_type: MIME type of the file.

        Returns:
            ArtifactResult containing saved metadata.
        """
        pass

    @abstractmethod
    def read(self, relative_path: str) -> bytes:
        """Read binary content of artifact at relative_path.

        Args:
            relative_path: Safe relative path/filename within storage root.

        Returns:
            Raw binary content bytes.
        """
        pass

    @abstractmethod
    def exists(self, relative_path: str) -> bool:
        """Check whether an artifact exists at relative_path.

        Args:
            relative_path: Safe relative path/filename within storage root.

        Returns:
            True if file exists, False otherwise.
        """
        pass

    @abstractmethod
    def delete(self, relative_path: str) -> bool:
        """Delete artifact at relative_path if it exists.

        Args:
            relative_path: Safe relative path/filename within storage root.

        Returns:
            True if deleted, False if file did not exist.
        """
        pass

    @abstractmethod
    def get_path(self, relative_path: str) -> str:
        """Get absolute path or storage reference string for relative_path.

        Args:
            relative_path: Safe relative path/filename within storage root.

        Returns:
            Resolved absolute path or storage locator.
        """
        pass
