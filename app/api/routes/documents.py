from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from fastapi import Depends
import os
import logging

from app.db.session import get_db, get_db_session
from app.models.document import Document, DocumentStatus
from app.models.schemas import DocumentUploadResponse, DocumentResponse
from app.utils.file_utils import save_upload_file
from app.services.document_parser import DocumentParser
from app.services.chunker import TextChunker
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore
from app.core.config import settings
from app.api.dependencies import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


def process_document_background(document_id: int, file_path: str, file_type: str):
    """后台处理文档：解析、切分、向量化
    
    ⚠️ 使用独立的数据库 session，避免后台任务异步执行时 session 已关闭
    """
    db = get_db_session()
    try:
        # 更新状态为解析中
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error(f"文档 {document_id} 不存在")
            return
            
        doc.status = DocumentStatus.PARSING.value
        db.commit()

        # 解析文档
        parser = DocumentParser()
        texts, parse_info = parser.parse(file_path, file_type)
        
        # 记录解析信息
        logger.info(f"文档 {document_id} 解析完成: {parse_info}")
        
        # 检查解析质量
        if parse_info.get("quality_warning"):
            logger.warning(f"文档 {document_id} 解析质量警告: {parse_info['quality_warning']}")

        # 切分文本
        doc.status = DocumentStatus.CHUNKING.value
        db.commit()
        chunker = TextChunker()
        chunks = chunker.split(texts)
        
        if not chunks:
            raise ValueError("文档切分后没有产生有效 chunk，请检查文档内容")

        # 向量化
        doc.status = DocumentStatus.EMBEDDING.value
        db.commit()
        embedding_service = EmbeddingService()
        embeddings = embedding_service.embed_documents(chunks)

        # 存入向量库
        vector_store = VectorStore(db)
        vector_store.add_chunks(document_id, chunks, embeddings)

        # 更新文档状态
        doc.status = DocumentStatus.COMPLETED.value
        doc.chunk_count = len(chunks)
        db.commit()
        logger.info(f"文档 {document_id} 处理完成，共 {len(chunks)} 个 chunks")

    except Exception as e:
        logger.error(f"文档 {document_id} 处理失败: {e}", exc_info=True)
        try:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = DocumentStatus.FAILED.value
                doc.error_message = str(e)[:500]  # 限制错误信息长度
                db.commit()
        except Exception as rollback_err:
            logger.error(f"更新文档失败状态出错: {rollback_err}")
    finally:
        db.close()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)  # 获取当前登录用户
):
    # 验证文件类型
    allowed_types = ["pdf", "docx", "txt", "md"]
    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in allowed_types:
        raise HTTPException(400, f"不支持的文件类型，仅支持: {', '.join(allowed_types)}")

    # 保存文件
    file_path, file_type = await save_upload_file(file)
    file_size = os.path.getsize(file_path)

    # 创建数据库记录，关联当前用户
    document = Document(
        filename=file.filename,
        file_path=file_path,
        file_type=file_type,
        file_size=file_size,
        status=DocumentStatus.UPLOADED.value,
        user_id=current_user.id  # 关键：设置文档所属用户
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # 添加后台任务处理（不再传递 db session，后台任务会创建独立 session）
    background_tasks.add_task(
        process_document_background,
        document.id,
        file_path,
        file_type
    )

    return DocumentUploadResponse(
        document_id=document.id,
        filename=document.filename,
        status=document.status
    )


@router.get("/{document_id}/status")
async def get_document_status(
        document_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)  # 需要认证
):
    # 只查询属于当前用户的文档
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    if not doc:
        raise HTTPException(404, "文档不存在或无权访问")
    return {
        "id": doc.id,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "error_message": doc.error_message
    }


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
        skip: int = 0,
        limit: int = 20,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)  # 需要认证
):
    # 只返回当前用户的文档
    docs = db.query(Document)\
        .filter(Document.user_id == current_user.id)\
        .order_by(Document.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    return docs