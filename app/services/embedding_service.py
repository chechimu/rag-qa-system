from typing import List
import openai
from app.core.config import settings
import time
import logging
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=settings.EMBEDDING_API_KEY or settings.LLM_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL
        )
        self.model = settings.EMBEDDING_MODEL
        self.max_retries = 3
        self.retry_delay = 1

    def _normalize(self, vector: List[float]) -> List[float]:
        """对向量进行 L2 归一化"""
        norm = np.linalg.norm(vector)
        if norm > 0:
            return (np.array(vector) / norm).tolist()
        return vector

    def _embed_with_retry(self, texts: List[str]) -> List[List[float]]:
        """带重试的 embedding 生成"""
        for attempt in range(self.max_retries):
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=texts
                )
                embeddings = [item.embedding for item in response.data]
                return embeddings
            except Exception as e:
                logger.error(f"Embedding error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise e

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量生成文本向量（已归一化）"""
        if not texts:
            return []
            
        embeddings = []
        batch_size = 20  # 根据 API 限制调整
        failed_batches = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                batch_embeddings = self._embed_with_retry(batch)
                # 归一化处理
                normalized_batch = [self._normalize(emb) for emb in batch_embeddings]
                embeddings.extend(normalized_batch)
                time.sleep(0.3)  # 避免频率限制
            except Exception as e:
                logger.error(f"Batch {i//batch_size + 1} embedding failed: {e}")
                failed_batches.append(i)
                # 填充零向量作为占位（避免数据错位）
                dim = 1024  # bge-m3 维度
                embeddings.extend([[0.0] * dim] * len(batch))
        
        if failed_batches:
            logger.warning(f"共 {len(failed_batches)} 个 batch 失败，已用零向量填充")
            
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """为查询文本生成向量（已归一化）"""
        embeddings = self._embed_with_retry([text])
        return self._normalize(embeddings[0])