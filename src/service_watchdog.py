"""
Service Watchdog
Runs as SYSTEM via NSSM in Session 0

Responsibilities:
- Manage central SQLite database
- Receive monitoring data from User Agent via IPC
- Monitor User Agent health
- Enforce policies and retention
- Cleanup old data
"""

import sys
import time
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime
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
            
            logger.info("Service Watchdog initialized successfully")
            
        except Exception as e:
            logger.critical(f"Failed to initialize Service Watchdog: {e}", exc_info=True)
            raise
    
    def _register_ipc_handlers(self):
        """Register IPC message handlers"""
        # Screenshot handler
        self.ipc_server.register_handler('screenshot', self._handle_screenshot)
        
        # Clipboard handler
        self.ipc_server.register_handler('clipboard', self._handle_clipboard)
        
        # App usage handler
        self.ipc_server.register_handler('app_usage', self._handle_app_usage)
        
        # Ping/health check handler
        self.ipc_server.register_handler('ping', self._handle_ping)
        
        logger.info("IPC handlers registered")
    
    def _handle_screenshot(self, data: dict):
        """Handle screenshot data from User Agent"""
        try:
            logger.debug(f"Received screenshot: {data.get('filepath')}")
            self.db.log_screenshot(data)
        except Exception as e:
            logger.error(f"Error handling screenshot: {e}")
    
    def _handle_clipboard(self, data: dict):
        """Handle clipboard data from User Agent"""
        try:
            logger.debug(f"Received clipboard: {data.get('content_type')}")
            self.db.log_clipboard(data)
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
    
    def _cleanup_old_screenshots(self):
        """Delete old screenshot files"""
        try:
            from datetime import timedelta
            
            cutoff_date = datetime.now() - timedelta(days=Config.MAX_SCREENSHOT_AGE_DAYS)
            cutoff_timestamp = cutoff_date.timestamp()
            
            deleted_count = 0
            deleted_bytes = 0
            
            for screenshot_file in Config.SCREENSHOT_DIR.glob("*.jpg"):
                try:
                    # Check file modification time
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
                # Check if User Agent is running
                # This is optional - you could implement process monitoring here
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
            
            # Start User Agent monitor thread (optional)
            monitor_thread = threading.Thread(target=self._monitor_user_agent, daemon=True)
            monitor_thread.start()
            self.threads.append(monitor_thread)
            
            logger.info("Service Watchdog started successfully")
            logger.info("Listening for User Agent connections...")
            
            # Main loop - just keep running
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
