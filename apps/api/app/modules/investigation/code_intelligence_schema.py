"""Public, bounded rule-analysis response; it never carries source text."""
from typing import Literal

from pydantic import BaseModel, Field


class Signal(BaseModel):
    kind: Literal['traceback', 'path', 'identifier', 'function', 'method', 'class', 'exception', 'import_error', 'module', 'title_term']
    value: str = Field(max_length=300)
    origin: Literal['title', 'body']
    line: int = Field(ge=1, le=200)
    source_line: int | None = Field(default=None, ge=1, le=1000000)
    symbol: str | None = Field(default=None, max_length=64)


class Node(BaseModel):
    id: str = Field(max_length=100)
    chunk_id: str = Field(max_length=36)
    path: str = Field(max_length=512)
    name: str = Field(max_length=512)
    kind: Literal['file', 'module', 'class', 'function', 'method']
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    parent: str | None = Field(max_length=64)
    is_async: bool


class Edge(BaseModel):
    type: Literal['DEFINES', 'MEMBER_OF', 'IMPORTS_UNRESOLVED', 'IMPORTS_POTENTIAL',
                  'CALLS_STATIC', 'CALLS_AMBIGUOUS', 'CALLS_UNKNOWN']
    source: str = Field(max_length=100)
    target: str = Field(max_length=128)
    chunk_id: str = Field(max_length=36)


class Citation(BaseModel):
    chunk_id: str
    path: str
    symbol: str | None
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    snapshot_id: str
    commit_sha: str
    url: str


class Finding(BaseModel):
    rule_id: Literal['traceback_location', 'explicit_source_match', 'exception_alignment', 'import_alignment']
    chunk_id: str
    citation: Citation
    signals: list[Signal] = Field(max_length=4)
    explanation: str = Field(max_length=500)
    next_steps: list[str] = Field(max_length=4)
    limitations: list[str] = Field(max_length=4)
    uncertainty: Literal['high']


class CandidateScore(BaseModel):
    chunk_id: str
    baseline_rank: int = Field(ge=1, le=30)
    signal_points: int = Field(ge=0, le=16)
    relationship_points: int = Field(ge=0, le=1)


class AnalysisResponse(BaseModel):
    version: Literal['cie-v1']
    label: Literal['RULE-BASED ANALYSIS — POSSIBLE CAUSES, NOT VERIFIED']
    job_id: str
    repository_id: str
    snapshot_id: str
    commit_sha: str
    signals: list[Signal] = Field(max_length=40)
    nodes: list[Node] = Field(max_length=500)
    edges: list[Edge] = Field(max_length=1000)
    candidate_ranking: list[CandidateScore] = Field(max_length=20)
    findings: list[Finding] = Field(max_length=10)
    abstained: bool
    limitations: list[str] = Field(max_length=16)
    bytes_parsed: int = Field(ge=0, le=65536)
