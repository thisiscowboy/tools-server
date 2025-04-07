import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.core.filesystem_service import FilesystemService


@pytest.fixture
def fs_test_dir():
    # Create a temporary directory for testing
    temp_dir_path = tempfile.mkdtemp()
    yield temp_dir_path
    # Cleanup
    shutil.rmtree(temp_dir_path)


@pytest.fixture
def fs_service_fixture(fs_test_dir):
    # Configure service with test paths
    with patch("app.core.filesystem_service.get_config") as mock_config:
        mock_config.return_value.allowed_directories = [fs_test_dir]
        mock_config.return_value.file_cache_enabled = False
        mock_config.return_value.s3_access_key = None
        mock_config.return_value.s3_secret_key = None
        service = FilesystemService()
        yield service


class TestFilesystemService:
    def test_normalize_path(self, fs_service_fixture, fs_test_dir):
        # Test path normalization
        test_path = os.path.join(fs_test_dir, "test_file.txt")
        normalized = fs_service_fixture.normalize_path(test_path)
        assert str(normalized) == str(Path(test_path).resolve())

    def test_read_write_file(self, fs_service_fixture, fs_test_dir):
        # Test writing and reading a file
        test_path = os.path.join(fs_test_dir, "test_file.txt")
        content = "Test content"

        # Write file
        result = fs_service_fixture.write_file(test_path, content)
        assert "Successfully wrote to" in result

        # Read file
        read_content = fs_service_fixture.read_file(test_path)
        assert read_content == content

    def test_list_directory(self, fs_service_fixture, fs_test_dir):
        # Test directory listing
        # First create some test files
        os.makedirs(os.path.join(fs_test_dir, "subdir"), exist_ok=True)
        
        test_file1 = os.path.join(fs_test_dir, "file1.txt")
        test_file2 = os.path.join(fs_test_dir, "file2.txt")
        
        with open(test_file1, "w", encoding="utf-8") as f:
            f.write("File 1 content")
        
        with open(test_file2, "w", encoding="utf-8") as f:
            f.write("File 2 content")

        # List directory
        result = fs_service_fixture.list_directory(fs_test_dir)
        
        # Verify result structure
        assert "items" in result
        assert "directory" in result
        assert len(result["items"]) >= 3  # subdir, file1.txt, file2.txt
        
        # Verify files are included
        file_names = [item["name"] for item in result["items"]]
        assert "file1.txt" in file_names
        assert "file2.txt" in file_names
        assert "subdir" in file_names

    def test_create_delete_directory(self, fs_service_fixture, fs_test_dir):
        # Test directory creation and deletion
        new_dir = os.path.join(fs_test_dir, "new_test_dir", "nested_dir")
        
        # Create directory
        result = fs_service_fixture.create_directory(new_dir)
        assert "Successfully created" in result
        assert os.path.exists(new_dir)
        
        # Delete directory
        delete_result = fs_service_fixture.delete_file(new_dir)
        assert "Successfully deleted" in delete_result
        assert not os.path.exists(new_dir)

    def test_search_files(self, fs_service_fixture, fs_test_dir):
        # Test searching for files
        # Create test files with specific patterns
        test_dir1 = os.path.join(fs_test_dir, "search_test")
        os.makedirs(test_dir1, exist_ok=True)
        
        test_file1 = os.path.join(test_dir1, "search_file1.txt")
        test_file2 = os.path.join(test_dir1, "search_file2.txt")
        test_file3 = os.path.join(test_dir1, "other_file.txt")
        
        with open(test_file1, "w", encoding="utf-8") as f:
            f.write("Search file 1")
        
        with open(test_file2, "w", encoding="utf-8") as f:
            f.write("Search file 2")
        
        with open(test_file3, "w", encoding="utf-8") as f:
            f.write("Other file")
        
        # Search for files
        result = fs_service_fixture.search_files(fs_test_dir, "search_file*.txt")
        
        # Verify search results
        assert len(result) == 2
        file_paths = [item["path"] for item in result]
        assert os.path.basename(test_file1) in str(file_paths)
        assert os.path.basename(test_file2) in str(file_paths)
        assert os.path.basename(test_file3) not in str(file_paths)

    @patch("app.core.filesystem_service.boto3")
    def test_s3_operations(self, mock_boto3):
        # Test S3 operations
        # This test mocks S3 interactions
        
        # Mock S3 client and resource
        mock_s3_client = MagicMock()
        mock_s3_resource = MagicMock()
        mock_boto3.client.return_value = mock_s3_client
        mock_boto3.resource.return_value = mock_s3_resource
        
        # Create a service with S3 enabled
        with patch("app.core.filesystem_service.get_config") as mock_config:
            mock_config.return_value.allowed_directories = ["/test"]
            mock_config.return_value.s3_access_key = "test_key"
            mock_config.return_value.s3_secret_key = "test_secret"
            
            s3_service = FilesystemService()
            
            # Test S3 write operation
            s3_service.write_file("s3_test_file.txt", "S3 test content", "s3", "test_bucket")
            
            # Verify S3 client was called correctly
            mock_s3_client.put_object.assert_called_with(
                Bucket="test_bucket",
                Key="s3_test_file.txt",
                Body="S3 test content"
            )
