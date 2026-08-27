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
        # Negation is rendered as a prefix on the predicate ("不喜欢") rather
        # than being baked into the value, so the content reads naturally and
        # the predicate stays stable for slot-conflict detection.
        if candidate.negated and not predicate.startswith("不"):
            predicate = f"不{predicate}"
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
            negated=candidate.negated,
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
        decision, supersede_target = await self._decide(
            user_id=user_id,
            candidate=candidate,
            fingerprint=fingerprint,
            ckey=ckey,
            source_kind=source_kind,
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
                negated=candidate.negated,
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
            # Same slot (type+subject+predicate) but a new value: the user's fact
            # evolved. Persist the new fact as active and mark the old one as
            # superseded, linking them via superseded_by_id so the evolution chain
            # is preserved (supports "you used to ... now ..." recall).
            content = self._render_content(candidate)
            category = resolve_category(candidate.memory_type, candidate.category)
            memory = Memory(
                user_id=user_id,
                memory_type=candidate.memory_type,
                category=category,
                subject=normalize_text(candidate.subject),
                predicate=normalize_text(candidate.predicate),
                value=normalize_text(candidate.value),
                negated=candidate.negated,
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
            if supersede_target is not None:
                supersede_target.status = MemoryStatus.superseded
                supersede_target.superseded_by_id = memory.id
            record.status = "accepted"
            record.decision = Decision.update
            record.target_memory_id = memory.id
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
        source_kind: str,
    ) -> tuple[str, Memory | None]:
        """Decide add/update/ignore based on dedupe and conflict rules.

        Returns ``(decision, supersede_target)``: when the decision is ``update``,
        ``supersede_target`` is the active memory that the new value supersedes.
        """
        # Exact duplicate (same fingerprint) -> ignore.
        exact = await self.repo.get_active_by_fingerprint(user_id=user_id, fingerprint=fingerprint)
        if exact is not None:
            return Decision.ignore, None

        # Same conflict slot (same type+subject+predicate after canonicalization)
        # -> update/supersede. Prefer to supersede the most recently updated
        # active memory. Explicit memories (user asked to remember) are the
        # user's authoritative statement; if the incoming candidate is implicit
        # and an explicit memory already occupies the slot, ignore the implicit
        # candidate instead of superseding the explicit one.
        conflicts = await self.repo.get_active_by_conflict_key(user_id=user_id, conflict_key=ckey)
        if conflicts:
            # If the incoming candidate is implicit but an explicit memory
            # already exists in this slot, keep the explicit one (drop implicit).
            if source_kind == "implicit" and any(
                m.source_kind == "explicit" for m in conflicts
            ):
                return Decision.ignore, None
            target = max(conflicts, key=lambda m: m.updated_at)
            return Decision.update, target

        return Decision.add, None

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
                negated=memory.negated,
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
