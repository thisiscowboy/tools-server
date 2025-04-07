from fastapi import APIRouter, Body, HTTPException, Query, Path, File, UploadFile, Form
from fastapi.responses import PlainTextResponse, FileResponse, Response
from typing import List, Dict, Any, Optional
import os
import logging
from app.models.filesystem import (
    ReadFileRequest,
    WriteFileRequest,
    ListDirectoryRequest,
    SearchFilesRequest,
    CreateDirectoryRequest,
    DeleteFileRequest,
    DirectoryListingResponse,
    InvalidateCacheRequest,
    FileExistsRequest,
)
from app.core.filesystem_service import FilesystemService

logger = logging.getLogger(__name__)
router = APIRouter(
    responses={
        400: {"description": "Bad request"},
        403: {"description": "Access denied"},
        404: {"description": "File not found"},
        500: {"description": "Server error"},
    }
)
filesystem_service = FilesystemService()


@router.post(
    "/read",
    response_class=PlainTextResponse,
    summary="Read a file",
    description="Read the entire contents of a file from local or S3 storage",
)
async def read_file(request: ReadFileRequest = Body(...)):
    """
    Read the entire contents of a file.
    Supports both local filesystem and S3 storage.
    """
    try:
        return filesystem_service.read_file(request.path, request.storage, request.bucket)
    except ValueError as e:
        logger.warning(f"Access denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError:
        logger.warning(f"File not found: {request.path}")
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")
    except Exception as e:
        logger.error(f"Error reading file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/write",
    response_class=PlainTextResponse,
    summary="Write to a file",
    description="Write content to a file, overwriting if it exists",
)
async def write_file(request: WriteFileRequest = Body(...)):
    """
    Write content to a file, overwriting if it exists.
    Supports both local filesystem and S3 storage.
    """
    try:
        result = filesystem_service.write_file(
            request.path, request.content, request.storage, request.bucket
        )
        # Invalidate cache if caching is enabled
        try:
            filesystem_service.invalidate_cache(request.path, request.storage, request.bucket)
        except Exception as cache_error:
            logger.warning(f"Failed to invalidate cache: {cache_error}")
        return result
    except ValueError as e:
        logger.warning(f"Access denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error writing file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/list",
    response_model=DirectoryListingResponse,
    summary="List directory contents",
    description="List contents of a directory",
)
async def list_directory(request: ListDirectoryRequest = Body(...)):
    """
    List contents of a directory.
    Supports both local filesystem and S3 storage.
    """
    try:
        return filesystem_service.list_directory(
            request.path, request.storage, request.bucket, request.recursive
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/search", summary="Search for files", description="Search for files matching a pattern"
)
async def search_files(request: SearchFilesRequest = Body(...)):
    """
    Search for files matching a pattern.
    Supports both local filesystem and S3 storage.
    """
    try:
        results = filesystem_service.search_files(
            request.path, request.pattern, request.storage, request.bucket, request.exclude_patterns
        )
        return {"matches": results or ["No matches found"]}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/mkdir",
    response_class=PlainTextResponse,
    summary="Create a directory",
    description="Create a directory and parent directories if needed",
)
async def create_directory(request: CreateDirectoryRequest = Body(...)):
    """
    Create a new directory recursively.
    Supports both local filesystem and S3 storage.
    """
    try:
        return filesystem_service.create_directory(request.path, request.storage, request.bucket)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/delete",
    response_class=PlainTextResponse,
    summary="Delete a file",
    description="Delete a file from storage",
)
async def delete_file(request: DeleteFileRequest = Body(...)):
    """
    Delete a file.
    Supports both local filesystem and S3 storage.
    """
    try:
        return filesystem_service.delete_file(request.path, request.storage, request.bucket)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/read-binary",
    summary="Read binary file",
    description="Read a binary file and return its contents",
    responses={
        200: {"content": {"application/octet-stream": {}}, "description": "Binary file content"}
    },
)
async def read_binary_file(request: ReadFileRequest = Body(...)):
    """
    Read the contents of a binary file.
    Returns the file as a downloadable binary response.
    """
    try:
        content = filesystem_service.read_file_binary(request.path, request.storage, request.bucket)
        # Get filename from path
        filename = os.path.basename(request.path)
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ValueError as e:
        logger.warning(f"Access denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError:
        logger.warning(f"File not found: {request.path}")
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")
    except Exception as e:
        logger.error(f"Error reading binary file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/upload",
    response_class=PlainTextResponse,
    summary="Upload file",
    description="Upload a file to storage",
)
async def upload_file(
    file: UploadFile = File(...),
    path: str = Form(...),
    storage: str = Form("local"),
    bucket: Optional[str] = Form(None),
):
    """
    Upload a file to storage.
    Supports both local filesystem and S3 storage.
    """
    try:
        content = await file.read()
        result = filesystem_service.write_file_binary(
            os.path.join(path, file.filename), content, storage, bucket
        )
        # Invalidate cache if caching is enabled
        try:
            filesystem_service.invalidate_cache(os.path.join(path, file.filename), storage, bucket)
        except Exception as cache_error:
            logger.warning(f"Failed to invalidate cache: {cache_error}")
        return result
    except ValueError as e:
        logger.warning(f"Access denied: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/exists",
    summary="Check if file exists",
    description="Check if a file or directory exists in storage",
)
async def file_exists(request: FileExistsRequest = Body(...)):
    """
    Check if a file or directory exists.
    Supports both local filesystem and S3 storage.
    """
    try:
        exists = False
        if request.storage == "local":
            try:
                path = filesystem_service.normalize_path(request.path)
                exists = path.exists()
            except ValueError:
                # If normalize_path fails, file doesn't exist or is inaccessible
                exists = False
        elif request.storage == "s3":
            if not request.bucket:
                raise ValueError("S3 bucket name is required for S3 storage")
            if not filesystem_service.s3_client:
                raise ValueError("S3 client not configured")
            try:
                filesystem_service.s3_client.head_object(Bucket=request.bucket, Key=request.path)
                exists = True
            except:
                exists = False
        else:
            raise ValueError(f"Unsupported storage type: {request.storage}")
        return {"exists": exists, "path": request.path}
    except ValueError as e:
        logger.warning(f"Invalid request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error checking file existence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/invalidate-cache",
    response_class=PlainTextResponse,
    summary="Invalidate cache",
    description="Invalidate file cache for a path or all paths",
)
async def invalidate_cache(request: InvalidateCacheRequest = Body(...)):
    """
    Invalidate file cache.
    Can invalidate a specific path or all cached files.
    """
    try:
        if request.path:
            filesystem_service.invalidate_cache(request.path, request.storage, request.bucket)
            return f"Successfully invalidated cache for {request.path}"
        else:
            filesystem_service.invalidate_cache()
            return "Successfully invalidated all cache entries"
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
