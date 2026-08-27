"""Memory schemas: candidate payload and API views."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MemoryCandidatePayload(ApiModel):
    """A structured memory candidate produced by the LLM extractor."""

    memory_type: Literal[
        "identity", "preference", "habit", "person", "event", "task", "temporary", "communication"
    ]
    category: Literal["basic_info", "communication_taboo", "communication_preference", "other"] = (
        "other"
    )
    subject: str = Field(min_length=1, max_length=80)
    predicate: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=500)
    negated: bool = False
    source_message_ids: list[uuid.UUID] = Field(min_length=1, max_length=8)
    evidence_quote: str = Field(min_length=1, max_length=240)
    confidence: float = Field(ge=0, le=1)
    importance: float = Field(ge=0, le=1)
    valid_until: datetime | None = None


class MemoryView(ApiModel):
    id: str
    memory_type: str
    category: str
    subject: str
    predicate: str
    value: str
    negated: bool = False
    content: str
    source_kind: str
    status: str
    confidence: float
    importance: float
    evidence_quote: str
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class MemoryPage(ApiModel):
    data: list[MemoryView]
    next_cursor: str | None = None
    has_more: bool = False


class CreateMemoryRequest(ApiModel):
    memory_type: Literal[
        "identity", "preference", "habit", "person", "event", "task", "temporary", "communication"
    ]
    category: Literal["basic_info", "communication_taboo", "communication_preference", "other"] = (
        "other"
    )
    subject: str = Field(min_length=1, max_length=80)
    predicate: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=500)
    negated: bool = False


class UpdateMemoryRequest(ApiModel):
    value: str | None = Field(default=None, max_length=500)
    category: (
        Literal["basic_info", "communication_taboo", "communication_preference", "other"] | None
    ) = None
    importance: float | None = Field(default=None, ge=0, le=1)
    expires_at: datetime | None = None
