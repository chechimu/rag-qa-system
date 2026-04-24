import time
import logging
from functools import wraps
from fastapi import Request, HTTPException
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    """简单的内存限流器（基于滑动窗口）
    
    生产环境建议使用 Redis 实现分布式限流
    """
    
    def __init__(self):
        # 存储请求记录: {key: [(timestamp, count), ...]}
        self.requests: Dict[str, list] = {}
        self.window_size = 60  # 窗口大小（秒）
        self.max_requests = 60  # 每窗口最大请求数
    
    def is_allowed(self, key: str) -> Tuple[bool, int]:
        """检查是否允许请求，返回 (是否允许, 剩余次数)"""
        now = time.time()
        window_start = now - self.window_size
        
        # 清理过期记录
        if key in self.requests:
            self.requests[key] = [
                (t, c) for t, c in self.requests[key] if t > window_start
            ]
        else:
            self.requests[key] = []
        
        # 计算当前窗口内的请求总数
        total = sum(c for t, c in self.requests[key])
        
        if total >= self.max_requests:
            return False, 0
        
        # 记录本次请求
        self.requests[key].append((now, 1))
        remaining = self.max_requests - total - 1
        return True, remaining


# 全局限流器实例
rate_limiter = RateLimiter()


def rate_limit(requests_per_minute: int = 60):
    """限流装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # 使用 IP + 路径作为限流 key
            client_ip = request.client.host if request.client else "unknown"
            key = f"{client_ip}:{request.url.path}"
            
            allowed, remaining = rate_limiter.is_allowed(key)
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail="请求过于频繁，请稍后再试",
                    headers={"Retry-After": "60"}
                )
            
            # 添加限流响应头
            response = await func(request, *args, **kwargs)
            if hasattr(response, 'headers'):
                response.headers["X-RateLimit-Remaining"] = str(remaining)
            return response
        return wrapper
    return decorator
