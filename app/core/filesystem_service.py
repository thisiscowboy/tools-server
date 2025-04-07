import os
import pathlib
import logging
import hashlib
from typing import Optional, List, Dict, Any
import time
import threading
import glob
import shutil
import fnmatch
from app.utils.config import get_config

# Third-party imports in try/except for graceful handling
try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    boto3 = None
    HAS_BOTO3 = False

logger = logging.getLogger(__name__)

class FilesystemService:
    def __init__(self):
        config = get_config()
        self.allowed_directories = [str(pathlib.Path(os.path.expanduser(d)).resolve())
                                   for d in config.allowed_directories]
        self.s3_client = None
        self.s3_resource = None
        
        if config.s3_access_key and config.s3_secret_key:
            try:
                if not HAS_BOTO3 or boto3 is None:
                    logger.warning("boto3 is not installed. S3 functionality will be disabled.")
                else:
                    self.s3_client = boto3.client(
                        's3',
                        aws_access_key_id=config.s3_access_key,
                        aws_secret_access_key=config.s3_secret_key,
                        region_name=config.s3_region
                    )
                    self.s3_resource = boto3.resource(
                        's3',
                        aws_access_key_id=config.s3_access_key,
                        aws_secret_access_key=config.s3_secret_key,
                        region_name=config.s3_region
                    )
                    logger.info("S3 client initialized successfully")
            except Exception as e:
                logger.error("Failed to initialize S3 client: %s", e)
                
        self.cache_enabled = hasattr(config, 'file_cache_enabled') and config.file_cache_enabled
        self.cache_dir = pathlib.Path("./cache")
        self.cache_max_age = 3600
        self.cache = {}
        self.cache_lock = threading.Lock()
        
        if self.cache_enabled:
            self.cache_dir.mkdir(exist_ok=True)
            logger.info("File caching enabled")

    def normalize_path(self, requested_path: str) -> pathlib.Path:
        if not requested_path:
            raise ValueError("Empty path not allowed")
        requested = pathlib.Path(os.path.expanduser(requested_path)).resolve()
        
        for allowed in self.allowed_directories:
            if str(requested).startswith(allowed):
                return requested
        raise ValueError(f"Access denied: {requested} is outside allowed directories.")

    def _cache_key(self, path: str, storage: str = "local", bucket: Optional[str] = None) -> str:
        key_parts = [storage, path]
        if bucket:
            key_parts.append(bucket)
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def read_file(self, path: str, storage: str = "local", bucket: Optional[str] = None) -> str:
        if storage == "local":
            file_path = self.normalize_path(path)
            return file_path.read_text(encoding="utf-8")
        elif storage == "s3":
            if not bucket:
                raise ValueError("S3 bucket name is required for S3 storage")
            if not self.s3_client:
                raise ValueError("S3 client not configured")
            response = self.s3_client.get_object(Bucket=bucket, Key=path)
            return response['Body'].read().decode('utf-8')
        else:
            raise ValueError(f"Unsupported storage type: {storage}")

    def read_file_cached(self, path: str, max_age: Optional[int] = None,
                        storage: str = "local", bucket: Optional[str] = None) -> str:
        if not self.cache_enabled:
            return self.read_file(path, storage, bucket)
        cache_key = self._cache_key(path, storage, bucket)
        cache_max_age = self.cache_max_age if max_age is None else max_age
        
        with self.cache_lock:
            if cache_key in self.cache:
                entry = self.cache[cache_key]
                if time.time() - entry["timestamp"] < cache_max_age:
                    logger.debug("Cache hit for %s", path)
                    return entry["content"]
        
        content = self.read_file(path, storage, bucket)
        
        with self.cache_lock:
            self.cache[cache_key] = {
                "content": content,
                "timestamp": time.time()
            }
            cache_file = self.cache_dir / cache_key
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                logger.warning("Failed to write to disk cache: %s", e)
        return content

    def read_file_binary(self, path: str, storage: str = "local", bucket: Optional[str] = None) -> bytes:
        if storage == "local":
            file_path = self.normalize_path(path)
            if not file_path.exists():
                raise ValueError(f"File not found: {path}")
            if file_path.is_dir():
                raise ValueError(f"Path is a directory, not a file: {path}")
            return file_path.read_bytes()
        elif storage == "s3":
            if not bucket:
                raise ValueError("S3 bucket name is required for S3 storage")
            if not self.s3_client:
                raise ValueError("S3 client not configured")
            response = self.s3_client.get_object(Bucket=bucket, Key=path)
            return response['Body'].read()
        else:
            raise ValueError(f"Unsupported storage type: {storage}")

    def write_file(self, path: str, content: str, storage: str = "local", bucket: Optional[str] = None) -> str:
        if storage == "local":
            file_path = self.normalize_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote to {path}"
        elif storage == "s3":
            if not bucket:
                raise ValueError("S3 bucket name is required for S3 storage")
            if not self.s3_client:
                raise ValueError("S3 client not configured")
            self.s3_client.put_object(
                Bucket=bucket,
                Key=path,
                Body=content.encode('utf-8'),
                ContentType='text/plain'
            )
            return f"Successfully wrote to s3://{bucket}/{path}"
        else:
            raise ValueError(f"Unsupported storage type: {storage}")

    def write_file_binary(self, path: str, content: bytes,
                         storage: str = "local", bucket: Optional[str] = None) -> str:
        if storage == "local":
            file_path = self.normalize_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        elif storage == "s3":
            if not bucket:
                raise ValueError("S3 bucket name is required for S3 storage")
            if not self.s3_client:
                raise ValueError("S3 client not configured")
            self.s3_client.put_object(Bucket=bucket, Key=path, Body=content)
            return f"Successfully wrote to s3://{bucket}/{path}"
        else:
            raise ValueError(f"Unsupported storage type: {storage}")

    def create_directory(self, path: str, storage: str = "local", bucket: Optional[str] = None) -> str:
        if storage == "local":
            dir_path = self.normalize_path(path)
            dir_path.mkdir(parents=True, exist_ok=True)
            return f"Successfully created directory {path}"
        elif storage == "s3":
            if not bucket:
                raise ValueError("S3 bucket name is required for S3 storage")
            if not self.s3_client:
                raise ValueError("S3 client not configured")
            # S3 doesn't need explicit directory creation, but we'll add an empty marker
            self.s3_client.put_object(Bucket=bucket, Key=f"{path}/", Body=b'')
            return f"Successfully created directory s3://{bucket}/{path}/"
        else:
            raise ValueError(f"Unsupported storage type: {storage}")

    def delete_file(self, path: str, storage: str = "local", bucket: Optional[str] = None) -> str:
        if storage == "local":
            file_path = self.normalize_path(path)
            if file_path.exists():
                if file_path.is_file():
                    file_path.unlink()
                else:
                    shutil.rmtree(file_path)
                return f"Successfully deleted {path}"
            else:
                return f"File or directory does not exist: {path}"
        elif storage == "s3":
            if not bucket:
                raise ValueError("S3 bucket name is required for S3 storage")
            if not self.s3_client:
                raise ValueError("S3 client not configured")
            self.s3_client.delete_object(Bucket=bucket, Key=path)
            return f"Successfully deleted s3://{bucket}/{path}"
        else:
            raise ValueError(f"Unsupported storage type: {storage}")

    def search_files(self, directory: str, pattern: str, storage: str = "local", bucket: Optional[str] = None) -> List[str]:
        if storage == "local":
            dir_path = self.normalize_path(directory)
            if not dir_path.exists() or not dir_path.is_dir():
                raise ValueError(f"Directory does not exist: {directory}")
            
            matches = []
            for root, _, _ in os.walk(dir_path):
                for file in glob.glob(os.path.join(root, pattern)):
                    matches.append(file)
            return matches
        elif storage == "s3":
            if not bucket:
                raise ValueError("S3 bucket name is required for S3 storage")
            if not self.s3_client:
                raise ValueError("S3 client not configured")
            
            # Convert glob pattern to a prefix for S3
            prefix = directory.rstrip('/') + '/' if directory else ''
            response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            
            matches = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    if fnmatch.fnmatch(os.path.basename(key), pattern):
                        matches.append(key)
            return matches
        else:
            raise ValueError(f"Unsupported storage type: {storage}")

    def list_directory(self, directory: str, storage: str = "local", bucket: Optional[str] = None) -> Dict[str, Any]:
        if storage == "local":
            dir_path = self.normalize_path(directory)
            if not dir_path.exists():
                raise ValueError(f"Directory does not exist: {directory}")
            if not dir_path.is_dir():
                raise ValueError(f"Path is not a directory: {directory}")
            
            items = []
            for item in dir_path.iterdir():
                item_type = "directory" if item.is_dir() else "file"
                size = 0
                if item.is_file():
                    size = item.stat().st_size
                items.append({
                    "name": item.name,
                    "type": item_type,
                    "size": size,
                    "modified": item.stat().st_mtime
                })
            
            return {
                "path": str(dir_path),
                "items": items
            }
        elif storage == "s3":
            if not bucket:
                raise ValueError("S3 bucket name is required for S3 storage")
            if not self.s3_client:
                raise ValueError("S3 client not configured")
            
            prefix = directory.rstrip('/') + '/' if directory else ''
            response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix, Delimiter='/')
            
            items = []
            
            # Add directories (CommonPrefixes)
            if 'CommonPrefixes' in response:
                for prefix_obj in response['CommonPrefixes']:
                    prefix_name = prefix_obj['Prefix']
                    name = os.path.basename(prefix_name.rstrip('/'))
                    items.append({
                        "name": name,
                        "type": "directory",
                        "size": 0,
                        "modified": 0
                    })
            
            # Add files (Contents)
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    # Skip the directory itself or empty directory markers
                    if key == prefix or key.endswith('/'):
                        continue
                    name = os.path.basename(key)
                    items.append({
                        "name": name,
                        "type": "file",
                        "size": obj['Size'],
                        "modified": obj['LastModified'].timestamp() if hasattr(obj['LastModified'], 'timestamp') else 0
                    })
            
            return {
                "path": f"s3://{bucket}/{directory}",
                "items": items
            }
        else:
            raise ValueError(f"Unsupported storage type: {storage}")

    def file_exists(self, path: str, storage: str = "local", bucket: Optional[str] = None) -> bool:
        if storage == "local":
            file_path = self.normalize_path(path)
            return file_path.exists()
        elif storage == "s3":
            if not bucket:
                raise ValueError("S3 bucket name is required for S3 storage")
            if not self.s3_client:
                raise ValueError("S3 client not configured")
            
            try:
                self.s3_client.head_object(Bucket=bucket, Key=path)
                return True
            except Exception:
                # Check if it might be a directory by looking for objects with this prefix
                response = self.s3_client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=path.rstrip('/') + '/',
                    MaxKeys=1
                )
                return 'Contents' in response and len(response['Contents']) > 0
        else:
            raise ValueError(f"Unsupported storage type: {storage}")

    def invalidate_cache(self, path: Optional[str] = None,
                        storage: str = "local", bucket: Optional[str] = None):
        if not self.cache_enabled:
            return
        with self.cache_lock:
            if path is not None:
                cache_key = self._cache_key(path, storage, bucket)
                if cache_key in self.cache:
                    del self.cache[cache_key]
                cache_file = self.cache_dir / cache_key
                if cache_file.exists():
                    cache_file.unlink()
            else:
                self.cache.clear()
                for cache_file in self.cache_dir.glob("*"):
                    try:
                        cache_file.unlink()
                    except Exception as e:
                        logger.warning("Failed to delete cache file %s: %s", cache_file, e)
