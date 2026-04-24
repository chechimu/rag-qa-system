import json
import logging
from typing import Optional, Any
import redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis 缓存服务"""
    
    def __init__(self):
        self.client = None
        self.enabled = False
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 测试连接
            self.client.ping()
            self.enabled = True
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.warning(f"Redis 连接失败，缓存功能将禁用: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if not self.enabled:
            return None
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Redis get 失败: {e}")
            return None
    
    def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """设置缓存，默认1小时过期"""
        if not self.enabled:
            return False
        try:
            self.client.setex(key, expire, json.dumps(value))
            return True
        except Exception as e:
            logger.warning(f"Redis set 失败: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self.enabled:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis delete 失败: {e}")
            return False
    
    def clear_pattern(self, pattern: str) -> bool:
        """按模式删除缓存"""
        if not self.enabled:
            return False
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
            return True
        except Exception as e:
            logger.warning(f"Redis clear_pattern 失败: {e}")
            return False


# 全局缓存实例
cache = CacheService()
