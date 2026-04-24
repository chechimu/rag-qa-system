import sys

sys.path.append(".")
from app.models.user import User
from app.db.base import Base
from app.db.session import engine
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.conversation import Conversation
from sqlalchemy import text


def init_db():
    print("Cleaning database...")
    with engine.connect() as conn:
        # 彻底清空整个public schema，不管之前有什么残留，全部删掉
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))
        conn.commit()
        print("✅ Database cleaned, all old data removed.")

    print("Creating extensions...")
    with engine.connect() as conn:
        # 1. 启用 pgvector 扩展（必须最先执行）
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
        print("✅ pgvector extension enabled.")

        # 2. 创建中文全文检索配置
        try:
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'simple_chinese') THEN
                        CREATE TEXT SEARCH CONFIGURATION simple_chinese (PARSER = default);
                        ALTER TEXT SEARCH CONFIGURATION simple_chinese
                            ADD MAPPING FOR asciiword, word, numword, asciihword, hword
                            WITH simple;
                    END IF;
                END
                $$;
            """))
            conn.commit()
            print("✅ Full-text config 'simple_chinese' created.")
        except Exception as e:
            print(f"⚠️  Could not create text search config (non-fatal): {e}")

    # 3. 创建所有表
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully!")

    # 4. 手动创建向量索引，加IF NOT EXISTS，避免重复创建报错
    print("Creating vector index...")
    with engine.connect() as conn:
        conn.execute(text("""
               CREATE INDEX IF NOT EXISTS ix_chunks_embedding 
               ON chunks USING ivfflat (embedding vector_cosine_ops);
           """))
        conn.commit()
        print("✅ Vector index created successfully!")

if __name__ == "__main__":
    init_db()