from typing import Protocol


class GitHubClient(Protocol):
    """Inject into future services; Sprint 1 makes no external GitHub API calls."""

    def get_public_repository(self, owner: str, name: str) -> dict: ...
