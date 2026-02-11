"""
Database Manager for Enterprise Monitoring Agent - ENHANCED
Handles all SQLite database operations with encryption support

ENHANCEMENTS:
- Added 'synced' and 'synced_at' columns to track server sync status
- Added migration logic to add columns to existing databases
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Centralized database manager for monitoring data"""
    
    def __init__(self, db_path: Path, enable_encryption: bool = True):
        self.db_path = Path(db_path)
        self.enable_encryption = enable_encryption
        self.lock = Lock()
        
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database schema
        self._init_database()
        
        # Run migrations
        self._run_migrations()
        
        logger.info(f"Database initialized at {self.db_path}")
    
    def _init_database(self):
        """Initialize database schema"""
        with self.lock:
            try:
                conn = sqlite3.connect(str(self.db_path), timeout=10.0)
                cursor = conn.cursor()
                
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
                
                # Create tables
                self._create_tables(cursor)
                
                # Create indexes
                self._create_indexes(cursor)
                
                conn.commit()
                conn.close()
                
                logger.info("Database schema initialized successfully")
                
            except sqlite3.Error as e:
                logger.error(f"Database initialization failed: {e}", exc_info=True)
                raise
    
    def _create_tables(self, cursor):
        """Create all required tables"""
        
        # Screenshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                filepath TEXT NOT NULL,
                file_size_bytes INTEGER,
                resolution TEXT,
                active_window TEXT,
                active_app TEXT,
                synced INTEGER DEFAULT 0,
                synced_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Clipboard events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clipboard_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                content_type TEXT,
                content_preview TEXT,
                encrypted_content BLOB,
                content_hash TEXT,
                source_app TEXT,
                synced INTEGER DEFAULT 0,
                synced_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # App usage table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                app_name TEXT NOT NULL,
                window_title TEXT,
                duration_seconds REAL,
                synced INTEGER DEFAULT 0,
                synced_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # System events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT,
                message TEXT,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def _create_indexes(self, cursor):
        """Create indexes for better query performance"""
        
        # Screenshots indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_screenshots_timestamp 
            ON screenshots(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_screenshots_app 
            ON screenshots(active_app)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_screenshots_synced 
            ON screenshots(synced)
        """)
        
        # Clipboard events indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_clipboard_timestamp 
            ON clipboard_events(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_clipboard_type 
            ON clipboard_events(content_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_clipboard_synced 
            ON clipboard_events(synced)
        """)
        
        # App usage indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_app_usage_timestamp 
            ON app_usage(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_app_usage_name 
            ON app_usage(app_name)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_app_usage_synced 
            ON app_usage(synced)
        """)
        
        # System events indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_system_events_timestamp 
            ON system_events(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_system_events_type 
            ON system_events(event_type)
        """)
    
    def _run_migrations(self):
        """
        NEW: Run database migrations
        
        This adds the 'synced' and 'synced_at' columns to existing databases
        that were created with the old schema
        """
        with self.lock:
            try:
                conn = sqlite3.connect(str(self.db_path), timeout=10.0)
                cursor = conn.cursor()
                
                # Check if migrations are needed
                tables_to_migrate = ['screenshots', 'clipboard_events', 'app_usage']
                
                for table in tables_to_migrate:
                    # Check if synced column exists
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = [col[1] for col in cursor.fetchall()]
                    
                    if 'synced' not in columns:
                        logger.info(f"Adding synced columns to {table}")
                        cursor.execute(f"""
                            ALTER TABLE {table} 
                            ADD COLUMN synced INTEGER DEFAULT 0
                        """)
                        cursor.execute(f"""
                            ALTER TABLE {table} 
                            ADD COLUMN synced_at TEXT
                        """)
                        
                        # Create index
                        cursor.execute(f"""
                            CREATE INDEX IF NOT EXISTS idx_{table}_synced 
                            ON {table}(synced)
                        """)
                
                conn.commit()
                conn.close()
                
            except sqlite3.Error as e:
                logger.error(f"Migration error: {e}", exc_info=True)
    
    def log_screenshot(self, data: Dict[str, Any]):
        """Log screenshot metadata"""
        with self.lock:
            try:
                conn = sqlite3.connect(str(self.db_path), timeout=10.0)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO screenshots (
                        timestamp, filepath, file_size_bytes, resolution,
                        active_window, active_app
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    data.get('timestamp'),
                    data.get('filepath'),
                    data.get('file_size_bytes'),
                    data.get('resolution'),
                    data.get('active_window'),
                    data.get('active_app')
                ))
                
                conn.commit()
                conn.close()
                
                logger.debug(f"Logged screenshot: {data.get('filepath')}")
                
            except sqlite3.Error as e:
                logger.error(f"Error logging screenshot: {e}")
    
    def log_clipboard_event(self, data: Dict[str, Any]):
        """Log clipboard event"""
        with self.lock:
            try:
                conn = sqlite3.connect(str(self.db_path), timeout=10.0)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO clipboard_events (
                        timestamp, content_type, content_preview,
                        encrypted_content, content_hash, source_app
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    data.get('timestamp'),
                    data.get('content_type'),
                    data.get('content_preview'),
                    data.get('encrypted_content'),
                    data.get('content_hash'),
                    data.get('source_app')
                ))
                
                conn.commit()
                conn.close()
                
                logger.debug(f"Logged clipboard event: {data.get('content_type')}")
                
            except sqlite3.Error as e:
                logger.error(f"Error logging clipboard event: {e}")
    
    def log_app_usage(self, data: Dict[str, Any]):
        """Log application usage"""
        with self.lock:
            try:
                conn = sqlite3.connect(str(self.db_path), timeout=10.0)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO app_usage (
                        timestamp, app_name, window_title, duration_seconds
                    ) VALUES (?, ?, ?, ?)
                """, (
                    data.get('timestamp'),
                    data.get('app_name'),
                    data.get('window_title'),
                    data.get('duration_seconds')
                ))
                
                conn.commit()
                conn.close()
                
                logger.debug(f"Logged app usage: {data.get('app_name')}")
                
            except sqlite3.Error as e:
                logger.error(f"Error logging app usage: {e}")
    
    def log_system_event(self, event_type: str, severity: str, message: str, details: Dict = None):
        """Log system event"""
        with self.lock:
            try:
                conn = sqlite3.connect(str(self.db_path), timeout=10.0)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO system_events (
                        timestamp, event_type, severity, message, details
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    event_type,
                    severity,
                    message,
                    json.dumps(details) if details else None
                ))
                
                conn.commit()
                conn.close()
                
                logger.debug(f"Logged system event: {event_type}")
                
            except sqlite3.Error as e:
                logger.error(f"Error logging system event: {e}")
    
    def cleanup_old_data(self, retention_days: int = 30, screenshot_days: int = 7):
        """Delete old data based on retention policy"""
        with self.lock:
            try:
                conn = sqlite3.connect(str(self.db_path), timeout=10.0)
                cursor = conn.cursor()
                
                # Calculate cutoff dates
                cutoff_date = (datetime.now() - timedelta(days=retention_days)).isoformat()
                screenshot_cutoff = (datetime.now() - timedelta(days=screenshot_days)).isoformat()
                
                # Delete old screenshots metadata (only if synced or older than threshold)
                cursor.execute("""
                    DELETE FROM screenshots 
                    WHERE timestamp < ? AND (synced = 1 OR timestamp < ?)
                """, (screenshot_cutoff, screenshot_cutoff))
                screenshots_deleted = cursor.rowcount
                
                # Delete old clipboard events (only if synced)
                cursor.execute("""
                    DELETE FROM clipboard_events 
                    WHERE timestamp < ? AND synced = 1
                """, (cutoff_date,))
                clipboard_deleted = cursor.rowcount
                
                # Delete old app usage (only if synced)
                cursor.execute("""
                    DELETE FROM app_usage 
                    WHERE timestamp < ? AND synced = 1
                """, (cutoff_date,))
                app_usage_deleted = cursor.rowcount
                
                # Delete old system events
                cursor.execute("""
                    DELETE FROM system_events WHERE timestamp < ?
                """, (cutoff_date,))
                system_events_deleted = cursor.rowcount
                
                conn.commit()
                
                # Vacuum to reclaim space
                cursor.execute("VACUUM")
                
                conn.close()
                
                logger.info(
                    f"Cleanup complete - Deleted: {screenshots_deleted} screenshots, "
                    f"{clipboard_deleted} clipboard events, {app_usage_deleted} app usage records, "
                    f"{system_events_deleted} system events"
                )
                
            except sqlite3.Error as e:
                logger.error(f"Error during cleanup: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.lock:
            try:
                conn = sqlite3.connect(str(self.db_path), timeout=10.0)
                cursor = conn.cursor()
                
                stats = {}
                
                # Count records in each table
                for table in ['screenshots', 'clipboard_events', 'app_usage', 'system_events']:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[f'{table}_count'] = cursor.fetchone()[0]
                    
                    # Count unsynced records
                    if table != 'system_events':
                        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE synced = 0")
                        stats[f'{table}_unsynced'] = cursor.fetchone()[0]
                
                # Get database size
                cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                size_bytes = cursor.fetchone()[0]
                stats['database_size_mb'] = round(size_bytes / (1024 * 1024), 2)
                
                # Get date range
                cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM screenshots")
                result = cursor.fetchone()
                if result[0]:
                    stats['oldest_screenshot'] = result[0]
                    stats['newest_screenshot'] = result[1]
                
                conn.close()
                
                return stats
                
            except sqlite3.Error as e:
                logger.error(f"Error getting statistics: {e}")
                return {}
    
    def optimize_database(self):
        """Optimize database performance"""
        with self.lock:
            try:
                conn = sqlite3.connect(str(self.db_path), timeout=10.0)
                cursor = conn.cursor()
                
                # Analyze tables
                cursor.execute("ANALYZE")
                
                # Optimize
                cursor.execute("PRAGMA optimize")
                
                conn.close()
                
                logger.info("Database optimized")
                
            except sqlite3.Error as e:
                logger.error(f"Error optimizing database: {e}")
    
    def close(self):
        """Close database connections"""
        logger.info("Database manager closed")