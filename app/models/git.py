from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union


class GitRepoPath(BaseModel):
    repo_path: str = Field(..., description="File system path to the Git repository.")


class GitStatusRequest(GitRepoPath):
    pass


class GitDiffRequest(GitRepoPath):
    file_path: Optional[str] = Field(None, description="Specific file to show diff for")
    target: Optional[str] = Field(None, description="The branch or commit to diff against.")


class GitCommitRequest(GitRepoPath):
    message: str = Field(..., description="Commit message for recording the change.")
    author_name: Optional[str] = Field(None, description="Git author name")
    author_email: Optional[str] = Field(None, description="Git author email")


class GitAddRequest(GitRepoPath):
    files: List[str] = Field(..., description="List of file paths to add to the staging area.")


class GitLogRequest(GitRepoPath):
    max_count: int = Field(10, description="Maximum number of commits to retrieve.")
    file_path: Optional[str] = Field(None, description="Filter log by specific file")


class GitCreateBranchRequest(GitRepoPath):
    branch_name: str = Field(..., description="Name of the branch to create.")
    base_branch: Optional[str] = Field(
        None, description="Optional base branch name to create the new branch from."
    )


class GitCheckoutRequest(GitRepoPath):
    branch_name: str = Field(..., description="Branch name to checkout.")
    create: bool = Field(False, description="Whether to create the branch if it doesn't exist")


class GitInitRequest(GitRepoPath):
    bare: bool = Field(False, description="Whether to create a bare repository")


class GitCloneRequest(BaseModel):
    repo_url: str = Field(..., description="URL of the repository to clone")
    local_path: str = Field(..., description="Local path to clone to")
    auth_token: Optional[str] = Field(None, description="Authentication token if needed")


class CommitInfo(BaseModel):
    hash: str = Field(..., description="Commit hash")
    author: str = Field(..., description="Commit author")
    date: str = Field(..., description="Commit date")
    message: str = Field(..., description="Commit message")


class GitStatusResponse(BaseModel):
    clean: bool = Field(..., description="Whether the working directory is clean")
    current_branch: str = Field(..., description="Current active branch")
    staged_files: List[str] = Field(..., description="Files staged for commit")
    unstaged_files: List[str] = Field(..., description="Files with changes not staged")
    untracked_files: List[str] = Field(..., description="Untracked files")


class GitLogResponse(BaseModel):
    commits: List[CommitInfo] = Field(..., description="List of commits")
