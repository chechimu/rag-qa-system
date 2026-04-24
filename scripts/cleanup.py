"""
清理脚本：定期清理过期的对话历史

使用方式：
    python scripts/cleanup.py --days 30 --dry-run
"""

import sys
import argparse
from datetime import datetime, timedelta
from sqlalchemy import text

sys.path.append(".")
from app.db.session import engine
from app.models.conversation import Conversation
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(bind=engine)


def cleanup_conversations(days: int = 30, dry_run: bool = False):
    """清理指定天数前的对话历史"""
    cutoff_date = datetime.now() - timedelta(days=days)
    
    db = SessionLocal()
    try:
        # 查询要删除的记录数
        count = db.query(Conversation).filter(
            Conversation.created_at < cutoff_date
        ).count()
        
        if count == 0:
            print(f"✅ 没有超过 {days} 天的对话记录需要清理")
            return
        
        print(f"发现 {count} 条超过 {days} 天的对话记录")
        
        if dry_run:
            print(f"[试运行] 将删除 {count} 条记录（实际未删除）")
            return
        
        # 执行删除
        deleted = db.query(Conversation).filter(
            Conversation.created_at < cutoff_date
        ).delete(synchronize_session=False)
        
        db.commit()
        print(f"✅ 已删除 {deleted} 条过期对话记录")
        
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        db.rollback()
    finally:
        db.close()


def cleanup_orphaned_documents(dry_run: bool = False):
    """清理没有 chunks 的文档（可能处理失败的文档）"""
    db = SessionLocal()
    try:
        from app.models.document import Document
        from app.models.chunk import Chunk
        
        # 查找没有 chunks 且状态不是 completed 的文档
        subquery = db.query(Chunk.document_id).distinct().subquery()
        
        orphaned = db.query(Document).filter(
            ~Document.id.in_(subquery),
            Document.status != "completed"
        ).all()
        
        if not orphaned:
            print("✅ 没有孤立的文档需要清理")
            return
        
        print(f"发现 {len(orphaned)} 个孤立文档（无 chunks）")
        
        if dry_run:
            for doc in orphaned:
                print(f"  - {doc.filename} (status: {doc.status})")
            return
        
        for doc in orphaned:
            db.delete(doc)
        
        db.commit()
        print(f"✅ 已删除 {len(orphaned)} 个孤立文档")
        
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清理过期数据")
    parser.add_argument("--days", type=int, default=30, help="清理多少天前的数据")
    parser.add_argument("--dry-run", action="store_true", help="试运行，不实际删除")
    parser.add_argument("--orphans", action="store_true", help="清理孤立文档")
    
    args = parser.parse_args()
    
    print(f"🧹 开始清理（dry_run={args.dry_run}）...")
    cleanup_conversations(args.days, args.dry_run)
    
    if args.orphans:
        cleanup_orphaned_documents(args.dry_run)
    
    print("✨ 清理完成")
