"""Embedding adapter (OpenAI-compatible embeddings endpoint)."""

from typing import Any

import httpx2 as httpx

from zhiban.llm.errors import classify_http_error


class EmbeddingAdapter:
    def __init__(self, api_key: str, base_url: str, model: str = "text-embedding-3-small") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(timeout=30.0)

    async def embed(self, text: str) -> list[float]:
        response = await self._client.post(
            f"{self.base_url}/embeddings",
            json={"model": self.model, "input": text},
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        if response.status_code >= 400:
            raise classify_http_error(response.status_code, response.text[:500])
        data: dict[str, Any] = response.json()
        return list(data["data"][0]["embedding"])

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.post(
            f"{self.base_url}/embeddings",
            json={"model": self.model, "input": texts},
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        if response.status_code >= 400:
            raise classify_http_error(response.status_code, response.text[:500])
        data: dict[str, Any] = response.json()
        return [list(item["embedding"]) for item in data["data"]]

    async def aclose(self) -> None:
        await self._client.aclose()
