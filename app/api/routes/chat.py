from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import uuid
import json
import logging

from app.db.session import get_db
from app.models.schemas import ChatRequest, ChatResponse, SourceInfo
from app.services.rag_service import RAGService
from app.api.dependencies import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session_id = request.session_id or str(uuid.uuid4())
    rag_service = RAGService(db)

    # ⚠️ 关键：提前取出 user_id，避免在生成器内访问 ORM 属性导致 DetachedInstanceError
    user_id = current_user.id

    if request.stream:
        response_stream, sources = await rag_service.answer(
            query=request.query,
            session_id=session_id,
            user_id=user_id,
            stream=True
        )

        def generate():
            full_answer = ""
            try:
                for chunk in response_stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_answer += content
                        yield f"data: {json.dumps({'content': content})}\n\n"
            except Exception as e:
                logger.error(f"Stream generation error: {e}", exc_info=True)
                full_answer += " [生成中断，请重试]"
                yield f"data: {json.dumps({'content': ' [生成中断，请重试]'})}\n\n"
            finally:
                # 保存消息，使用提前保存的 user_id
                try:
                    rag_service.save_message(
                        session_id, "assistant", full_answer,
                        {"sources": sources}, user_id=user_id
                    )
                except Exception as save_err:
                    logger.error(f"Failed to save message: {save_err}")

                # 确保发送来源信息
                yield f"data: {json.dumps({'sources': sources, 'session_id': session_id})}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    else:
        answer, sources = await rag_service.answer(
            query=request.query,
            session_id=session_id,
            user_id=user_id,
            stream=False
        )
        source_infos = [SourceInfo(**s) for s in sources]
        return ChatResponse(answer=answer, session_id=session_id, sources=source_infos)