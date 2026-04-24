from typing import List, Dict, Tuple, Generator
from sqlalchemy.orm import Session
from app.services.embedding_service import EmbeddingService
from app.services.reranker import RerankerService
from app.services.vector_store import VectorStore
from app.services.llm_service import LLMService
from app.services.cache_service import cache
from app.models.conversation import Conversation
import logging
import json
import hashlib

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore(db)
        self.llm_service = LLMService()
        self.reranker = RerankerService()
    
    def _get_cache_key(self, query: str, user_id: int) -> str:
        """生成缓存 key"""
        key_data = f"rag:{user_id}:{query}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get_conversation_history(self, session_id: str, user_id: int, limit: int = 10) -> List[Dict[str, str]]:
        """获取对话历史"""
        conversations = self.db.query(Conversation) \
            .filter(Conversation.user_id == user_id, Conversation.session_id == session_id) \
            .order_by(Conversation.created_at.desc()) \
            .limit(limit) \
            .all()

        history = []
        for conv in reversed(conversations):
            history.append({"role": conv.role, "content": conv.content})
        return history

    def save_message(self, session_id: str, role: str, content: str, metadata: Dict = None, user_id: int = None):
        """保存对话消息"""
        conversation = Conversation(
            session_id=session_id,
            role=role,
            content=content,
            meta_info=metadata,
            user_id=user_id
        )
        self.db.add(conversation)
        self.db.commit()

    async def answer(
        self,
        query: str,
        session_id: str,
        user_id: int,
        stream: bool = False
    ) -> Tuple[str, List[Dict]] | Generator:
        """RAG 问答主流程"""
        # 1. 保存用户消息
        self.save_message(session_id, "user", query, user_id=user_id)

        # 2. 获取对话历史
        history = self.get_conversation_history(session_id, user_id)

        # 3. 检查缓存（仅非流式模式）
        if not stream:
            cache_key = self._get_cache_key(query, user_id)
            cached_result = cache.get(f"rag:answer:{cache_key}")
            if cached_result:
                logger.info(f"缓存命中: {query[:50]}...")
                return cached_result["answer"], cached_result["sources"]

        # 4. 生成查询向量
        query_embedding = self.embedding_service.embed_query(query)

        # 5. 检索相关文档块
        chunks_with_scores = self.vector_store.hybrid_search(
            query=query,
            query_embedding=query_embedding,
            user_id=user_id,
            top_k=20,
            vector_weight=0.7,
            text_weight=0.3
        )
        
        # 兜底：如果混合检索返回空，降级为纯向量检索
        if not chunks_with_scores:
            logger.warning("混合检索返回空，降级为纯向量检索")
            chunks_with_scores = self.vector_store.similarity_search_by_user(
                query_embedding=query_embedding,
                user_id=user_id,
                top_k=20
            )

        # 重排序（用 rerank 分数，更可靠）
        if chunks_with_scores:
            reranked = await self.reranker.rerank(
                query=query,
                chunks_with_scores=chunks_with_scores,
                top_k=10
            )
            chunks_with_scores = reranked

        # 记录所有分数用于调试
        logger.info(f"Retrieved {len(chunks_with_scores)} chunks for query: {query[:50]}")
        for i, (chunk, score) in enumerate(chunks_with_scores):
            logger.info(f"  [{i}] score={score:.4f}, doc={chunk.document_id}, content={chunk.content[:80]}")

        # 过滤低相似度（rerank 分数通常在 0~1 范围，但可能偏低）
        SIMILARITY_THRESHOLD = 0.001
        relevant_chunks = [(c, s) for c, s in chunks_with_scores if s > SIMILARITY_THRESHOLD]
        
        # 兜底逻辑：如果过滤后太少，补充高分结果直到至少 5 个
        MIN_CONTEXT_CHUNKS = 5
        if len(relevant_chunks) < MIN_CONTEXT_CHUNKS and chunks_with_scores:
            seen_ids = {c.id for c, _ in relevant_chunks}
            for c, s in chunks_with_scores:
                if c.id not in seen_ids:
                    relevant_chunks.append((c, s))
                    seen_ids.add(c.id)
                if len(relevant_chunks) >= MIN_CONTEXT_CHUNKS:
                    break
        
        # 如果还是空的，取前 3 个（极端兜底）
        if not relevant_chunks and chunks_with_scores:
            relevant_chunks = chunks_with_scores[:3]

        logger.info(f"Final context: {len(relevant_chunks)} chunks (threshold={SIMILARITY_THRESHOLD})")

        # 6. 构建上下文（带编号和相似度，帮助 LLM 判断相关性）
        context_parts = []
        sources = []
        for i, (chunk, score) in enumerate(relevant_chunks):
            context_parts.append(f"[片段 {i+1}] (相关度: {score:.3f})\n{chunk.content}")
            sources.append({
                "document_id": chunk.document_id,
                "chunk_id": chunk.id,
                "content": chunk.content[:300] + "...",
                "similarity": float(score)
            })

        context = "\n\n---\n\n".join(context_parts)

        # 7. 生成回答
        if stream:
            response_stream = self.llm_service.generate_answer(
                query=query,
                context=context,
                history=history,
                stream=True
            )
            return response_stream, sources
        else:
            answer = self.llm_service.generate_answer(
                query=query,
                context=context,
                history=history,
                stream=False
            )
            # 保存助手回复
            self.save_message(session_id, "assistant", answer, {"sources": sources}, user_id=user_id)
            
            # 缓存结果（仅缓存有有效来源的回答）
            if sources:
                cache_key = self._get_cache_key(query, user_id)
                cache.set(f"rag:answer:{cache_key}", {
                    "answer": answer,
                    "sources": sources
                }, expire=1800)  # 缓存30分钟
            
            return answer, sources
