import os
import shutil
import tempfile
from unittest.mock import patch

import pytest
from git import Repo

from app.core.git_service import GitService


@pytest.fixture
def git_temp_directory():
    # Create a temporary directory for testing
    temp_dir_path = tempfile.mkdtemp()
    yield temp_dir_path
    # Cleanup
    shutil.rmtree(temp_dir_path)


@pytest.fixture
def git_service_fixture():
    service = GitService()
    yield service


@pytest.fixture
def git_repo_path(git_temp_directory):
    # Initialize a Git repository for testing
    repo_path = os.path.join(git_temp_directory, "test_repo")
    os.makedirs(repo_path)

    # Initialize git repo
    Repo.init(repo_path)

    # Create a test file and commit it
    test_file = os.path.join(repo_path, "test.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("Initial content")

    repo = Repo(repo_path)
    repo.git.add("test.txt")
    repo.git.config("user.email", "test@example.com")
    repo.git.config("user.name", "Test User")
    repo.git.commit("-m", "Initial commit")

    yield repo_path


class TestGitService:
    def test_get_status(self, git_service_fixture, git_repo_path):
        # Test getting repository status
        result = git_service_fixture.get_status(git_repo_path)
        
        # Verify result
        assert "current_branch" in result
        assert "is_clean" in result
        assert result["is_clean"] is True  # Repository should be clean after initialization

    def test_add_and_commit(self, git_service_fixture, git_repo_path):
        # Test adding and committing changes
        # Create a new file
        new_file = os.path.join(git_repo_path, "new_file.txt")
        with open(new_file, "w", encoding="utf-8") as f:
            f.write("New file content")
        
        # Add the file
        add_result = git_service_fixture.add_files(git_repo_path, ["new_file.txt"])
        assert "Staged files" in add_result
        
        # Commit the changes
        commit_result = git_service_fixture.commit_changes(git_repo_path, "Added new file")
        assert "Committed" in commit_result
        
        # Verify repository status
        status = git_service_fixture.get_status(git_repo_path)
        assert status["is_clean"] is True  # Repository should be clean after commit

    def test_get_log(self, git_service_fixture, git_repo_path):
        # Test getting commit log
        log_result = git_service_fixture.get_log(git_repo_path)
        
        # Verify log structure
        assert "commits" in log_result
        assert len(log_result["commits"]) >= 1
        
        # Verify commit information
        latest_commit = log_result["commits"][0]
        assert "hash" in latest_commit
        assert "message" in latest_commit
        assert "author" in latest_commit
        assert "date" in latest_commit
        assert latest_commit["message"] == "Initial commit"

    def test_create_checkout_branch(self, git_service_fixture, git_repo_path):
        # Test creating and checking out a branch
        # Create a new file and commit it to master
        new_file = os.path.join(git_repo_path, "master_file.txt")
        with open(new_file, "w", encoding="utf-8") as f:
            f.write("Master branch file")
        
        git_service_fixture.add_files(git_repo_path, ["master_file.txt"])
        git_service_fixture.commit_changes(git_repo_path, "Added file on master")
        
        # Create a new branch
        branch_result = git_service_fixture.create_branch(git_repo_path, "test-branch")
        assert "Created" in branch_result
        
        # Checkout the new branch
        checkout_result = git_service_fixture.checkout_branch(git_repo_path, "test-branch")
        assert "Switched to branch" in checkout_result
        
        # Create a branch-specific file
        branch_file = os.path.join(git_repo_path, "branch_file.txt")
        with open(branch_file, "w", encoding="utf-8") as f:
            f.write("Branch specific file")
        
        git_service_fixture.add_files(git_repo_path, ["branch_file.txt"])
        git_service_fixture.commit_changes(git_repo_path, "Added file on branch")
        
        # Verify status shows we're on the test branch
        status = git_service_fixture.get_status(git_repo_path)
        assert status["current_branch"] == "test-branch"

    def test_create_tag(self, git_service_fixture, git_repo_path):
        # Test creating a tag
        tag_result = git_service_fixture.create_tag(git_repo_path, "v1.0", "Version 1.0")
        assert "Created tag" in tag_result
        
        # Get tags
        repo = Repo(git_repo_path)
        tags = list(repo.tags)
        assert len(tags) == 1
        assert str(tags[0]) == "v1.0"

    @patch("app.core.git_service.requests")
    def test_webhook(self, mock_requests, git_service_fixture, git_temp_directory):
        # Test webhook functionality
        # Set up a repo
        repo_path = os.path.join(git_temp_directory, "webhook_test_repo")
        os.makedirs(repo_path)
        
        Repo.init(repo_path)
        
        # Mock webhook response
        mock_response = mock_requests.post.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        
        # Configure and trigger webhook
        webhook_url = "https://example.com/webhook"
        
        # Add a webhook
        result = git_service_fixture.add_webhook(repo_path, webhook_url, ["push"])
        assert "Added webhook" in result
        
        # Trigger webhook (we're just testing the mechanics here, not the actual HTTP request)
        trigger_result = git_service_fixture.trigger_webhook(repo_path, "push", {"data": "test"})
        assert "Triggered webhook" in trigger_result

        # Verify that the request was made
        mock_requests.post.assert_called()
