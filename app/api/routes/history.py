from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from typing import List

from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.schemas import ConversationResponse, SessionListResponse
from app.api.dependencies import get_current_user
from app.models.user import User
router = APIRouter(prefix="/history", tags=["history"])


@router.get("/sessions", response_model=List[SessionListResponse])
async def list_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 获取所有会话的摘要信息
    subquery = db.query(
        Conversation.session_id,
        func.max(Conversation.created_at).label("last_message_at"),
        func.count(Conversation.id).label("message_count"),
        func.max(Conversation.content).label("preview")
    ).filter(
        Conversation.user_id == current_user.id  # 过滤用户
    ).group_by(Conversation.session_id).subquery()

    sessions = db.query(subquery).order_by(subquery.c.last_message_at.desc()).all()

    return [
        SessionListResponse(
            session_id=s.session_id,
            last_message_at=s.last_message_at,
            message_count=s.message_count,
            preview=s.preview[:50] + "..." if len(s.preview) > 50 else s.preview
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=List[ConversationResponse])
async def get_conversation(session_id: str, limit: int = 50, db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    conversations = db.query(Conversation) \
        .filter(Conversation.user_id == current_user.id,Conversation.session_id == session_id) \
        .order_by(Conversation.created_at.asc()) \
        .limit(limit) \
        .all()

    if not conversations:
        raise HTTPException(404, "会话不存在")

    return conversations


@router.delete("/{session_id}")
async def delete_conversation(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = db.query(Conversation) \
        .filter(Conversation.user_id == current_user.id,Conversation.session_id == session_id) \
        .delete()
    db.commit()

    return {"deleted": result}