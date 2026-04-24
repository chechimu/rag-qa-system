from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"

# 连接池配置
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,           # 连接池大小
    max_overflow=20,        # 超出 pool_size 时最多创建的连接数
    pool_timeout=30,        # 获取连接的超时时间
    pool_recycle=3600,      # 连接回收时间（1小时）
    echo=settings.DEBUG     # DEBUG 模式下打印 SQL
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """获取独立的数据库 session（用于后台任务等）"""
    return SessionLocal()