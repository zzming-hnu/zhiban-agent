from fastapi import APIRouter

from zhiban.api.health import router as health_router
from zhiban.api.models import router as models_router
from zhiban.auth.router import router as auth_router
from zhiban.conversations.router import router as conversations_router
from zhiban.conversations.runs_router import router as runs_router
from zhiban.memory.router import router as memories_router
from zhiban.todos.router import router as todos_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(models_router)
api_router.include_router(auth_router)
api_router.include_router(conversations_router)
api_router.include_router(runs_router)
api_router.include_router(memories_router)
api_router.include_router(todos_router)
