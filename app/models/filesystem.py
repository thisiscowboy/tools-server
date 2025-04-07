from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class ReadFileRequest(BaseModel):
    """Request to read a file"""

    path: str = Field(..., description="Path to file")
    storage: str = Field("local", description="Storage type (local or s3)")
    bucket: Optional[str] = Field(None, description="S3 bucket name if using S3 storage")


class WriteFileRequest(BaseModel):
    """Request to write to a file"""

    path: str = Field(..., description="Path to file")
    content: str = Field(..., description="Content to write")
    storage: str = Field("local", description="Storage type (local or s3)")
    bucket: Optional[str] = Field(None, description="S3 bucket name if using S3 storage")


class ListDirectoryRequest(BaseModel):
    """Request to list directory contents"""

    path: str = Field(..., description="Directory path")
    storage: str = Field("local", description="Storage type (local or s3)")
    bucket: Optional[str] = Field(None, description="S3 bucket name if using S3 storage")
    recursive: bool = Field(False, description="Whether to list subdirectories recursively")


class SearchFilesRequest(BaseModel):
    """Request to search for files"""

    path: str = Field(..., description="Base path to search in")
    pattern: str = Field(..., description="Pattern to search for")
    storage: str = Field("local", description="Storage type (local or s3)")
    bucket: Optional[str] = Field(None, description="S3 bucket name if using S3 storage")
    exclude_patterns: Optional[List[str]] = Field(None, description="Patterns to exclude")


class CreateDirectoryRequest(BaseModel):
    """Request to create a directory"""

    path: str = Field(..., description="Directory path")
    storage: str = Field("local", description="Storage type (local or s3)")
    bucket: Optional[str] = Field(None, description="S3 bucket name if using S3 storage")


class DeleteFileRequest(BaseModel):
    """Request to delete a file"""

    path: str = Field(..., description="Path to file")
    storage: str = Field("local", description="Storage type (local or s3)")
    bucket: Optional[str] = Field(None, description="S3 bucket name if using S3 storage")


class DirectoryItem(BaseModel):
    """Information about a directory item"""

    name: str = Field(..., description="Item name")
    path: str = Field(..., description="Item path relative to listing directory")
    type: str = Field(..., description="Item type (file or directory)")
    size: Optional[int] = Field(None, description="File size in bytes")
    last_modified: Optional[int] = Field(None, description="Last modification timestamp")


class DirectoryListingResponse(BaseModel):
    """Response for directory listing"""

    path: str = Field(..., description="Listed directory path")
    items: List[DirectoryItem] = Field(..., description="Directory contents")


class InvalidateCacheRequest(BaseModel):
    """Request to invalidate file cache"""

    path: Optional[str] = Field(None, description="Path to invalidate (None for all)")
    storage: str = Field("local", description="Storage type (local or s3)")
    bucket: Optional[str] = Field(None, description="S3 bucket name if using S3 storage")


class FileExistsRequest(BaseModel):
    """Request to check if file exists"""

    path: str = Field(..., description="Path to check")
    storage: str = Field("local", description="Storage type (local or s3)")
    bucket: Optional[str] = Field(None, description="S3 bucket name if using S3 storage")
