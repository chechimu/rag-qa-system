from sqlalchemy import Column, String, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db.base import BaseModel
from sqlalchemy import Computed
from sqlalchemy.dialects.postgresql import TSVECTOR

class Chunk(BaseModel):
    __tablename__ = "chunks"

    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    token_count = Column(Integer, default=0)
    embedding = Column(Vector(1024), nullable=True)  # 维度根据实际 embedding 模型调整

    # 新增：全文检索字段（自动生成 tsvector）
    content_tsv = Column(
        TSVECTOR,
        Computed("to_tsvector('simple_chinese', content)", persisted=True)
    )

    # 这里只保留全文索引！向量索引我们在init_db里手动创建，避免SQLAlchemy自动创建的兼容问题
    __table_args__ = (
        Index("ix_chunks_content_tsv", content_tsv, postgresql_using="gin"),  # 全文索引
    )

    document = relationship("Document", backref="chunks")