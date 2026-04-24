import os
import uuid
import logging
from pathlib import Path
from fastapi import UploadFile, HTTPException
from app.core.config import settings

logger = logging.getLogger(__name__)


async def save_upload_file(upload_file: UploadFile) -> tuple[str, str]:
    """保存上传文件，返回 (文件路径, 文件类型)
    
    检查点：
    - 文件大小限制（默认 50MB）
    - 空文件检查
    """
    # 检查文件大小
    content = await upload_file.read()
    file_size = len(content)
    
    if file_size == 0:
        raise HTTPException(400, "上传文件为空")
    
    if file_size > settings.MAX_UPLOAD_SIZE:
        max_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
        raise HTTPException(400, f"文件大小超过限制（最大 {max_mb:.0f}MB）")
    
    # 确保上传目录存在
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # 生成唯一文件名
    file_ext = Path(upload_file.filename).suffix.lower()
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # 保存文件
    with open(file_path, "wb") as f:
        f.write(content)

    file_type = file_ext.lstrip(".")
    logger.info(f"文件上传成功: {upload_file.filename} -> {file_path} ({file_size} bytes)")
    return file_path, file_type