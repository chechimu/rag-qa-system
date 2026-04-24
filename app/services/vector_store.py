from typing import List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.chunk import Chunk
import json

class VectorStore:
    def __init__(self, db: Session):
        self.db = db

    def add_chunks(self, document_id: int, chunks: List[str], embeddings: List[List[float]]):
        """将 chunk 和向量存入数据库"""
        for idx, (content, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = Chunk(
                document_id=document_id,
                content=content,
                chunk_index=idx,
                token_count=len(content),
                embedding=embedding
            )
            self.db.add(chunk)
        self.db.commit()

    def similarity_search(self, query_embedding: List[float], top_k: int = 4) -> List[Tuple[Chunk, float]]:
        """余弦相似度检索（无用户过滤，用于管理后台等场景）"""
        query = text("""
            SELECT 
                chunks.id,
                chunks.document_id,
                chunks.content,
                chunks.chunk_index,
                chunks.token_count,
                chunks.created_at,
                chunks.updated_at,
                1 - (embedding <=> :query_embedding) as similarity
            FROM chunks
            ORDER BY embedding <=> :query_embedding
            LIMIT :top_k
        """)
        result = self.db.execute(
            query,
            {"query_embedding": json.dumps(query_embedding), "top_k": top_k}
        )
        chunks_with_scores = []
        for row in result:
            chunk = Chunk(
                id=row.id,
                document_id=row.document_id,
                content=row.content,
                chunk_index=row.chunk_index,
                token_count=row.token_count,
                created_at=row.created_at,
                updated_at=row.updated_at
            )
            chunks_with_scores.append((chunk, row.similarity))
        return chunks_with_scores

    def hybrid_search(
            self,
            query: str,
            query_embedding: List[float],
            user_id: int,
            top_k: int = 8,
            vector_weight: float = 0.7,
            text_weight: float = 0.3
    ) -> List[Tuple[Chunk, float]]:
        """
        混合检索：向量相似度 + 全文检索相关性，加权融合
        简化实现：分别获取向量检索和全文检索结果，在 Python 中融合，避免 SQL 复杂性
        """
        # 1. 向量检索（取 top_k * 2 候选）
        vector_results = self.similarity_search_by_user(
            query_embedding, user_id, top_k=top_k * 2
        )
        
        # 2. 全文检索（取 top_k * 2 候选）
        text_query = text("""
            SELECT c.id, c.document_id, c.content, c.chunk_index, c.token_count,
                   c.created_at, c.updated_at,
                   ts_rank(c.content_tsv, plainto_tsquery('simple_chinese', :query)) as text_score
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.user_id = :user_id
              AND c.content_tsv @@ plainto_tsquery('simple_chinese', :query)
            ORDER BY text_score DESC
            LIMIT :candidate_k
        """)
        text_result = self.db.execute(
            text_query,
            {"query": query, "user_id": user_id, "candidate_k": top_k * 2}
        )
        
        text_results = []
        for row in text_result:
            chunk = Chunk(
                id=row.id, document_id=row.document_id, content=row.content,
                chunk_index=row.chunk_index, token_count=row.token_count,
                created_at=row.created_at, updated_at=row.updated_at
            )
            text_results.append((chunk, row.text_score))
        
        # 3. 归一化并融合分数
        # vector_score 已经是 0~1（余弦相似度）
        # text_score 范围不定，需要归一化
        max_text_score = max([s for _, s in text_results]) if text_results else 1.0
        if max_text_score == 0:
            max_text_score = 1.0
        
        # 合并结果，加权融合
        combined_scores = {}
        
        # 向量结果
        for chunk, score in vector_results:
            combined_scores[chunk.id] = {
                'chunk': chunk,
                'score': score * vector_weight,
                'vector_score': score,
                'text_score': 0.0
            }
        
        # 全文结果
        for chunk, score in text_results:
            normalized_text_score = score / max_text_score
            if chunk.id in combined_scores:
                combined_scores[chunk.id]['score'] += normalized_text_score * text_weight
                combined_scores[chunk.id]['text_score'] = normalized_text_score
            else:
                combined_scores[chunk.id] = {
                    'chunk': chunk,
                    'score': normalized_text_score * text_weight,
                    'vector_score': 0.0,
                    'text_score': normalized_text_score
                }
        
        # 按融合分数排序，取 top_k
        sorted_results = sorted(
            combined_scores.values(),
            key=lambda x: x['score'],
            reverse=True
        )[:top_k]
        
        return [(item['chunk'], item['score']) for item in sorted_results]

    def similarity_search_by_user(
        self,
        query_embedding: List[float],
        user_id: int,
        top_k: int = 4
    ) -> List[Tuple[Chunk, float]]:
        """只检索属于指定用户的文档块"""
        query = text("""
            SELECT 
                chunks.id,
                chunks.document_id,
                chunks.content,
                chunks.chunk_index,
                chunks.token_count,
                chunks.created_at,
                chunks.updated_at,
                1 - (embedding <=> :query_embedding) as similarity
            FROM chunks
            JOIN documents ON chunks.document_id = documents.id
            WHERE documents.user_id = :user_id
            ORDER BY embedding <=> :query_embedding
            LIMIT :top_k
        """)
        result = self.db.execute(
            query,
            {
                "query_embedding": json.dumps(query_embedding),
                "user_id": user_id,
                "top_k": top_k
            }
        )
        chunks_with_scores = []
        for row in result:
            chunk = Chunk(
                id=row.id,
                document_id=row.document_id,
                content=row.content,
                chunk_index=row.chunk_index,
                token_count=row.token_count,
                created_at=row.created_at,
                updated_at=row.updated_at
            )
            chunks_with_scores.append((chunk, row.similarity))
        return chunks_with_scores

    def delete_document_chunks(self, document_id: int):
        """删除文档的所有 chunks"""
        self.db.query(Chunk).filter(Chunk.document_id == document_id).delete()
        self.db.commit()