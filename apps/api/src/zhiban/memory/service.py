"""Memory domain service: candidate → decision → persistence."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from zhiban.db.models import Memory, MemoryCandidate
from zhiban.llm.embedding import EmbeddingAdapter
from zhiban.memory.ids import candidate_idempotency_key, conflict_key, memory_fingerprint
from zhiban.memory.normalize import normalize_text
from zhiban.memory.repository import MemoryRepository
from zhiban.memory.schemas import MemoryCandidatePayload
from zhiban.memory.types import (
    Decision,
    MemoryStatus,
    RejectReason,
    SourceKind,
    resolve_category,
)
from zhiban.memory.validator import validate_candidate


class MemoryService:
    def __init__(self, session: AsyncSession, embedding: EmbeddingAdapter | None = None) -> None:
        self._session = session
        self._embedding = embedding
        self.repo = MemoryRepository(session)

    async def _embed(self, text: str) -> list[float] | None:
        """Generate an embedding for text; returns None on failure (degraded)."""
        if self._embedding is None:
            return None
        try:
            return await self._embedding.embed(text)
        except Exception:  # noqa: BLE001 - embedding is best-effort
            return None

    def _render_content(self, candidate: MemoryCandidatePayload) -> str:
        subject = normalize_text(candidate.subject)
        predicate = normalize_text(candidate.predicate)
        value = normalize_text(candidate.value)
        return f"{subject} {predicate} {value}".strip()

    async def process_candidate(
        self,
        *,
        user_id: uuid.UUID,
        candidate: MemoryCandidatePayload,
        source_kind: str,
        extractor_version: str,
        available_message_ids: set[uuid.UUID],
        available_message_texts: dict[uuid.UUID, str],
    ) -> tuple[str | None, MemoryCandidate]:
        """Validate, decide, and persist one candidate.

        Returns ``(decision, candidate_record)``; ``decision`` is None when rejected.
        """
        fingerprint = memory_fingerprint(
            user_id=user_id,
            memory_type=candidate.memory_type,
            subject=candidate.subject,
            predicate=candidate.predicate,
            value=candidate.value,
        )
        ckey = conflict_key(
            user_id=user_id,
            memory_type=candidate.memory_type,
            subject=candidate.subject,
            predicate=candidate.predicate,
        )
        payload = candidate.model_dump(mode="json")
        source_ids_str: list[str] = payload["source_message_ids"]
        idem_key = candidate_idempotency_key(
            user_id=user_id,
            extractor_version=extractor_version,
            source_message_ids=candidate.source_message_ids,
            canonical_candidate=candidate.model_dump_json(),
        )

        # Idempotent replay.
        existing_candidate = await self.repo.get_candidate_by_idempotency_key(
            user_id=user_id, idempotency_key=idem_key
        )
        if existing_candidate is not None:
            return existing_candidate.decision, existing_candidate

        record = MemoryCandidate(
            user_id=user_id,
            idempotency_key=idem_key,
            payload=payload,
            source_message_ids=source_ids_str,
            extractor_version=extractor_version,
            status="processing",
        )
        await self.repo.upsert_candidate(record)

        # Validate.
        validation = validate_candidate(
            candidate,
            source_kind=source_kind,
            available_message_ids=available_message_ids,
            available_message_texts=available_message_texts,
        )
        if not validation.ok:
            record.status = "rejected"
            record.reject_reason = validation.reason.value if validation.reason else None
            await self._session.commit()
            return None, record

        # Decide.
        decision = await self._decide(
            user_id=user_id, candidate=candidate, fingerprint=fingerprint, ckey=ckey
        )

        if decision == Decision.add:
            content = self._render_content(candidate)
            # Deterministic category resolution: identity/person/event must be
            # basic_info, regardless of what the LLM guessed.
            category = resolve_category(candidate.memory_type, candidate.category)
            memory = Memory(
                user_id=user_id,
                memory_type=candidate.memory_type,
                category=category,
                subject=normalize_text(candidate.subject),
                predicate=normalize_text(candidate.predicate),
                value=normalize_text(candidate.value),
                content=content,
                source_kind=source_kind,
                status=MemoryStatus.active,
                confidence=candidate.confidence,
                importance=candidate.importance,
                fingerprint=fingerprint,
                conflict_key=ckey,
                embedding=await self._embed(content),
                source_message_ids=source_ids_str,
                evidence_quote=candidate.evidence_quote,
                expires_at=candidate.valid_until,
                last_evidenced_at=datetime.now(UTC),
            )
            await self.repo.add(memory)
            record.status = "accepted"
            record.decision = Decision.add
            record.target_memory_id = memory.id
        elif decision == Decision.update:
            record.status = "accepted"
            record.decision = Decision.update
        elif decision == Decision.ignore:
            record.status = "rejected"
            record.reject_reason = RejectReason.duplicate
            record.decision = Decision.ignore
        elif decision == Decision.delete:
            record.status = "accepted"
            record.decision = Decision.delete

        record.processed_at = datetime.now(UTC)
        await self._session.commit()
        return decision, record

    async def _decide(
        self,
        *,
        user_id: uuid.UUID,
        candidate: MemoryCandidatePayload,
        fingerprint: str,
        ckey: str,
    ) -> str:
        """Decide add/update/ignore based on dedupe and conflict rules."""
        # Exact duplicate (same fingerprint) -> ignore.
        exact = await self.repo.get_active_by_fingerprint(user_id=user_id, fingerprint=fingerprint)
        if exact is not None:
            return Decision.ignore

        # Same conflict slot (same type+subject+predicate, different value) -> update/supersede.
        conflicts = await self.repo.get_active_by_conflict_key(user_id=user_id, conflict_key=ckey)
        if conflicts:
            return Decision.update

        return Decision.add

    async def get_memory(self, *, user_id: uuid.UUID, memory_id: uuid.UUID) -> Memory | None:
        return await self.repo.get(user_id=user_id, memory_id=memory_id)

    async def list_memories(self, *, user_id: uuid.UUID, limit: int = 100) -> list[Memory]:
        return await self.repo.list_active(user_id=user_id, limit=limit)

    async def soft_delete(self, *, user_id: uuid.UUID, memory_id: uuid.UUID) -> bool:
        memory = await self.repo.get(user_id=user_id, memory_id=memory_id)
        if memory is None:
            return False
        memory.status = MemoryStatus.deleted
        memory.deleted_at = datetime.now(UTC)
        await self._session.commit()
        return True

    async def update_value(
        self,
        *,
        user_id: uuid.UUID,
        memory_id: uuid.UUID,
        value: str | None,
        category: str | None,
        importance: float | None,
    ) -> Memory | None:
        memory = await self.repo.get(user_id=user_id, memory_id=memory_id)
        if memory is None:
            return None
        if value is not None:
            memory.value = normalize_text(value)
            memory.content = f"{memory.subject} {memory.predicate} {memory.value}".strip()
            # Recompute fingerprint and clear stale embedding.
            memory.fingerprint = memory_fingerprint(
                user_id=user_id,
                memory_type=memory.memory_type,
                subject=memory.subject,
                predicate=memory.predicate,
                value=memory.value,
            )
            memory.embedding = None
        if category is not None:
            memory.category = category
        if importance is not None:
            memory.importance = importance
        memory.version += 1
        await self._session.commit()
        return memory


def source_kind_for(user_content: str) -> SourceKind:
    """Determine source_kind: explicit if the user asked to remember, else implicit."""
    from zhiban.memory.extractor import detect_explicit_request

    return SourceKind.explicit if detect_explicit_request(user_content) else SourceKind.implicit
