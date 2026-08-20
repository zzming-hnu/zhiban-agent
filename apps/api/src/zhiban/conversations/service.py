"""Conversation and message domain logic."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.conversations.repository import ConversationRepository, MessageRepository
from zhiban.conversations.runs import RunRepository
from zhiban.core.errors import AppError
from zhiban.db.models import AgentRun, Conversation, Message

Cursor = tuple[datetime, uuid.UUID] | None


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)
        self.runs = RunRepository(session)

    async def create(self, *, user_id: uuid.UUID, title: str) -> Conversation:
        return await self.conversations.create(user_id=user_id, title=title)

    async def get_or_404(self, *, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
        conv = await self.conversations.get(user_id=user_id, conversation_id=conversation_id)
        if conv is None:
            raise AppError(code="not_found", message="会话不存在", status_code=404)
        return conv

    async def list_conversations(
        self,
        *,
        user_id: uuid.UUID,
        cursor: Cursor,
        limit: int,
    ) -> tuple[list[Conversation], bool]:
        items = await self.conversations.list(user_id=user_id, cursor=cursor, limit=limit)
        has_more = len(items) > limit
        return items[:limit], has_more

    async def rename(
        self, *, user_id: uuid.UUID, conversation_id: uuid.UUID, title: str
    ) -> Conversation:
        await self.get_or_404(user_id=user_id, conversation_id=conversation_id)
        conv = await self.conversations.update_title(
            user_id=user_id, conversation_id=conversation_id, title=title
        )
        assert conv is not None
        return conv

    async def delete(self, *, user_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
        await self.get_or_404(user_id=user_id, conversation_id=conversation_id)
        await self.conversations.soft_delete(user_id=user_id, conversation_id=conversation_id)

    async def create_message(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        content: str,
        client_message_id: str | None,
    ) -> Message:
        await self.get_or_404(user_id=user_id, conversation_id=conversation_id)
        if client_message_id is not None:
            existing = await self.messages.get_by_client_id(
                user_id=user_id,
                conversation_id=conversation_id,
                client_message_id=client_message_id,
            )
            if existing is not None:
                raise AppError(
                    code="duplicate_message",
                    message="消息已存在",
                    status_code=409,
                )
        return await self.messages.create(
            user_id=user_id,
            conversation_id=conversation_id,
            role="user",
            content=content,
            client_message_id=client_message_id,
        )

    async def list_messages(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        cursor: Cursor,
        limit: int,
    ) -> tuple[list[Message], bool]:
        await self.get_or_404(user_id=user_id, conversation_id=conversation_id)
        items = await self.messages.list(
            user_id=user_id,
            conversation_id=conversation_id,
            cursor=cursor,
            limit=limit,
        )
        has_more = len(items) > limit
        return items[:limit], has_more

    async def start_run(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        content: str,
        client_message_id: str | None,
        model: str | None,
    ) -> tuple[Message, Message, AgentRun]:
        """Create user message + assistant placeholder + run in one transaction."""
        await self.get_or_404(user_id=user_id, conversation_id=conversation_id)
        if client_message_id is not None:
            existing = await self.messages.get_by_client_id(
                user_id=user_id,
                conversation_id=conversation_id,
                client_message_id=client_message_id,
            )
            if existing is not None:
                raise AppError(
                    code="duplicate_message",
                    message="消息已存在",
                    status_code=409,
                )

        # Cancel any interrupted active run before starting a new one.
        await self.runs.cancel_active_for_conversation(
            user_id=user_id, conversation_id=conversation_id
        )

        user_msg = await self.messages.create(
            user_id=user_id,
            conversation_id=conversation_id,
            role="user",
            content=content,
            client_message_id=client_message_id,
        )
        assistant_msg = await self.messages.create(
            user_id=user_id,
            conversation_id=conversation_id,
            role="assistant",
            content="",
        )
        assistant_msg.status = "generating"

        run = await self.runs.create(
            user_id=user_id,
            conversation_id=conversation_id,
            user_message_id=user_msg.id,
            assistant_message_id=assistant_msg.id,
            model=model,
        )
        return user_msg, assistant_msg, run

    async def get_run_or_404(self, *, user_id: uuid.UUID, run_id: uuid.UUID) -> AgentRun:
        return await self.runs.get_or_404(user_id=user_id, run_id=run_id)
