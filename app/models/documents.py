from enum import Enum
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, HttpUrl


class DocumentType(str, Enum):
    MANUSCRIPT = "manuscript"  # Novels, fiction, etc.
    DOCUMENTATION = "documentation"  # Research papers, technical docs
    DATASET = "dataset"  # Structured data for training
    WEBPAGE = "webpage"  # Scraped web content
    GENERIC = "generic"  # Other document types


class CreateDocumentRequest(BaseModel):
    """Request model for document creation"""

    title: str = Field(..., description="Document title", min_length=1)
    content: str = Field(..., description="Document content (text)")
    document_type: DocumentType = Field(DocumentType.GENERIC, description="Type of document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata")
    tags: List[str] = Field(default_factory=list, description="Document tags")
    source_url: Optional[str] = Field(None, description="Source URL if applicable")
    storage_type: str = Field("local", description="Storage type (local or s3)")


class UpdateDocumentRequest(BaseModel):
    """Request model for document updates"""

    title: Optional[str] = Field(None, description="Updated title")
    content: Optional[str] = Field(None, description="Updated content")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")
    tags: Optional[List[str]] = Field(None, description="Updated tags")
    commit_message: str = Field("Updated document", description="Git commit message")


class DocumentResponse(BaseModel):
    """Response model for document operations"""

    id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Document title")
    document_type: DocumentType = Field(..., description="Type of document")
    created_at: int = Field(..., description="Creation timestamp")
    updated_at: int = Field(..., description="Last update timestamp")
    tags: List[str] = Field(..., description="Document tags")
    metadata: Dict[str, Any] = Field(..., description="Document metadata")
    content_preview: str = Field(..., description="Preview of document content")
    size_bytes: int = Field(..., description="Document size in bytes")
    version_count: Optional[int] = Field(1, description="Number of versions")
    content_available: bool = Field(..., description="Whether full content is available")
    source_url: Optional[str] = Field(None, description="Source URL if applicable")


class DocumentVersionResponse(BaseModel):
    """Response model for document version history"""

    version_hash: str = Field(..., description="Git commit hash")
    commit_message: str = Field(..., description="Commit message")
    author: str = Field(..., description="Author name")
    timestamp: int = Field(..., description="Commit timestamp")
    changes: Optional[Dict[str, Any]] = Field(None, description="Changes in this version")


class DocumentContentResponse(BaseModel):
    """Response model for document content"""

    id: str = Field(..., description="Document identifier")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Full document content")
    version: Optional[str] = Field(None, description="Version hash if specific version requested")
