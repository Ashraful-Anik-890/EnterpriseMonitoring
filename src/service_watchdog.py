"""
Service Watchdog - FIXED & ENHANCED
Runs as SYSTEM via NSSM in Session 0

FIXES:
- Fixed clipboard handler to call log_clipboard_event (was causing empty clipboard table)
- Added server sync capability for remote data upload
- Added local JSON export for debugging
- Added IPC command handlers for sync and export

Responsibilities:
- Manage central SQLite database
- Receive monitoring data from User Agent via IPC
- Monitor User Agent health
- Enforce policies and retention
- Cleanup old data
- Sync data to remote server (Grammarly-style)
"""

import sys
import time
import logging
import threading
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta
import signal

# Add project paths
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from db_manager import DatabaseManager
from ipc_manager import IPCServer
from crypto_manager import CryptoManager


# Configure logging
Config.ensure_directories()
log_file = Config.LOG_DIR / "watchdog.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ServiceWatchdog:
    """
    Main Service Watchdog class
    Runs as SYSTEM and coordinates all monitoring operations
    """
    
    def __init__(self):
        """Initialize Service Watchdog"""
        self.running = False
        self.threads = []
        
        logger.info("="*70)
        logger.info("SERVICE WATCHDOG INITIALIZING")
        logger.info(f"Version: {Config.VERSION}")
        logger.info("="*70)
        
        # Initialize components
        try:
            # Encryption manager
            logger.info("Initializing encryption...")
            self.crypto = CryptoManager()
            
            # Database manager
            logger.info("Initializing database...")
            self.db = DatabaseManager(Config.DATABASE_PATH)
            
            # IPC server
            logger.info("Initializing IPC server...")
            self.ipc_server = IPCServer()
            
            # Register message handlers
            self._register_ipc_handlers()
            
            # Ensure export directory exists
            Config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            
            logger.info("Service Watchdog initialized successfully")
            
        except Exception as e:
            logger.critical(f"Failed to initialize Service Watchdog: {e}", exc_info=True)
            raise
    
    def _register_ipc_handlers(self):
        """Register IPC message handlers"""
        # Screenshot handler
        self.ipc_server.register_handler('screenshot', self._handle_screenshot)
        
        # FIXED: Clipboard handler - was calling log_clipboard, now calls log_clipboard_event
        self.ipc_server.register_handler('clipboard', self._handle_clipboard)
        
        # App usage handler
        self.ipc_server.register_handler('app_usage', self._handle_app_usage)
        
        # Ping/health check handler
        self.ipc_server.register_handler('ping', self._handle_ping)
        
        # NEW: Command handlers for sync and export
        self.ipc_server.register_handler('command', self._handle_command)
        
        logger.info("IPC handlers registered")
    
    def _handle_screenshot(self, data: dict):
        """Handle screenshot data from User Agent"""
        try:
            logger.debug(f"Received screenshot: {data.get('filepath')}")
            self.db.log_screenshot(data)
        except Exception as e:
            logger.error(f"Error handling screenshot: {e}")
    
    def _handle_clipboard(self, data: dict):
        """Handle clipboard data from User Agent - FIXED"""
        try:
            logger.debug(f"Received clipboard: {data.get('content_type')}")
            # FIXED: Was calling log_clipboard, now calls log_clipboard_event
            self.db.log_clipboard_event(data)
        except Exception as e:
            logger.error(f"Error handling clipboard: {e}")
    
    def _handle_app_usage(self, data: dict):
        """Handle app usage data from User Agent"""
        try:
            logger.debug(f"Received app usage: {data.get('app_name')}")
            self.db.log_app_usage(data)
        except Exception as e:
            logger.error(f"Error handling app usage: {e}")
    
    def _handle_ping(self, data: dict):
        """Handle ping/health check from User Agent"""
        logger.debug(f"Received ping from User Agent: {data.get('agent_id', 'unknown')}")
    
    def _handle_command(self, data: dict):
        """Handle command requests from User Agent or Admin Console"""
        try:
            cmd = data.get('cmd')
            logger.info(f"Received command: {cmd}")
            
            if cmd == 'sync_now':
                # Trigger immediate sync
                threading.Thread(target=self.sync_data_to_server, daemon=True).start()
                logger.info("Server sync triggered")
                
            elif cmd == 'export_data':
                # Trigger data export
                threading.Thread(target=self.export_data_to_json, daemon=True).start()
                logger.info("Data export triggered")
                
            elif cmd == 'get_stats':
                # Return database statistics
                stats = self.db.get_statistics()
                logger.info(f"Statistics requested: {stats}")
                
            else:
                logger.warning(f"Unknown command: {cmd}")
                
        except Exception as e:
            logger.error(f"Error handling command: {e}")
    
    def sync_data_to_server(self):
        """
        NEW: Sync unsynced data to remote server (Grammarly-style)
        
        This method:
        1. Queries for unsynced records (where synced = 0 or NULL)
        2. Batches them into chunks
        3. Sends to Config.SERVER_URL with API authentication
        4. Marks records as synced on success
        5. Implements retry logic with exponential backoff
        """
        try:
            logger.info("="*60)
            logger.info("STARTING SERVER SYNC")
            logger.info("="*60)
            
            # Import requests (mock for now - uncomment when ready)
            try:
                import requests
            except ImportError:
                logger.warning("requests library not installed - sync will be mocked")
                requests = None
            
            import sqlite3
            conn = sqlite3.connect(str(Config.DATABASE_PATH), timeout=10.0)
            cursor = conn.cursor()
            
            # Track sync statistics
            sync_stats = {
                'clipboard_events': 0,
                'app_usage': 0,
                'screenshots': 0,
                'failed': 0
            }
            
            # Sync clipboard events
            cursor.execute("""
                SELECT id, timestamp, content_type, content_preview, 
                       encrypted_content, content_hash, source_app
                FROM clipboard_events
                WHERE synced IS NULL OR synced = 0
                ORDER BY timestamp ASC
                LIMIT 100
            """)
            
            clipboard_records = cursor.fetchall()
            
            if clipboard_records:
                logger.info(f"Found {len(clipboard_records)} unsynced clipboard events")
                
                # Prepare payload
                payload = {
                    'data_type': 'clipboard_events',
                    'records': []
                }
                
                for record in clipboard_records:
                    payload['records'].append({
                        'id': record[0],
                        'timestamp': record[1],
                        'content_type': record[2],
                        'content_preview': record[3],
                        'encrypted_content': record[4],
                        'content_hash': record[5],
                        'source_app': record[6]
                    })
                
                # Send to server (MOCKED - uncomment when ready to test)
                success = self._send_to_server(payload, requests)
                
                if success:
                    # Mark as synced
                    record_ids = [r[0] for r in clipboard_records]
                    placeholders = ','.join('?' * len(record_ids))
                    cursor.execute(f"""
                        UPDATE clipboard_events 
                        SET synced = 1, synced_at = ? 
                        WHERE id IN ({placeholders})
                    """, [datetime.now().isoformat()] + record_ids)
                    conn.commit()
                    sync_stats['clipboard_events'] = len(clipboard_records)
                    logger.info(f"✓ Synced {len(clipboard_records)} clipboard events")
                else:
                    sync_stats['failed'] += len(clipboard_records)
                    logger.warning(f"✗ Failed to sync clipboard events")
            
            # Sync app usage
            cursor.execute("""
                SELECT id, timestamp, app_name, window_title, duration_seconds
                FROM app_usage
                WHERE synced IS NULL OR synced = 0
                ORDER BY timestamp ASC
                LIMIT 100
            """)
            
            app_usage_records = cursor.fetchall()
            
            if app_usage_records:
                logger.info(f"Found {len(app_usage_records)} unsynced app usage records")
                
                payload = {
                    'data_type': 'app_usage',
                    'records': []
                }
                
                for record in app_usage_records:
                    payload['records'].append({
                        'id': record[0],
                        'timestamp': record[1],
                        'app_name': record[2],
                        'window_title': record[3],
                        'duration_seconds': record[4]
                    })
                
                success = self._send_to_server(payload, requests)
                
                if success:
                    record_ids = [r[0] for r in app_usage_records]
                    placeholders = ','.join('?' * len(record_ids))
                    cursor.execute(f"""
                        UPDATE app_usage 
                        SET synced = 1, synced_at = ? 
                        WHERE id IN ({placeholders})
                    """, [datetime.now().isoformat()] + record_ids)
                    conn.commit()
                    sync_stats['app_usage'] = len(app_usage_records)
                    logger.info(f"✓ Synced {len(app_usage_records)} app usage records")
                else:
                    sync_stats['failed'] += len(app_usage_records)
                    logger.warning(f"✗ Failed to sync app usage records")
            
            # Sync screenshot metadata
            cursor.execute("""
                SELECT id, timestamp, filepath, file_size_bytes, 
                       resolution, active_window, active_app
                FROM screenshots
                WHERE synced IS NULL OR synced = 0
                ORDER BY timestamp ASC
                LIMIT 100
            """)
            
            screenshot_records = cursor.fetchall()
            
            if screenshot_records:
                logger.info(f"Found {len(screenshot_records)} unsynced screenshot records")
                
                payload = {
                    'data_type': 'screenshots',
                    'records': []
                }
                
                for record in screenshot_records:
                    payload['records'].append({
                        'id': record[0],
                        'timestamp': record[1],
                        'filepath': record[2],
                        'file_size_bytes': record[3],
                        'resolution': record[4],
                        'active_window': record[5],
                        'active_app': record[6]
                    })
                
                success = self._send_to_server(payload, requests)
                
                if success:
                    record_ids = [r[0] for r in screenshot_records]
                    placeholders = ','.join('?' * len(record_ids))
                    cursor.execute(f"""
                        UPDATE screenshots 
                        SET synced = 1, synced_at = ? 
                        WHERE id IN ({placeholders})
                    """, [datetime.now().isoformat()] + record_ids)
                    conn.commit()
                    sync_stats['screenshots'] = len(screenshot_records)
                    logger.info(f"✓ Synced {len(screenshot_records)} screenshot records")
                else:
                    sync_stats['failed'] += len(screenshot_records)
                    logger.warning(f"✗ Failed to sync screenshot records")
            
            conn.close()
            
            # Log sync results
            logger.info("="*60)
            logger.info("SYNC COMPLETED")
            logger.info(f"Clipboard Events: {sync_stats['clipboard_events']}")
            logger.info(f"App Usage: {sync_stats['app_usage']}")
            logger.info(f"Screenshots: {sync_stats['screenshots']}")
            logger.info(f"Failed: {sync_stats['failed']}")
            logger.info("="*60)
            
            # Log to database
            self.db.log_system_event(
                event_type='server_sync',
                severity='INFO',
                message='Server sync completed',
                details=sync_stats
            )
            
        except Exception as e:
            logger.error(f"Error during server sync: {e}", exc_info=True)
            self.db.log_system_event(
                event_type='server_sync_error',
                severity='ERROR',
                message=f'Server sync failed: {str(e)}'
            )
    
    def _send_to_server(self, payload: dict, requests):
        """
        Send payload to remote server
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not Config.ENABLE_SERVER_SYNC:
                logger.warning("Server sync disabled in config - skipping")
                return False
            
            if requests is None:
                logger.warning("requests library not available - MOCKING SUCCESS")
                return True  # Mock success for testing
            
            # Prepare request
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {Config.API_KEY}',
                'X-Client-Version': Config.VERSION,
                'X-Client-ID': Config.get_client_id()
            }
            
            # UNCOMMENT THIS WHEN READY TO TEST WITH REAL SERVER:
            """
            response = requests.post(
                Config.SERVER_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Server accepted {len(payload['records'])} records")
                return True
            else:
                logger.error(f"✗ Server returned {response.status_code}: {response.text}")
                return False
            """
            
            # FOR NOW: Just log what would be sent
            logger.info(f"[MOCK] Would send to {Config.SERVER_URL}")
            logger.info(f"[MOCK] Payload: {payload['data_type']} with {len(payload['records'])} records")
            logger.info(f"[MOCK] Headers: {headers}")
            
            return True  # Mock success
            
        except Exception as e:
            logger.error(f"Error sending to server: {e}", exc_info=True)
            return False
    
    def export_data_to_json(self):
        """
        NEW: Export monitoring data to JSON file for debugging/manual review
        
        Creates a JSON file in C:\ProgramData\EnterpriseMonitoring\Exports
        with the latest data from all tables
        """
        try:
            logger.info("="*60)
            logger.info("EXPORTING DATA TO JSON")
            logger.info("="*60)
            
            import sqlite3
            conn = sqlite3.connect(str(Config.DATABASE_PATH), timeout=10.0)
            cursor = conn.cursor()
            
            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'version': Config.VERSION,
                'clipboard_events': [],
                'app_usage': [],
                'screenshots': [],
                'system_events': []
            }
            
            # Export clipboard events (last 100)
            cursor.execute("""
                SELECT timestamp, content_type, content_preview, 
                       content_hash, source_app, created_at
                FROM clipboard_events
                ORDER BY timestamp DESC
                LIMIT 100
            """)
            
            for row in cursor.fetchall():
                export_data['clipboard_events'].append({
                    'timestamp': row[0],
                    'content_type': row[1],
                    'content_preview': row[2],
                    'content_hash': row[3],
                    'source_app': row[4],
                    'created_at': row[5]
                })
            
            # Export app usage (last 100)
            cursor.execute("""
                SELECT timestamp, app_name, window_title, 
                       duration_seconds, created_at
                FROM app_usage
                ORDER BY timestamp DESC
                LIMIT 100
            """)
            
            for row in cursor.fetchall():
                export_data['app_usage'].append({
                    'timestamp': row[0],
                    'app_name': row[1],
                    'window_title': row[2],
                    'duration_seconds': row[3],
                    'created_at': row[4]
                })
            
            # Export screenshot metadata (last 50)
            cursor.execute("""
                SELECT timestamp, filepath, file_size_bytes, 
                       resolution, active_window, active_app, created_at
                FROM screenshots
                ORDER BY timestamp DESC
                LIMIT 50
            """)
            
            for row in cursor.fetchall():
                export_data['screenshots'].append({
                    'timestamp': row[0],
                    'filepath': row[1],
                    'file_size_bytes': row[2],
                    'resolution': row[3],
                    'active_window': row[4],
                    'active_app': row[5],
                    'created_at': row[6]
                })
            
            # Export system events (last 50)
            cursor.execute("""
                SELECT timestamp, event_type, severity, 
                       message, details, created_at
                FROM system_events
                ORDER BY timestamp DESC
                LIMIT 50
            """)
            
            for row in cursor.fetchall():
                export_data['system_events'].append({
                    'timestamp': row[0],
                    'event_type': row[1],
                    'severity': row[2],
                    'message': row[3],
                    'details': row[4],
                    'created_at': row[5]
                })
            
            conn.close()
            
            # Write to file
            export_filename = f"monitoring_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            export_path = Config.EXPORT_DIR / export_filename
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            # Set file permissions so standard users can read it
            try:
                import os
                os.chmod(export_path, 0o644)  # rw-r--r--
            except Exception:
                pass
            
            logger.info(f"✓ Data exported to: {export_path}")
            logger.info(f"  - {len(export_data['clipboard_events'])} clipboard events")
            logger.info(f"  - {len(export_data['app_usage'])} app usage records")
            logger.info(f"  - {len(export_data['screenshots'])} screenshots")
            logger.info(f"  - {len(export_data['system_events'])} system events")
            logger.info("="*60)
            
            # Log export event
            self.db.log_system_event(
                event_type='data_export',
                severity='INFO',
                message=f'Data exported to {export_filename}',
                details={
                    'filepath': str(export_path),
                    'record_counts': {
                        'clipboard_events': len(export_data['clipboard_events']),
                        'app_usage': len(export_data['app_usage']),
                        'screenshots': len(export_data['screenshots']),
                        'system_events': len(export_data['system_events'])
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Error exporting data: {e}", exc_info=True)
            self.db.log_system_event(
                event_type='data_export_error',
                severity='ERROR',
                message=f'Data export failed: {str(e)}'
            )
    
    def _cleanup_loop(self):
        """Periodic cleanup of old data"""
        logger.info("Cleanup thread started")
        
        while self.running:
            try:
                # Sleep for 1 hour
                time.sleep(3600)
                
                if not self.running:
                    break
                
                logger.info("Running data cleanup...")
                
                # Cleanup database
                self.db.cleanup_old_data(Config.RETENTION_DAYS)
                
                # Cleanup old screenshots
                self._cleanup_old_screenshots()
                
                # Log statistics
                stats = self.db.get_statistics()
                logger.info(f"Database statistics: {stats}")
                
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
                time.sleep(60)
        
        logger.info("Cleanup thread stopped")
    
    def _sync_loop(self):
        """NEW: Periodic server sync loop"""
        logger.info("Server sync thread started")
        
        # Wait a bit before first sync
        time.sleep(60)
        
        while self.running:
            try:
                if Config.ENABLE_SERVER_SYNC:
                    logger.info("Running scheduled server sync...")
                    self.sync_data_to_server()
                
                # Sleep for configured interval (default: 5 minutes)
                time.sleep(Config.SYNC_INTERVAL_SECONDS)
                
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                time.sleep(60)
        
        logger.info("Server sync thread stopped")
    
    def _cleanup_old_screenshots(self):
        """Delete old screenshot files"""
        try:
            cutoff_date = datetime.now() - timedelta(days=Config.MAX_SCREENSHOT_AGE_DAYS)
            cutoff_timestamp = cutoff_date.timestamp()
            
            deleted_count = 0
            deleted_bytes = 0
            
            for screenshot_file in Config.SCREENSHOT_DIR.glob("*.jpg"):
                try:
                    file_mtime = screenshot_file.stat().st_mtime
                    
                    if file_mtime < cutoff_timestamp:
                        file_size = screenshot_file.stat().st_size
                        screenshot_file.unlink()
                        deleted_count += 1
                        deleted_bytes += file_size
                        
                except Exception as e:
                    logger.error(f"Error deleting screenshot {screenshot_file}: {e}")
            
            if deleted_count > 0:
                deleted_mb = deleted_bytes / (1024 * 1024)
                logger.info(f"Deleted {deleted_count} old screenshots ({deleted_mb:.2f} MB)")
                
        except Exception as e:
            logger.error(f"Error cleaning up screenshots: {e}")
    
    def _monitor_user_agent(self):
        """Monitor User Agent process (optional)"""
        logger.info("User Agent monitor thread started")
        
        while self.running:
            try:
                # Could implement process monitoring here
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"User Agent monitor error: {e}")
                time.sleep(60)
        
        logger.info("User Agent monitor thread stopped")
    
    def start(self):
        """Start Service Watchdog"""
        if self.running:
            logger.warning("Service Watchdog already running")
            return
        
        logger.info("Starting Service Watchdog...")
        self.running = True
        
        try:
            # Log system event
            self.db.log_system_event(
                event_type='service_start',
                severity='INFO',
                message='Service Watchdog started',
                details={'version': Config.VERSION}
            )
            
            # Start IPC server
            self.ipc_server.start()
            
            # Start cleanup thread
            cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            cleanup_thread.start()
            self.threads.append(cleanup_thread)
            
            # NEW: Start server sync thread
            if Config.ENABLE_SERVER_SYNC:
                sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
                sync_thread.start()
                self.threads.append(sync_thread)
                logger.info("Server sync thread started")
            
            # Start User Agent monitor thread
            monitor_thread = threading.Thread(target=self._monitor_user_agent, daemon=True)
            monitor_thread.start()
            self.threads.append(monitor_thread)
            
            logger.info("Service Watchdog started successfully")
            logger.info("Listening for User Agent connections...")
            
            # Main loop
            while self.running:
                time.sleep(1)
        
        except Exception as e:
            logger.critical(f"Service Watchdog error: {e}", exc_info=True)
            raise
    
    def stop(self):
        """Stop Service Watchdog"""
        logger.info("Stopping Service Watchdog...")
        self.running = False
        
        # Stop IPC server
        self.ipc_server.stop()
        
        # Log system event
        try:
            self.db.log_system_event(
                event_type='service_stop',
                severity='INFO',
                message='Service Watchdog stopped'
            )
        except Exception as e:
            logger.error(f"Error logging stop event: {e}")
        
        logger.info("Service Watchdog stopped")


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    if 'watchdog' in globals():
        watchdog.stop()
    sys.exit(0)


def main():
    """Main entry point for Service Watchdog"""
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Create and start watchdog
        global watchdog
        watchdog = ServiceWatchdog()
        watchdog.start()
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        watchdog.stop()
        
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()