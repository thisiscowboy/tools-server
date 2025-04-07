import os
import tempfile
from typing import List, Optional, Dict, Any, Union
import git
from git import Repo
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field
from app.utils.config import get_config

router = APIRouter()


class GitRepoPath(BaseModel):
    repo_path: str = Field(..., description="Path to the Git repository")


class GitAddRequest(GitRepoPath):
    files: List[str] = Field(..., description="List of files to add")


class GitCommitRequest(GitRepoPath):
    message: str = Field(..., description="Commit message")
    author_name: Optional[str] = Field(None, description="Author name")
    author_email: Optional[str] = Field(None, description="Author email")


class GitStatusRequest(GitRepoPath):
    pass


class GitDiffRequest(GitRepoPath):
    file_path: Optional[str] = Field(None, description="Path to the file to diff")
    target: Optional[str] = Field(None, description="Target to diff against")


class GitLogRequest(GitRepoPath):
    max_count: int = Field(10, description="Maximum number of commits to return")
    file_path: Optional[str] = Field(None, description="Path to the file to get log for")


class GitBranchRequest(GitRepoPath):
    branch_name: str = Field(..., description="Name of the branch")
    base_branch: Optional[str] = Field(
        None, description="Base branch to create the new branch from"
    )


class GitCheckoutRequest(GitRepoPath):
    branch_name: str = Field(..., description="Name of the branch to checkout")
    create: bool = Field(False, description="Create the branch if it doesn't exist")


class GitCloneRequest(BaseModel):
    repo_url: str = Field(..., description="URL of the repository to clone")
    local_path: str = Field(..., description="Local path to clone the repository to")
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
    remote: str = Field("origin", description="Name of the remote")
    branch: Optional[str] = Field(None, description="Branch to pull")


class GitFetchRequest(GitRepoPath):
    remote: str = Field("origin", description="Name of the remote")
    all_remotes: bool = Field(False, description="Fetch from all remotes")


class GitCreateTagRequest(GitRepoPath):
    tag_name: str = Field(..., description="Name of the tag to create")
    message: Optional[str] = Field(None, description="Tag message")
    commit: str = Field("HEAD", description="Commit to tag")


class TagInfo(BaseModel):
    name: str = Field(..., description="Tag name")
    commit: str = Field(..., description="Tagged commit hash")
    date: str = Field(..., description="Date of tagged commit")


class GitTagsResponse(BaseModel):
    tags: List[TagInfo] = Field(..., description="List of tags")


