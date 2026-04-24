from sqlalchemy import Column, String, Text, JSON, Integer, ForeignKey
from app.db.base import BaseModel


class Conversation(BaseModel):
    __tablename__ = "conversations"

    session_id = Column(String(64), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    meta_info = Column(JSON, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)