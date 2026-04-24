import openai
import time
from typing import List, Dict, Any, Generator
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=90.0
        )
        self.model = settings.LLM_MODEL
        self.max_retries = 3
        self.retry_delay = 2  # 重试间隔秒数

    def _create_messages(self, query: str, context: str, history: List[Dict[str, str]] = None) -> List[Dict]:
        """构建消息列表"""
        system_prompt = """你是一个文档问答助手。请基于以下【文档内容】回答用户问题。

请遵守以下规则：
1. 必须基于【文档内容】回答，不要回答"文档中未提及相关内容"，除非文档真的完全空白。
2. 即使文档片段的相关度较低，也请尽量从中提取有用信息回答。
3. 对于概括性问题（如"主要讲了什么"），请综合所有片段内容给出全面回答。
4. 回答时引用文档中的关键原文作为依据。
5. 回答应简洁、准确，使用中文。

【文档内容】
{context}
"""
        formatted_system = system_prompt.format(context=context)
        
        messages = [{"role": "system", "content": formatted_system}]

        # 添加历史对话（最近几轮）
        if history:
            messages.extend(history[-6:])  # 保留最近3轮对话

        # 添加当前查询
        messages.append({"role": "user", "content": query})
        return messages

    def generate_answer(
        self,
        query: str,
        context: str,
        history: List[Dict[str, str]] = None,
        stream: bool = False
    ) -> str | Generator:
        """基于上下文和历史生成回答，带重试机制"""
        messages = self._create_messages(query, context, history)
        
        # 调试：记录实际发送的 context 长度和内容预览
        logger.info(f"LLM context length: {len(context)} chars")
        logger.info(f"LLM context preview: {context[:500]}...")

        if stream:
            return self._generate_stream(messages)
        else:
            return self._generate_sync(messages)
    
    def _generate_sync(self, messages: List[Dict]) -> str:
        """同步生成，带重试"""
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1024
                )
                content = response.choices[0].message.content
                if content and content.strip():
                    return content
                logger.warning(f"LLM 返回空内容，尝试重试 ({attempt + 1}/{self.max_retries})")
            except Exception as e:
                logger.error(f"LLM error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # 指数退避
                else:
                    return "抱歉，生成回答时出现错误，请稍后重试。"
        return "抱歉，服务暂时不可用，请稍后重试。"
    
    def _generate_stream(self, messages: List[Dict]) -> Generator:
        """流式生成，带重试"""
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=1024
                )
                return response
            except Exception as e:
                logger.error(f"LLM stream error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
        
        # 返回错误生成器
        def error_generator():
            yield {
                "choices": [{"delta": {"content": "生成回答时出错，请稍后重试。"}}]
            }
        return error_generator()