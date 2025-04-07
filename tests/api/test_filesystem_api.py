import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import os
import io

from app.api.filesystem import router
from app.models.filesystem import DirectoryListingResponse

# Create test app
app = FastAPI()
app.include_router(router, prefix="/fs")
client = TestClient(app)


class TestFilesystemAPI:
    @patch("app.api.filesystem.filesystem_service")
    def test_read_file(self, mock_fs_service):
        # Mock the service
        mock_fs_service.read_file.return_value = "File content"

        # Send request
        response = client.post("/fs/read", json={"path": "/test/file.txt", "storage": "local"})

        # Verify response
        assert response.status_code == 200
        assert response.text == "File content"
        mock_fs_service.read_file.assert_called_once()

    @patch("app.api.filesystem.filesystem_service")
    def test_write_file(self, mock_fs_service):
        # Mock the service
        mock_fs_service.write_file.return_value = "Successfully wrote to /test/file.txt"

        # Send request
        response = client.post(
            "/fs/write",
            json={"path": "/test/file.txt", "content": "New content", "storage": "local"},
        )

        # Verify response
        assert response.status_code == 200
        assert response.text == "Successfully wrote to /test/file.txt"
        mock_fs_service.write_file.assert_called_once()

    @patch("app.api.filesystem.filesystem_service")
    def test_list_directory(self, mock_fs_service):
        # Mock the service
        mock_fs_service.list_directory.return_value = {
            "path": "/test",
            "items": [
                {
                    "name": "file1.txt",
                    "path": "file1.txt",
                    "type": "file",
                    "size": 100,
                    "last_modified": 1609459200,
                },
                {
                    "name": "subdir",
                    "path": "subdir",
                    "type": "directory",
                    "size": None,
                    "last_modified": None,
                },
            ],
        }

        # Send request
        response = client.post(
            "/fs/list", json={"path": "/test", "storage": "local", "recursive": False}
        )

        # Verify response
        assert response.status_code == 200
        assert response.json()["path"] == "/test"
        assert len(response.json()["items"]) == 2
        assert response.json()["items"][0]["name"] == "file1.txt"
        mock_fs_service.list_directory.assert_called_once()

    @patch("app.api.filesystem.filesystem_service")
    def test_search_files(self, mock_fs_service):
        # Mock the service
        mock_fs_service.search_files.return_value = ["/test/file1.txt", "/test/subdir/file2.txt"]

        # Send request
        response = client.post(
            "/fs/search", json={"path": "/test", "pattern": "*.txt", "storage": "local"}
        )

        # Verify response
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert "/test/file1.txt" in response.json()
        mock_fs_service.search_files.assert_called_once()

    @patch("app.api.filesystem.filesystem_service")
    def test_create_directory(self, mock_fs_service):
        # Mock the service
        mock_fs_service.create_directory.return_value = (
            "Successfully created directory /test/newdir"
        )

        # Send request
        response = client.post("/fs/mkdir", json={"path": "/test/newdir", "storage": "local"})

        # Verify response
        assert response.status_code == 200
        assert response.text == "Successfully created directory /test/newdir"
        mock_fs_service.create_directory.assert_called_once()

    @patch("app.api.filesystem.filesystem_service")
    def test_delete_file(self, mock_fs_service):
        # Mock the service
        mock_fs_service.delete_file.return_value = "Successfully deleted /test/file.txt"

        # Send request
        response = client.post("/fs/delete", json={"path": "/test/file.txt", "storage": "local"})

        # Verify response
        assert response.status_code == 200
        assert response.text == "Successfully deleted /test/file.txt"
        mock_fs_service.delete_file.assert_called_once()

    @patch("app.api.filesystem.filesystem_service")
    def test_upload_file(self, mock_fs_service):
        # Mock the service
        mock_fs_service.write_file_binary.return_value = "Successfully wrote to /test/uploaded.txt"
        mock_fs_service.invalidate_cache.return_value = None

        # Create test file
        test_file = io.BytesIO(b"Test file content")

        # Send request
        response = client.post(
            "/fs/upload",
            files={"file": ("uploaded.txt", test_file)},
            data={"path": "/test", "storage": "local"},
        )

        # Verify response
        assert response.status_code == 200
        assert "Successfully wrote to" in response.text
        mock_fs_service.write_file_binary.assert_called_once()

    @patch("app.api.filesystem.filesystem_service")
    def test_read_binary_file(self, mock_fs_service):
        # Mock the service
        mock_fs_service.read_file_binary.return_value = b"Binary content"

        # Send request
        response = client.post(
            "/fs/read-binary", json={"path": "/test/binary.bin", "storage": "local"}
        )

        # Verify response
        assert response.status_code == 200
        assert response.content == b"Binary content"
        mock_fs_service.read_file_binary.assert_called_once()

    @patch("app.api.filesystem.filesystem_service")
    def test_file_exists(self, mock_fs_service):
        # Mock the service
        mock_fs_service.file_exists.return_value = True

        # Send request
        response = client.post("/fs/exists", json={"path": "/test/file.txt", "storage": "local"})

        # Verify response
        assert response.status_code == 200
        assert response.json() is True
        mock_fs_service.file_exists.assert_called_once()
