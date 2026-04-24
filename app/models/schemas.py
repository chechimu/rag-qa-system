from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


# 文档相关
class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    document_id: int
    filename: str
    status: str


# 问答相关
class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    stream: bool = False


class SourceInfo(BaseModel):
    document_id: int
    chunk_id: int
    content: str
    similarity: float


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    sources: List[SourceInfo]


# 历史记录
class ConversationResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    metadata: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    session_id: str
    last_message_at: datetime
    message_count: int
    preview: str