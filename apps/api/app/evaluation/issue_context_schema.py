"""Versioned, bounded issue context shared by capture and held-out validation."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.ingestion.code_selection import contains_sensitive_source

ShortText = Annotated[str, Field(max_length=250)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Comment(StrictModel):
    id: int = Field(gt=0, lt=2**63)
    created_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    updated_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    body: str | None = Field(max_length=2000)

    @model_validator(mode="after")
    def timestamps(self):
        created = datetime.strptime(self.created_at, "%Y-%m-%dT%H:%M:%SZ")
        updated = datetime.strptime(self.updated_at, "%Y-%m-%dT%H:%M:%SZ")
        if updated < created:
            raise ValueError("invalid_comment_timestamps")
        return self


class IssueContext(StrictModel):
    version: Literal["issue-context-v1"]
    issue_id: int = Field(gt=0, lt=2**63)
    number: int = Field(gt=0, lt=2**31)
    state: Literal["open", "closed"]
    created_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    updated_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    title: str = Field(min_length=1, max_length=3000)
    body: str | None = Field(max_length=10000)
    labels: list[ShortText] = Field(max_length=30)
    comment_count: int = Field(ge=0, le=30)
    comments: list[Comment] = Field(max_length=30)

    @model_validator(mode="after")
    def complete_context(self):
        created = datetime.strptime(self.created_at, "%Y-%m-%dT%H:%M:%SZ")
        updated = datetime.strptime(self.updated_at, "%Y-%m-%dT%H:%M:%SZ")
        if updated < created:
            raise ValueError("invalid_issue_timestamps")
        if self.comment_count != len(self.comments) or len({c.id for c in self.comments}) != len(self.comments):
            raise ValueError("incomplete_comments")
        texts = [self.title, self.body or "", *self.labels, *(c.body or "" for c in self.comments)]
        if any(contains_sensitive_source(value) for value in texts):
            raise ValueError("sensitive_issue_context")
        return self


def normalized_context(issue: IssueContext) -> dict:
    """Preserve every supplied field and order comments like the issue-context builder."""
    context = issue.model_dump(mode="json")
    context["comments"] = sorted(context["comments"], key=lambda item: (item["created_at"], item["id"]))
    return context


def context_digest(issue: IssueContext) -> str:
    raw = json.dumps(normalized_context(issue), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("ascii")).hexdigest()
