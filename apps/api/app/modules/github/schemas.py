from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field


class GitHubID(BaseModel):
    id: int = Field(gt=0, le=2**63 - 1)


class RepoPayload(GitHubID):
    private: bool


class IssuePayload(GitHubID):
    number: int = Field(gt=0, le=2**31 - 1)
    title: str = Field(min_length=1, max_length=1024)
    body: str | None = Field(default=None, max_length=900_000)
    state: Literal["open", "closed"]
    updated_at: AwareDatetime


class IssueEvent(BaseModel):
    action: Literal["opened", "edited"]
    installation: GitHubID
    repository: RepoPayload
    issue: IssuePayload


class LifecycleEvent(BaseModel):
    action: str
    installation: GitHubID
    repositories_removed: list[GitHubID] = Field(default_factory=list)
