import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.git import router

# Create test app
app = FastAPI()
app.include_router(router, prefix="/git")
client = TestClient(app)


class TestGitAPI:
    @patch("app.api.git.git_service")
    def test_get_status(self, mock_git_service):
        # Mock the service
        mock_git_service.get_status.return_value = {
            "branch": "main",
            "clean": True,
            "untracked": [],
            "modified": [],
            "staged": [],
        }

        # Send request
        response = client.post("/git/status", json={"repo_path": "/test/repo"})

        # Verify response
        assert response.status_code == 200
        assert response.json()["branch"] == "main"
        assert response.json()["clean"] is True
        mock_git_service.get_status.assert_called_once()

    @patch("app.api.git.git_service")
    def test_get_diff(self, mock_git_service):
        # Mock the service
        mock_git_service.get_diff.return_value = "diff --git a/file.txt b/file.txt\n+New content"

        # Send request
        response = client.post(
            "/git/diff", json={"repo_path": "/test/repo", "file_path": "file.txt"}
        )

        # Verify response
        assert response.status_code == 200
        assert "diff --git" in response.text
        mock_git_service.get_diff.assert_called_once()

    @patch("app.api.git.git_service")
    def test_add_files(self, mock_git_service):
        # Mock the service
        mock_git_service.add_files.return_value = "Files staged successfully"

        # Send request
        response = client.post(
            "/git/add", json={"repo_path": "/test/repo", "files": ["file1.txt", "file2.txt"]}
        )

        # Verify response
        assert response.status_code == 200
        assert response.text == "Files staged successfully"
        mock_git_service.add_files.assert_called_once()

    @patch("app.api.git.git_service")
    def test_commit_changes(self, mock_git_service):
        # Mock the service
        mock_git_service.commit_changes.return_value = "Committed changes with hash abc123"

        # Send request
        response = client.post(
            "/git/commit",
            json={
                "repo_path": "/test/repo",
                "message": "Test commit",
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )

        # Verify response
        assert response.status_code == 200
        assert "Committed changes with hash" in response.text
        mock_git_service.commit_changes.assert_called_once()

    @patch("app.api.git.git_service")
    def test_reset_changes(self, mock_git_service):
        # Mock the service
        mock_git_service.reset_changes.return_value = "All staged changes reset"

        # Send request
        response = client.post("/git/reset", json={"repo_path": "/test/repo"})

        # Verify response
        assert response.status_code == 200
        assert response.text == "All staged changes reset"
        mock_git_service.reset_changes.assert_called_once()

    @patch("app.api.git.git_service")
    def test_get_log(self, mock_git_service):
        # Mock the service
        mock_git_service.get_log.return_value = {
            "commits": [
                {
                    "hash": "abc123",
                    "message": "Test commit",
                    "author": "Test User",
                    "date": "2023-01-01 10:00:00",
                }
            ]
        }

        # Send request
        response = client.post("/git/log", json={"repo_path": "/test/repo", "max_count": 10})

        # Verify response
        assert response.status_code == 200
        assert len(response.json()["commits"]) == 1
        assert response.json()["commits"][0]["hash"] == "abc123"
        mock_git_service.get_log.assert_called_once()

    @patch("app.api.git.git_service")
    def test_create_branch(self, mock_git_service):
        # Mock the service
        mock_git_service.create_branch.return_value = "Created branch 'feature'"

        # Send request
        response = client.post(
            "/git/branch",
            json={"repo_path": "/test/repo", "branch_name": "feature", "base_branch": "main"},
        )

        # Verify response
        assert response.status_code == 200
        assert response.text == "Created branch 'feature'"
        mock_git_service.create_branch.assert_called_once()

    @patch("app.api.git.git_service")
    def test_checkout_branch(self, mock_git_service):
        # Mock the service
        mock_git_service.checkout_branch.return_value = "Switched to branch 'feature'"

        # Send request
        response = client.post(
            "/git/checkout",
            json={"repo_path": "/test/repo", "branch_name": "feature", "create": False},
        )

        # Verify response
        assert response.status_code == 200
        assert response.text == "Switched to branch 'feature'"
        mock_git_service.checkout_branch.assert_called_once()

    @patch("app.api.git.git_service")
    def test_clone_repo(self, mock_git_service):
        # Mock the service
        mock_git_service.clone_repo.return_value = "Cloned repository to '/test/cloned'"

        # Send request
        response = client.post(
            "/git/clone",
            json={"repo_url": "https://github.com/example/repo.git", "local_path": "/test/cloned"},
        )

        # Verify response
        assert response.status_code == 200
        assert response.text == "Cloned repository to '/test/cloned'"
        mock_git_service.clone_repo.assert_called_once()

    @patch("app.api.git.git_service")
    def test_batch_commit(self, mock_git_service):
        # Mock the service
        mock_git_service.batch_commit.return_value = ["abc123", "def456"]

        # Send request
        response = client.post(
            "/git/batch-commit",
            json={
                "repo_path": "/test/repo",
                "file_groups": [["file1.txt", "file2.txt"], ["file3.txt"]],
                "message_template": "Batch commit",
            },
        )

        # Verify response
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0] == "abc123"
        mock_git_service.batch_commit.assert_called_once()
