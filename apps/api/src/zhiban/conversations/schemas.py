"""Conversation and message request/response schemas."""

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateConversationRequest(ApiModel):
    title: str = Field(default="新对话", max_length=200)


class UpdateConversationRequest(ApiModel):
    title: str = Field(min_length=1, max_length=200)


class ConversationView(ApiModel):
    id: str
    title: str
    status: str
    created_at: str
    updated_at: str


class ConversationPage(ApiModel):
    data: list[ConversationView]
    next_cursor: str | None = None
    has_more: bool = False


class CreateMessageRequest(ApiModel):
    content: str = Field(min_length=1, max_length=20000)
    client_message_id: str | None = Field(default=None, min_length=1, max_length=128)
    model: str | None = Field(default=None, min_length=1, max_length=128)


class MessageView(ApiModel):
    id: str
    role: str
    content: str
    status: str
    created_at: str


class MessagePage(ApiModel):
    data: list[MessageView]
    next_cursor: str | None = None
    has_more: bool = False


class RunAccepted(ApiModel):
    """Response for the two-phase message+run creation."""

    message_id: str
    assistant_message_id: str
    run_id: str
    status: str
    stream_url: str
