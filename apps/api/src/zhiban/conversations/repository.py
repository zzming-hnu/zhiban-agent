"""Repository for conversations and messages with enforced user scoping."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zhiban.db.models import Conversation, Message


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: uuid.UUID, title: str) -> Conversation:
        conv = Conversation(user_id=user_id, title=title or "新对话")
        self._session.add(conv)
        await self._session.flush()
        return conv

    async def get(self, *, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
        result = await self._session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.status != "deleted",
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        user_id: uuid.UUID,
        cursor: tuple[datetime, uuid.UUID] | None,
        limit: int,
    ) -> list[Conversation]:
        query = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.status == "active",
        )
        if cursor is not None:
            updated_at, conv_id = cursor
            query = query.where(
                (Conversation.updated_at < updated_at)
                | ((Conversation.updated_at == updated_at) & (Conversation.id < conv_id))
            )
        query = query.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).limit(
            limit + 1
        )
        result = await self._session.execute(query)
        return list(result.scalars())

    async def update_title(
        self, *, user_id: uuid.UUID, conversation_id: uuid.UUID, title: str
    ) -> Conversation | None:
        conv = await self.get(user_id=user_id, conversation_id=conversation_id)
        if conv is None:
            return None
        conv.title = title
        return conv

    async def soft_delete(self, *, user_id: uuid.UUID, conversation_id: uuid.UUID) -> bool:
        conv = await self.get(user_id=user_id, conversation_id=conversation_id)
        if conv is None:
            return False
        conv.status = "deleted"
        conv.deleted_at = datetime.now(UTC)
        return True


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        client_message_id: str | None = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            user_id=user_id,
            role=role,
            content=content,
            status="completed",
            client_message_id=client_message_id,
        )
        self._session.add(msg)
        await self._session.flush()
        return msg

    async def get_by_client_id(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        client_message_id: str,
    ) -> Message | None:
        result = await self._session.execute(
            select(Message).where(
                Message.user_id == user_id,
                Message.conversation_id == conversation_id,
                Message.client_message_id == client_message_id,
                Message.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        cursor: tuple[datetime, uuid.UUID] | None,
        limit: int,
    ) -> list[Message]:
        query = select(Message).where(
            Message.user_id == user_id,
            Message.conversation_id == conversation_id,
            Message.deleted_at.is_(None),
        )
        if cursor is not None:
            created_at, msg_id = cursor
            query = query.where(
                (Message.created_at > created_at)
                | ((Message.created_at == created_at) & (Message.id > msg_id))
            )
        query = query.order_by(Message.created_at.asc(), Message.id.asc()).limit(limit + 1)
        result = await self._session.execute(query)
        return list(result.scalars())
