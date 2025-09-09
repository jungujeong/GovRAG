"""
Index integrity checker and auto-repair utilities
"""
import os
import shutil
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from whoosh import index
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class IndexIntegrityChecker:
    """Check and maintain index integrity"""
    
    def __init__(self, index_dir: Path, backup_dir: Optional[Path] = None):
        self.index_dir = Path(index_dir)
        self.backup_dir = backup_dir or (self.index_dir.parent / "index_backup")
        self.integrity_file = self.index_dir / ".integrity.json"
        
    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of a file"""
        if not file_path.exists():
            return ""
        
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to calculate checksum for {file_path}: {e}")
            return ""
    
    def get_index_files(self) -> List[Path]:
        """Get all index-related files"""
        if not self.index_dir.exists():
            return []
        
        index_files = []
        for pattern in ["*.toc", "*.seg", "*.w", "*.pkl", "*.fdt", "*.fdx", 
                       "*.fnm", "*.frq", "*.nrm", "*.prx", "*.tii", "*.tis"]:
            index_files.extend(self.index_dir.rglob(pattern))
        
        return sorted(index_files)
    
    def create_integrity_snapshot(self) -> Dict:
        """Create integrity snapshot of current index"""
        snapshot = {
            "timestamp": str(Path().cwd().stat().st_mtime),
            "files": {}
        }
        
        for file_path in self.get_index_files():
            rel_path = str(file_path.relative_to(self.index_dir))
            snapshot["files"][rel_path] = {
                "checksum": self.calculate_checksum(file_path),
                "size": file_path.stat().st_size if file_path.exists() else 0,
                "mtime": file_path.stat().st_mtime if file_path.exists() else 0
            }
        
        return snapshot
    
    def save_integrity_snapshot(self) -> bool:
        """Save current integrity snapshot"""
        try:
            snapshot = self.create_integrity_snapshot()
            self.index_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.integrity_file, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
            
            logger.info(f"Saved integrity snapshot with {len(snapshot['files'])} files")
            return True
        except Exception as e:
            logger.error(f"Failed to save integrity snapshot: {e}")
            return False
    
    def load_integrity_snapshot(self) -> Optional[Dict]:
        """Load saved integrity snapshot"""
        try:
            if not self.integrity_file.exists():
                return None
            
            with open(self.integrity_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load integrity snapshot: {e}")
            return None
    
    def verify_integrity(self) -> Tuple[bool, List[str]]:
        """Verify index integrity against saved snapshot"""
        issues = []
        
        # Load saved snapshot
        saved_snapshot = self.load_integrity_snapshot()
        if not saved_snapshot:
            issues.append("No integrity snapshot found")
            return False, issues
        
        # Get current state
        current_files = {str(f.relative_to(self.index_dir)): f 
                        for f in self.get_index_files()}
        saved_files = saved_snapshot.get("files", {})
        
        # Check for missing files
        for rel_path in saved_files:
            if rel_path not in current_files:
                issues.append(f"Missing file: {rel_path}")
                continue
            
            file_path = current_files[rel_path]
            saved_info = saved_files[rel_path]
            
            # Check checksum
            current_checksum = self.calculate_checksum(file_path)
            if current_checksum != saved_info.get("checksum", ""):
                issues.append(f"Checksum mismatch: {rel_path}")
            
            # Check size
            current_size = file_path.stat().st_size if file_path.exists() else 0
            if current_size != saved_info.get("size", 0):
                issues.append(f"Size mismatch: {rel_path}")
        
        # Check for unexpected files
        for rel_path in current_files:
            if rel_path not in saved_files:
                issues.append(f"Unexpected file: {rel_path}")
        
        is_valid = len(issues) == 0
        if is_valid:
            logger.info("Index integrity verification passed")
        else:
            logger.warning(f"Index integrity verification failed: {len(issues)} issues")
        
        return is_valid, issues
    
    def is_whoosh_index_valid(self, index_path: Path) -> bool:
        """Check if Whoosh index is valid and readable"""
        try:
            if not index_path.exists():
                return False
            
            # Try to open the index
            if index.exists_in(str(index_path)):
                ix = index.open_dir(str(index_path))
                # Try to get basic info
                with ix.searcher() as searcher:
                    doc_count = searcher.doc_count()
                logger.debug(f"Index valid with {doc_count} documents")
                return True
            else:
                return False
        except Exception as e:
            logger.warning(f"Index validation failed: {e}")
            return False
    
    def create_backup(self) -> bool:
        """Create backup of current index"""
        try:
            if not self.index_dir.exists():
                logger.warning("No index to backup")
                return False
            
            # Create backup directory
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy index files
            backup_path = self.backup_dir / f"backup_{int(Path().cwd().stat().st_mtime)}"
            shutil.copytree(self.index_dir, backup_path, ignore_dangling_symlinks=True)
            
            # Save integrity snapshot
            integrity_checker = IndexIntegrityChecker(backup_path)
            integrity_checker.save_integrity_snapshot()
            
            logger.info(f"Created index backup at {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False
    
    def restore_from_backup(self, backup_name: Optional[str] = None) -> bool:
        """Restore index from backup"""
        try:
            if not self.backup_dir.exists():
                logger.error("No backup directory found")
                return False
            
            # Find backup to restore
            if backup_name:
                backup_path = self.backup_dir / backup_name
            else:
                # Get latest backup
                backups = [d for d in self.backup_dir.iterdir() 
                          if d.is_dir() and d.name.startswith("backup_")]
                if not backups:
                    logger.error("No backups found")
                    return False
                backup_path = max(backups, key=lambda x: x.stat().st_mtime)
            
            if not backup_path.exists():
                logger.error(f"Backup not found: {backup_path}")
                return False
            
            # Verify backup integrity
            backup_checker = IndexIntegrityChecker(backup_path)
            is_valid, issues = backup_checker.verify_integrity()
            if not is_valid:
                logger.warning(f"Backup integrity issues: {issues}")
            
            # Remove current index
            if self.index_dir.exists():
                shutil.rmtree(self.index_dir)
            
            # Restore from backup
            shutil.copytree(backup_path, self.index_dir)
            
            logger.info(f"Restored index from backup: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return False
    
    def auto_repair(self) -> bool:
        """Attempt to automatically repair corrupted index"""
        logger.info("Attempting auto-repair of index...")
        
        # First, try to restore from backup
        if self.restore_from_backup():
            logger.info("Auto-repair successful: restored from backup")
            return True
        
        # If no backup, remove corrupted index (will be recreated)
        try:
            if self.index_dir.exists():
                shutil.rmtree(self.index_dir)
                logger.info("Removed corrupted index for recreation")
            return True
        except Exception as e:
            logger.error(f"Auto-repair failed: {e}")
            return False

@contextmanager
def safe_index_operation(index_checker: IndexIntegrityChecker):
    """Context manager for safe index operations"""
    # Create backup before operation
    backup_created = index_checker.create_backup()
    
    try:
        yield
        # Save new integrity snapshot after successful operation
        index_checker.save_integrity_snapshot()
    except Exception as e:
        logger.error(f"Index operation failed: {e}")
        if backup_created:
            logger.info("Attempting to restore from backup...")
            index_checker.restore_from_backup()
        raise