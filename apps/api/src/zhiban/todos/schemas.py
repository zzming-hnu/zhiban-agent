"""Todo and reminder request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateTodoRequest(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(default="", max_length=2000)
    due_at: datetime | None = None
    timezone: str = Field(default="Asia/Shanghai", max_length=50)
    priority: int = Field(default=1, ge=0, le=3)


class TodoView(ApiModel):
    id: str
    title: str
    detail: str
    status: str
    due_at: datetime | None = None
    priority: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class CreateReminderRequest(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    remind_at: datetime
    timezone: str = Field(default="Asia/Shanghai", max_length=50)
    todo_id: str | None = None
    recurrence: str = Field(default="none", max_length=16)
    recurrence_end_at: datetime | None = None


class ReminderView(ApiModel):
    id: str
    title: str
    remind_at: datetime
    timezone: str
    recurrence: str = "none"
    recurrence_end_at: datetime | None = None
    status: str
    delivery_status: str
    delivered_at: datetime | None = None
    created_at: datetime