class GitService:
    def __init__(self):
        config = get_config()
        self.default_username = config.default_git_username
        self.default_email = config.default_git_email
        self.temp_auth_files = {}

    def _get_repo(self, repo_path: str) -> git.Repo:
        """Get git repository object"""
        try:
            repo = Repo(repo_path)
            return repo
        except git.exc.InvalidGitRepositoryError:
            raise ValueError(f"Invalid Git repository at '{repo_path}'")
        except Exception as e:
            raise ValueError(f"Failed to get repository: {str(e)}")

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
        repo = self._get_repo(repo_path)
        repo.git.reset()
        return "All staged changes reset"

    def get_log(
        self, repo_path: str, max_count: int = 10, file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get commit log"""
        repo = self._get_repo(repo_path)
        if file_path:
            # Get log for specific file
            commits = list(repo.iter_commits(paths=file_path, max_count=max_count))
        else:
            # Get log for entire repo
            commits = list(repo.iter_commits(max_count=max_count))
        commit_data = []
        for commit in commits:
            commit_data.append(
                {
                    "hash": commit.hexsha,
                    "author": f"{commit.author.name} <{commit.author.email}>",
                    "date": commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S %z"),
                    "message": commit.message.strip(),
                }
            )
        return {"commits": commit_data}

    def create_branch(
        self, repo_path: str, branch_name: str, base_branch: Optional[str] = None
    ) -> str:
        """Create a new branch"""
        repo = self._get_repo(repo_path)
        if base_branch:
            base = repo.refs[base_branch]
        else:
            base = repo.active_branch
        repo.create_head(branch_name, base)
        return f"Created branch '{branch_name}'"

    def checkout_branch(self, repo_path: str, branch_name: str, create: bool = False) -> str:
        """Checkout a branch"""
        repo = self._get_repo(repo_path)
        if create:
            # Create branch if it doesn't exist
            if branch_name not in repo.refs:
                repo.create_head(branch_name)
        # Checkout the branch
        repo.git.checkout(branch_name)
        return f"Switched to branch '{branch_name}'"

    def clone_repo(self, repo_url: str, local_path: str, auth_token: Optional[str] = None) -> str:
        """Clone a Git repository"""
        try:
            # If auth token is provided, modify the URL
            if auth_token:
                # Parse the URL to insert authentication
                if repo_url.startswith("https://"):
                    parsed_url = repo_url.replace(
                        "https://", f"https://x-access-token:{auth_token}@"
                    )
                    repo = git.Repo.clone_from(parsed_url, local_path)
                else:
                    # For SSH or other protocols, use standard clone
                    repo = git.Repo.clone_from(repo_url, local_path)
            else:
                repo = git.Repo.clone_from(repo_url, local_path)
            return f"Successfully cloned repository to '{local_path}'"
        except Exception as e:
            raise ValueError(f"Failed to clone repository: {str(e)}")

    def remove_file(self, repo_path: str, file_path: str) -> str:
        """Remove a file from Git"""
        repo = self._get_repo(repo_path)
        try:
            repo.index.remove([file_path])
            return f"Successfully removed {file_path} from Git"
        except Exception as e:
            raise ValueError(f"Failed to remove file: {str(e)}")

    def get_file_content_at_version(self, repo_path: str, file_path: str, version: str) -> str:
        """Get file content at a specific Git version"""
        repo = self._get_repo(repo_path)
        try:
            return repo.git.show(f"{version}:{file_path}")
        except Exception as e:
            raise ValueError(f"Failed to get file content at version {version}: {str(e)}")

    def setup_lfs(self, repo_path: str, file_patterns: List[str]) -> str:
        """Configure Git LFS for the repository"""
        repo = self._get_repo(repo_path)
        try:
            # Initialize LFS
            repo.git.execute(["git", "lfs", "install"])
            # Track file patterns
            for pattern in file_patterns:
                repo.git.execute(["git", "lfs", "track", pattern])
            # Add .gitattributes
            repo.git.add(".gitattributes")
            repo.git.commit("-m", "Set up Git LFS tracking")
            return "Git LFS configured successfully"
        except Exception as e:
            raise ValueError(f"Failed to set up Git LFS: {str(e)}")

    def batch_commit(
        self, repo_path: str, file_groups: List[List[str]], message_template: str
    ) -> List[str]:
        """Commit files in batches for better performance"""
        repo = self._get_repo(repo_path)
        commit_hashes = []
        for i, files in enumerate(file_groups):
            repo.git.add(files)
            commit = repo.index.commit(f"{message_template} (batch {i+1}/{len(file_groups)})")
            commit_hashes.append(commit.hexsha)
        return commit_hashes

    def pull(self, repo_path: str, remote: str = "origin", branch: str = None) -> str:
        """Pull changes from remote repository"""
        repo = self._get_repo(repo_path)
        try:
            if branch:
                result = repo.git.pull(remote, branch)
            else:
                result = repo.git.pull(remote)
            return result
        except Exception as e:
            raise ValueError(f"Failed to pull changes: {str(e)}")

    def fetch(self, repo_path: str, remote: str = "origin", all_remotes: bool = False) -> str:
        """Fetch changes from remote repository"""
        repo = self._get_repo(repo_path)
        try:
            if all_remotes:
                result = repo.git.fetch(all=True)
            else:
                result = repo.git.fetch(remote)
            return result
        except Exception as e:
            raise ValueError(f"Failed to fetch changes: {str(e)}")

    def create_tag(
        self, repo_path: str, tag_name: str, message: str = None, commit: str = "HEAD"
    ) -> str:
        """Create a new Git tag"""
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


git_service = GitService()


@router.post(
    "/status",
    response_model=Dict[str, Any],
    summary="Get repository status",
    description="Get the current status of a Git repository, including the current branch, staged changes, and unstaged changes.",
)
async def get_status(request: GitStatusRequest = Body(...)):
    """
    Get the current status of a Git repository.
    Returns the current branch, staged changes, and unstaged changes.
    """
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
    description="Get difference between working directory and HEAD or a specified target",
)
async def get_diff(request: GitDiffRequest = Body(...)):
    """
    Get difference between working directory and HEAD or a specified target.
    Show diff for specific files or the entire repository.
    """
    try:
        return git_service.get_diff(request.repo_path, request.file_path, request.target)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get diff: {str(e)}")


@router.post(
    "/add", response_model=str, summary="Stage files", description="Stage files for commit"
)
async def add_files(request: GitAddRequest = Body(...)):
    """
    Stage files for commit.
    Adds the specified files to the staging area.
    """
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
    description="Commit staged changes with a commit message.",
)
async def commit_changes(request: GitCommitRequest = Body(...)):
    """
    Commit staged changes with a commit message.
    Optionally, specify the author name and email.
    """
    try:
        return git_service.commit_changes(
            request.repo_path, request.message, request.author_name, request.author_email
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to commit changes: {str(e)}")


@router.post(
    "/log",
    response_model=Dict[str, Any],
    summary="Get commit log",
    description="Get the commit history of the repository",
)
async def get_log(request: GitLogRequest = Body(...)):
    """
    Get the commit history of the repository.
    Returns a list of commits with hash, author, date, and message.
    """
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
    description="Create a new branch in the repository",
)
async def create_branch(request: GitBranchRequest = Body(...)):
    """
    Create a new branch in the repository.
    Optionally, specify the base branch to create the new branch from.
    """
    try:
        return git_service.create_branch(
            request.repo_path, request.branch_name, request.base_branch
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create branch: {str(e)}")


@router.post(
    "/checkout", response_model=str, summary="Checkout branch", description="Checkout a branch"
)
async def checkout_branch(request: GitCheckoutRequest = Body(...)):
    """
    Checkout a branch.
    Optionally, create the branch if it doesn't exist.
    """
    try:
        return git_service.checkout_branch(request.repo_path, request.branch_name, request.create)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to checkout branch: {str(e)}")


@router.post(
    "/clone",
    response_model=str,
    summary="Clone repository",
    description="Clone a Git repository from a URL",
)
async def clone_repo(request: GitCloneRequest = Body(...)):
    """
    Clone a Git repository from a URL.
    Clones the repository from the specified URL to a local path.
    """
    try:
        return git_service.clone_repo(request.repo_url, request.local_path, request.auth_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clone repository: {str(e)}")


@router.post(
    "/remove",
    response_model=str,
    summary="Remove file",
    description="Remove a file from the repository",
)
async def remove_file(request: GitRemoveFileRequest = Body(...)):
    """
    Remove a file from the repository.
    Removes the specified file from the Git repository.
    """
    try:
        return git_service.remove_file(request.repo_path, request.file_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove file: {str(e)}")


@router.post(
    "/file-content",
    response_model=str,
    summary="Get file content",
    description="Get file content at a specific Git version",
)
async def get_file_content(request: GitFileContentRequest = Body(...)):
    """
    Get file content at a specific Git version.
    Returns the content of the specified file at the given version.
    """
    try:
        return git_service.get_file_content_at_version(
            request.repo_path, request.file_path, request.version
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get file content: {str(e)}")


@router.post(
    "/lfs",
    response_model=str,
    summary="Set up Git LFS",
    description="Configure Git LFS for the repository",
)
async def setup_lfs(request: GitLFSRequest = Body(...)):
    """
    Configure Git LFS for the repository.
    Tracks the specified file patterns with Git LFS.
    """
    try:
        return git_service.setup_lfs(request.repo_path, request.file_patterns)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set up Git LFS: {str(e)}")


@router.post(
    "/batch-commit",
    response_model=List[str],
    summary="Batch commit",
    description="Commit files in batches",
)
async def batch_commit(request: GitBatchCommitRequest = Body(...)):
    """
    Commit files in batches.
    Commits the specified file groups in batches for better performance.
    """
    try:
        return git_service.batch_commit(
            request.repo_path, request.file_groups, request.message_template
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to batch commit: {str(e)}")


@router.post(
    "/pull",
    response_model=str,
    summary="Pull changes",
    description="Pull changes from a remote repository",
)
async def pull_changes(request: GitPullRequest = Body(...)):
    """
    Pull changes from a remote repository.
    Fetches and merges changes from the specified remote and branch.
    """
    try:
        return git_service.pull(request.repo_path, request.remote, request.branch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pull changes: {str(e)}")


@router.post(
    "/fetch",
    response_model=str,
    summary="Fetch changes",
    description="Fetch changes from a remote repository",
)
async def fetch_changes(request: GitFetchRequest = Body(...)):
    """
    Fetch changes from a remote repository.
    Downloads objects and refs from the specified remote.
    """
    try:
        return git_service.fetch(request.repo_path, request.remote, request.all_remotes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch changes: {str(e)}")


@router.post(
    "/tag/create",
    response_model=str,
    summary="Create tag",
    description="Create a new tag in the repository",
)
async def create_tag(request: GitCreateTagRequest = Body(...)):
    """
    Create a new tag in the repository.
    Tags a specific commit with a name and optional message.
    """
    try:
        return git_service.create_tag(
            request.repo_path, request.tag_name, request.message, request.commit
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create tag: {str(e)}")


@router.post(
    "/tags",
    response_model=GitTagsResponse,
    summary="List tags",
    description="List all tags in the repository",
)
async def list_tags(request: GitRepoPath = Body(...)):
    """
    List all tags in the repository.
    Returns tag names, associated commits, and dates.
    """
    try:
        tags = git_service.list_tags(request.repo_path)
        return {"tags": tags}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tags: {str(e)}")
