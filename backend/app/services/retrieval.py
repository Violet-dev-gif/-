from __future__ import annotations


class RetrievalService:
    """
    Version1 占位检索层。后续可替换为 Milvus/pgvector 实现。
    """

    async def search(self, question: str) -> list[str]:
        if not question.strip():
            return []
        return []
