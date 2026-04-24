import httpx
from typing import List, Tuple
from app.core.config import settings
from app.models.chunk import Chunk

class RerankerService:
    def __init__(self):
        self.api_key = settings.LLM_API_KEY  # 复用硅基流动密钥
        self.base_url = settings.LLM_BASE_URL
        self.model = "BAAI/bge-reranker-v2-m3"

    async def rerank(
        self,
        query: str,
        chunks_with_scores: List[Tuple[Chunk, float]],
        top_k: int = 4
    ) -> List[Tuple[Chunk, float]]:
        if len(chunks_with_scores) <= top_k:
            return chunks_with_scores

        documents = [chunk.content for chunk, _ in chunks_with_scores]
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/rerank",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "query": query,
                    "documents": documents,
                    "top_n": top_k
                }
            )
            response.raise_for_status()
            data = response.json()

        reranked = []
        for item in data.get("results", []):
            idx = item["index"]
            score = item["relevance_score"]
            reranked.append((chunks_with_scores[idx][0], score))
        return reranked