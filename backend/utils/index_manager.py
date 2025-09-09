#!/usr/bin/env python3
"""
Index management CLI tool for backup, restore, and maintenance
"""
import argparse
import sys
from pathlib import Path
import logging

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config
from utils.index_integrity import IndexIntegrityChecker
from rag.whoosh_bm25 import WhooshBM25
from rag.chroma_store import ChromaStore

logger = logging.getLogger(__name__)

def setup_logging():
    """Setup logging for CLI"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def backup_indexes(args):
    """Create backup of all indexes"""
    print("🔄 Creating index backups...")
    
    # Backup Whoosh index
    whoosh_checker = IndexIntegrityChecker(Path(config.WHOOSH_DIR) / "main")
    if whoosh_checker.create_backup():
        print("✅ Whoosh index backup created")
    else:
        print("❌ Failed to backup Whoosh index")
    
    # TODO: Add ChromaDB backup when needed
    print("✅ Index backup complete!")

def restore_indexes(args):
    """Restore indexes from backup"""
    print("🔄 Restoring indexes from backup...")
    
    whoosh_checker = IndexIntegrityChecker(Path(config.WHOOSH_DIR) / "main")
    if whoosh_checker.restore_from_backup(args.backup_name):
        print("✅ Whoosh index restored")
    else:
        print("❌ Failed to restore Whoosh index")
    
    print("✅ Index restore complete!")

def verify_indexes(args):
    """Verify index integrity"""
    print("🔍 Verifying index integrity...")
    
    # Verify Whoosh
    whoosh_checker = IndexIntegrityChecker(Path(config.WHOOSH_DIR) / "main")
    is_valid, issues = whoosh_checker.verify_integrity()
    
    if is_valid:
        print("✅ Whoosh index integrity: PASS")
    else:
        print("❌ Whoosh index integrity: FAIL")
        for issue in issues:
            print(f"  - {issue}")
    
    # Test Whoosh functionality
    try:
        whoosh_instance = WhooshBM25()
        stats = whoosh_instance.get_stats()
        print(f"✅ Whoosh functional test: PASS ({stats.get('doc_count', 0)} docs)")
    except Exception as e:
        print(f"❌ Whoosh functional test: FAIL ({e})")
    
    print("✅ Index verification complete!")

def repair_indexes(args):
    """Attempt to repair corrupted indexes"""
    print("🔧 Attempting index repair...")
    
    whoosh_checker = IndexIntegrityChecker(Path(config.WHOOSH_DIR) / "main")
    if whoosh_checker.auto_repair():
        print("✅ Whoosh index repair successful")
    else:
        print("❌ Whoosh index repair failed")
    
    print("✅ Index repair complete!")

def list_backups(args):
    """List available backups"""
    print("📋 Available backups:")
    
    whoosh_checker = IndexIntegrityChecker(Path(config.WHOOSH_DIR) / "main")
    backup_dir = whoosh_checker.backup_dir
    
    if not backup_dir.exists():
        print("  No backups found")
        return
    
    backups = [d for d in backup_dir.iterdir() if d.is_dir() and d.name.startswith("backup_")]
    
    if not backups:
        print("  No backups found")
        return
    
    # Sort by modification time (newest first)
    backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    for i, backup in enumerate(backups):
        timestamp = backup.stat().st_mtime
        import datetime
        date_str = datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        size = sum(f.stat().st_size for f in backup.rglob('*') if f.is_file())
        size_mb = size / (1024 * 1024)
        
        status = "  🟢 Latest" if i == 0 else "  🔵 Available"
        print(f"{status} {backup.name} - {date_str} ({size_mb:.1f}MB)")

def clean_old_backups(args):
    """Clean old backups (keep last N)"""
    keep_count = args.keep or 5
    print(f"🧹 Cleaning old backups (keeping last {keep_count})...")
    
    whoosh_checker = IndexIntegrityChecker(Path(config.WHOOSH_DIR) / "main")
    backup_dir = whoosh_checker.backup_dir
    
    if not backup_dir.exists():
        print("  No backup directory found")
        return
    
    backups = [d for d in backup_dir.iterdir() if d.is_dir() and d.name.startswith("backup_")]
    
    if len(backups) <= keep_count:
        print(f"  Only {len(backups)} backups found, nothing to clean")
        return
    
    # Sort by modification time (newest first)
    backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    # Remove old backups
    removed_count = 0
    for backup in backups[keep_count:]:
        try:
            import shutil
            shutil.rmtree(backup)
            print(f"  🗑️  Removed {backup.name}")
            removed_count += 1
        except Exception as e:
            print(f"  ❌ Failed to remove {backup.name}: {e}")
    
    print(f"✅ Cleaned {removed_count} old backups")

def main():
    """Main CLI entry point"""
    setup_logging()
    
    parser = argparse.ArgumentParser(description="RAG Index Management Tool")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create index backups')
    backup_parser.set_defaults(func=backup_indexes)
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore indexes from backup')
    restore_parser.add_argument('--backup-name', help='Specific backup to restore (latest if not specified)')
    restore_parser.set_defaults(func=restore_indexes)
    
    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify index integrity')
    verify_parser.set_defaults(func=verify_indexes)
    
    # Repair command
    repair_parser = subparsers.add_parser('repair', help='Attempt to repair corrupted indexes')
    repair_parser.set_defaults(func=repair_indexes)
    
    # List backups command
    list_parser = subparsers.add_parser('list', help='List available backups')
    list_parser.set_defaults(func=list_backups)
    
    # Clean command
    clean_parser = subparsers.add_parser('clean', help='Clean old backups')
    clean_parser.add_argument('--keep', type=int, default=5, help='Number of backups to keep (default: 5)')
    clean_parser.set_defaults(func=clean_old_backups)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        args.func(args)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()