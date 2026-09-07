"""Artifact result schema for document storage operations."""
from pydantic import BaseModel, Field


class ArtifactResult(BaseModel):
    """Structured result object returned after storing a document artifact."""
    artifact_type: str = Field(..., description="Type of artifact, e.g. 'invoice_pdf', 'sales_pptx'")
    file_name: str = Field(..., description="Canonical filename of the artifact")
    file_path: str = Field(..., description="Resolved storage file path")
    relative_path: str = Field(..., description="Relative storage key within storage root")
    content_type: str = Field(..., description="MIME content type, e.g. 'application/pdf'")
    size_bytes: int = Field(0, description="Size of the file in bytes")
