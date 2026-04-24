from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import documents, chat, history, auth, metrics
from app.core.config import settings
from app.services.cache_service import cache
from app.db.session import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(history.router)
app.include_router(metrics.router)

@app.get("/health")
async def health_check():
    """健康检查端点"""
    health = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "services": {}
    }
    
    # 检查数据库连接
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        health["services"]["database"] = "connected"
    except Exception as e:
        health["services"]["database"] = f"error: {str(e)}"
        health["status"] = "degraded"
    
    # 检查 Redis
    if cache.enabled:
        health["services"]["redis"] = "connected"
    else:
        health["services"]["redis"] = "disabled"
    
    return health

@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)