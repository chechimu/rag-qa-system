from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.document import Document
from app.models.conversation import Conversation
from app.models.user import User
from app.api.dependencies import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/")
async def get_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户统计指标"""
    
    # 文档统计
    doc_stats = db.query(
        func.count(Document.id).label("total"),
        func.sum(Document.chunk_count).label("total_chunks")
    ).filter(
        Document.user_id == current_user.id
    ).first()
    
    # 状态分布
    status_counts = db.query(
        Document.status,
        func.count(Document.id).label("count")
    ).filter(
        Document.user_id == current_user.id
    ).group_by(Document.status).all()
    
    # 对话统计
    conv_stats = db.query(
        func.count(Conversation.id).label("total_messages")
    ).filter(
        Conversation.user_id == current_user.id
    ).first()
    
    return {
        "documents": {
            "total": doc_stats.total or 0,
            "total_chunks": doc_stats.total_chunks or 0,
            "status_distribution": {s.status: s.count for s in status_counts}
        },
        "conversations": {
            "total_messages": conv_stats.total_messages or 0
        }
    }
