"""Authenticated principal derived from the server-side session."""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: uuid.UUID
    session_id: uuid.UUID
