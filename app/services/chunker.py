from typing import List
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings

logger = logging.getLogger(__name__)


class TextChunker:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""]
        )

    def split(self, texts: List[str]) -> List[str]:
        """将文档段落列表切分为 chunk，并去重"""
        all_chunks = []
        for text in texts:
            chunks = self.text_splitter.split_text(text)
            all_chunks.extend(chunks)
        
        # 去重：移除完全相同的 chunk
        unique_chunks = []
        seen = set()
        for chunk in all_chunks:
            chunk_normalized = chunk.strip().lower()
            if chunk_normalized and chunk_normalized not in seen:
                seen.add(chunk_normalized)
                unique_chunks.append(chunk)
        
        if len(unique_chunks) < len(all_chunks):
            logger.info(f"Chunk 去重: {len(all_chunks)} -> {len(unique_chunks)} (移除 {len(all_chunks) - len(unique_chunks)} 个重复)")
        
        return unique_chunks