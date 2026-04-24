from sqlalchemy import Column, String, Integer, Text, Enum, ForeignKey
from app.db.base import BaseModel
import enum

class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"

class Document(BaseModel):
    __tablename__ = "documents"

    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(10), nullable=False)
    file_size = Column(Integer, default=0)
    status = Column(String(20), default=DocumentStatus.UPLOADED.value)
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # 添加 user_id 外键，关联 users 表
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)