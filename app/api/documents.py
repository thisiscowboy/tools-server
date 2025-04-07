import asyncio
import hashlib
import json
import os
import tempfile
import time
import random
import uuid
import logging
import threading
from typing import List, Optional, Dict, Any, Union, Set, Tuple
from pathlib import Path
from urllib.parse import urljoin, urlparse
import urllib.robotparser as robotparser
import requests
import git
from git import Repo
from fastapi import APIRouter, Body, Query, HTTPException, Path, UploadFile, File, Form, Response
from pydantic import BaseModel, Field
from app.models.documents import (
    DocumentType,
    CreateDocumentRequest,
    UpdateDocumentRequest,
    DocumentResponse,
    DocumentVersionResponse,
    DocumentContentResponse,
)
from app.core.documents_service import DocumentsService
from app.utils.config import get_config

# Set up logger
logger = logging.getLogger(__name__)
# Create router
router = APIRouter()


class GitService:
    def __init__(self):
        config = get_config()
        self.default_username = config.default_git_username
        self.default_email = config.default_git_email
        self.temp_auth_files = {}
        self.repo_locks = {}

    def _get_repo(self, repo_path: str) -> git.Repo:
        """Get git repository object"""
        try:
            repo = Repo(repo_path)
            return repo
        except git.exc.InvalidGitRepositoryError:
            raise ValueError(f"Invalid Git repository at '{repo_path}'")
        except Exception as e:
            raise ValueError(f"Failed to get repository: {str(e)}")

    def _get_repo_lock(self, repo_path: str) -> threading.Lock:
        """Get a lock for a specific repository to prevent concurrent modifications"""
        if repo_path not in self.repo_locks:
            self.repo_locks[repo_path] = threading.Lock()
        return self.repo_locks[repo_path]

    def get_status(self, repo_path: str) -> Dict[str, Any]:
        """Get the status of a Git repository"""
        repo = self._get_repo(repo_path)
        current_branch = repo.active_branch.name
        # Get staged files
        staged_files = [item.a_path for item in repo.index.diff("HEAD")]
        # Get modified but unstaged files
        unstaged_files = [item.a_path for item in repo.index.diff(None)]
        # Get untracked files
        untracked_files = repo.untracked_files
        return {
            "clean": not (staged_files or unstaged_files or untracked_files),
            "current_branch": current_branch,
            "staged_files": staged_files,
            "unstaged_files": unstaged_files,
            "untracked_files": untracked_files,
        }

    def get_diff(
        self, repo_path: str, file_path: Optional[str] = None, target: Optional[str] = None
    ) -> str:
        """Get diff of changes"""
        repo = self._get_repo(repo_path)
        if file_path and target:
            return repo.git.diff(target, file_path)
        elif file_path:
            return repo.git.diff("HEAD", file_path)
        elif target:
            return repo.git.diff(target)
        else:
            return repo.git.diff()

    def add_files(self, repo_path: str, files: List[str]) -> str:
        """Stage files for commit"""
        with self._get_repo_lock(repo_path):
            repo = self._get_repo(repo_path)
            repo.git.add(files)
            return "Files staged successfully"

    def commit_changes(
        self,
        repo_path: str,
        message: str,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
    ) -> str:
        """Commit staged changes"""
        with self._get_repo_lock(repo_path):
            repo = self._get_repo(repo_path)
            author_name = author_name or self.default_username
            author_email = author_email or self.default_email
            # Set author for this commit
            with repo.config_writer() as config:
                config.set_value("user", "name", author_name)
                config.set_value("user", "email", author_email)
            # Commit changes
            commit = repo.index.commit(message)
            return f"Committed changes with hash {commit.hexsha}"

    def reset_changes(self, repo_path: str) -> str:
        """Reset staged changes"""
        with self._get_repo_lock(repo_path):
            repo = self._get_repo(repo_path)
            repo.git.reset()
            return "All staged changes reset"

    def get_log(
        self, repo_path: str, max_count: int = 10, file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get log of commits"""
        repo = self._get_repo(repo_path)
        if file_path:
            commits = list(repo.iter_commits(paths=file_path, max_count=max_count))
        else:
            commits = list(repo.iter_commits(max_count=max_count))
        log_data = []
        for commit in commits:
            log_data.append(
                {
                    "hash": commit.hexsha,
                    "author": f"{commit.author.name} <{commit.author.email}>",
                    "date": commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S %z"),
                    "message": commit.message.strip(),
                }
            )
        return log_data

    def create_branch(
        self, repo_path: str, branch_name: str, base_branch: Optional[str] = None
    ) -> str:
        """Create a new branch"""
        with self._get_repo_lock(repo_path):
            repo = self._get_repo(repo_path)
            if base_branch:
                repo.git.checkout(base_branch)
            repo.git.checkout("-b", branch_name)
            return f"Created branch '{branch_name}'"

    def checkout_branch(self, repo_path: str, branch_name: str, create: bool = False) -> str:
        """Checkout an existing branch or create a new one"""
        with self._get_repo_lock(repo_path):
            repo = self._get_repo(repo_path)
            if create:
                if branch_name not in repo.refs:
                    repo.git.checkout("-b", branch_name)
                else:
                    raise ValueError(f"Branch '{branch_name}' already exists")
            else:
                repo.git.checkout(branch_name)
            return f"Checked out branch '{branch_name}'"

    def clone_repo(self, repo_url: str, local_path: str, auth_token: Optional[str] = None) -> str:
        """Clone a Git repository"""
        try:
            if auth_token:
                if repo_url.startswith("https://"):
                    repo_url = repo_url.replace("https://", f"https://x-access-token:{auth_token}@")
                Repo.clone_from(repo_url, local_path)
            else:
                Repo.clone_from(repo_url, local_path)
            return f"Cloned repository to '{local_path}'"
        except Exception as e:
            raise ValueError(f"Failed to clone repository: {str(e)}")

    def remove_file(self, repo_path: str, file_path: str) -> str:
        """Remove a file from the repository"""
        with self._get_repo_lock(repo_path):
            repo = self._get_repo(repo_path)
            try:
                repo.index.remove([file_path])
                repo.index.commit(f"Removed {file_path}")
                return f"Successfully removed {file_path} from Git"
            except Exception as e:
                raise ValueError(f"Failed to remove file: {str(e)}")

    def get_file_content(self, repo_path: str, file_path: str, version: str) -> str:
        """Get the content of a file at a specific Git version"""
        repo = self._get_repo(repo_path)
        try:
            blob = repo.git.show(f"{version}:{file_path}")
            return blob
        except Exception as e:
            raise ValueError(f"Failed to get file content at version {version}: {str(e)}")

    def configure_lfs(self, repo_path: str, file_patterns: List[str]) -> str:
        """Configure Git LFS for the repository"""
        with self._get_repo_lock(repo_path):
            repo = self._get_repo(repo_path)
            try:
                repo.git.execute(["git", "lfs", "install"])
                for pattern in file_patterns:
                    repo.git.execute(["git", "lfs", "track", pattern])
                repo.index.commit("Set up Git LFS tracking")
                return "Git LFS configured successfully"
            except Exception as e:
                raise ValueError(f"Failed to set up Git LFS: {str(e)}")

    def batch_commit(
        self, repo_path: str, file_groups: List[List[str]], message_template: str
    ) -> List[str]:
        """Commit files in batches for better performance"""
        with self._get_repo_lock(repo_path):
            repo = self._get_repo(repo_path)
            commit_hashes = []
            for i, file_group in enumerate(file_groups):
                repo.git.add(file_group)
                commit = repo.index.commit(f"{message_template} (batch {i+1}/{len(file_groups)})")
                commit_hashes.append(commit.hexsha)
            return commit_hashes

    def pull_changes(
        self, repo_path: str, remote: str = "origin", branch: str = None, all_remotes: bool = False
    ) -> str:
        """Pull changes from a remote repository"""
        with self._get_repo_lock(repo_path):
            repo = self._get_repo(repo_path)
            try:
                if all_remotes:
                    result = repo.git.fetch(all=True)
                else:
                    result = repo.git.pull(remote, branch)
                return result
            except Exception as e:
                raise ValueError(f"Failed to pull changes: {str(e)}")

    def create_tag(
        self, repo_path: str, tag_name: str, message: str = None, commit: str = "HEAD"
    ) -> str:
        """Create a new Git tag"""
        with self._get_repo_lock(repo_path):
            repo = self._get_repo(repo_path)
            try:
                if message:
                    repo.create_tag(tag_name, ref=commit, message=message)
                else:
                    repo.create_tag(tag_name, ref=commit)
                return f"Created tag '{tag_name}'"
            except Exception as e:
                raise ValueError(f"Failed to create tag: {str(e)}")

    def list_tags(self, repo_path: str) -> List[Dict[str, str]]:
        """List all tags in the repository"""
        repo = self._get_repo(repo_path)
        try:
            tags = []
            for tag in repo.tags:
                tags.append(
                    {
                        "name": tag.name,
                        "commit": tag.commit.hexsha,
                        "date": tag.commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S %z"),
                    }
                )
            return tags
        except Exception as e:
            raise ValueError(f"Failed to list tags: {str(e)}")

    def optimize_repo(self, repo_path: str) -> str:
        """Optimize the Git repository"""
        repo = self._get_repo(repo_path)
        try:
            repo.git.gc("--aggressive", "--prune=now")
            return "Repository optimized successfully"
        except Exception as e:
            raise ValueError(f"Failed to optimize repository: {str(e)}")

    def configure_auth(self, repo_path: str, username: str, password: str) -> str:
        """Configure authentication for repository operations"""
        if not username or not password:
            raise ValueError("Username and password required for HTTPS authentication")
        # Note: Storing passwords in git config is not secure
        # Consider using git credential store or credential manager
        with self._get_repo_lock(repo_path):
            repo = self._get_repo(repo_path)
            with repo.config_writer() as config:
                config.set_value("user", "name", username)
                config.set_value("user", "password", password)
            return "Authentication configured successfully"

    def register_webhook(self, repo_path: str, webhook: Dict[str, Any]) -> str:
        """Register a webhook for Git events"""
        # Note: This is a placeholder implementation. In a real-world scenario, you would need to handle webhooks
        # using Git hooks or a custom implementation.
        hook_path = os.path.join(repo_path, ".git", "hooks", "post-commit")
        with open(hook_path, "w") as hook_file:
            hook_file.write(
                f"#!/bin/sh\ncurl -X POST {webhook['url']} -d @- <<'EOF'\n$(git log -1 --pretty=format:'%H')\nEOF\n"
            )
        os.chmod(hook_path, 0o755)
        return "Webhook registered successfully"

    def restore_file_version(self, repo_path: str, file_path: str, version: str) -> bool:
        """Restore a file to a specific version"""
        try:
            # Get the file content at the specified version
            content = self.get_file_content(repo_path, file_path, version)
            # Write that content to the current file
            full_path = os.path.join(repo_path, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            # Add and commit the change
            self.add_files(repo_path, [file_path])
            self.commit_changes(repo_path, f"Restored file to version {version}")
            return True
        except Exception as e:
            logger.error(f"Error restoring file version: {e}", exc_info=True)
            return False


class GitRepoPath(BaseModel):
    repo_path: str = Field(..., description="Path to the Git repository")


class GitCommitRequest(GitRepoPath):
    files: List[str] = Field(..., description="List of files to add")
    message: str = Field(..., description="Commit message")
    author_name: Optional[str] = Field(None, description="Author name")
    author_email: Optional[str] = Field(None, description="Author email")


class GitDiffRequest(GitRepoPath):
    file_path: Optional[str] = Field(None, description="Path to the file to diff")
    target: Optional[str] = Field(None, description="Target to diff against")


class GitLogRequest(GitRepoPath):
    max_count: int = Field(10, description="Maximum number of commits to return")
    file_path: Optional[str] = Field(None, description="Path to the file to get log for")


class GitBranchRequest(GitRepoPath):
    branch_name: str = Field(..., description="Name of the branch to create")
    base_branch: Optional[str] = Field(
        None, description="Base branch to create the new branch from"
    )


class GitCheckoutRequest(GitRepoPath):
    branch_name: str = Field(..., description="Name of the branch to checkout")
    create: bool = Field(False, description="Create the branch if it doesn't exist")


class GitCloneRequest(BaseModel):
    repo_url: str = Field(..., description="URL of the repository to clone")
    local_path: str = Field(..., description="Path to clone the repository to")
    auth_token: Optional[str] = Field(
        None, description="Authentication token for private repositories"
    )


class GitRemoveFileRequest(GitRepoPath):
    file_path: str = Field(..., description="Path to the file to remove")


class GitFileContentRequest(GitRepoPath):
    file_path: str = Field(..., description="Path to the file")
    version: str = Field(..., description="Git version to get the file content from")


class GitLFSRequest(GitRepoPath):
    file_patterns: List[str] = Field(..., description="List of file patterns to track with LFS")


class GitBatchCommitRequest(GitRepoPath):
    file_groups: List[List[str]] = Field(
        ..., description="List of file groups to commit in batches"
    )
    message_template: str = Field(..., description="Template for commit messages")


class GitPullRequest(GitRepoPath):
    remote: str = Field("origin", description="Remote to pull from")
    branch: Optional[str] = Field(None, description="Branch to pull")
    all_remotes: bool = Field(False, description="Fetch from all remotes")


class GitTagRequest(GitRepoPath):
    tag_name: str = Field(..., description="Tag name")
    message: Optional[str] = Field(None, description="Tag message")
    commit: str = Field("HEAD", description="Commit to tag")


class GitTagsResponse(BaseModel):
    tags: List[Dict[str, str]] = Field(..., description="List of tags")


class GitWebhook(BaseModel):
    url: str = Field(..., description="Webhook URL")
    events: List[str] = Field(..., description="List of events to trigger the webhook")
    secret: Optional[str] = Field(None, description="Webhook secret")


router = APIRouter()
git_service = GitService()


@router.post(
    "/status",
    response_model=Dict[str, Any],
    summary="Get repository status",
    description="Get the status of a Git repository, including the current branch, staged changes, and unstaged changes.",
)
async def get_status(request: GitRepoPath = Body(...)):
    """Get the status of a Git repository."""
    try:
        return git_service.get_status(request.repo_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post(
    "/diff",
    response_model=str,
    summary="Get diff of changes",
    description="Get the difference between working directory and HEAD or a specified target.",
)
async def get_diff(request: GitDiffRequest = Body(...)):
    """Get the difference between working directory and HEAD or a specified target."""
    try:
        return git_service.get_diff(request.repo_path, request.file_path, request.target)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get diff: {str(e)}")


@router.post(
    "/add",
    response_model=str,
    summary="Stage files for commit",
    description="Stage files for commit.",
)
async def add_files(request: GitCommitRequest = Body(...)):
    """Stage files for commit."""
    try:
        return git_service.add_files(request.repo_path, request.files)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add files: {str(e)}")


@router.post(
    "/commit",
    response_model=str,
    summary="Commit changes",
    description="Commit staged changes with a commit message. Optionally, specify the author name and email.",
)
async def commit_changes(request: GitCommitRequest = Body(...)):
    """Commit staged changes with a commit message. Optionally, specify the author name and email."""
    try:
        return git_service.commit_changes(
            request.repo_path, request.message, request.author_name, request.author_email
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to commit changes: {str(e)}")


@router.post(
    "/reset",
    response_model=str,
    summary="Reset staged changes",
    description="Reset all staged changes.",
)
async def reset_changes(request: GitRepoPath = Body(...)):
    """Reset all staged changes."""
    try:
        return git_service.reset_changes(request.repo_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset changes: {str(e)}")


@router.post(
    "/log",
    response_model=List[Dict[str, Any]],
    summary="Get commit log",
    description="Get the commit log of the repository",
)
async def get_log(request: GitLogRequest = Body(...)):
    """Get the commit log of the repository."""
    try:
        return git_service.get_log(request.repo_path, request.max_count, request.file_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get log: {str(e)}")


@router.post(
    "/branch",
    response_model=str,
    summary="Create branch",
    description="Create a new branch from a base branch.",
)
async def create_branch(request: GitBranchRequest = Body(...)):
    """Create a new branch from a base branch."""
    try:
        return git_service.create_branch(
            request.repo_path, request.branch_name, request.base_branch
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create branch: {str(e)}")
