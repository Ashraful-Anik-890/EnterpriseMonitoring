"""
Shared Configuration Module - ENHANCED
Used by both Service Watchdog and User Agent

ADDITIONS:
- Server sync configuration (SERVER_URL, API_KEY)
- Export directory path
- Sync interval settings
- Client ID generation for server identification
"""

import os
import uuid
from pathlib import Path
from typing import Dict, Any
import json


class Config:
    """Centralized configuration for Enterprise Monitoring Agent"""
    
    # Version
    VERSION = "2.0.0"
    
    # IPC Settings
    IPC_HOST = "127.0.0.1"
    IPC_PORT = 51234
    IPC_AUTH_TOKEN = "ENTERPRISE_MONITOR_SECRET_2024"  # Change in production
    
    # Paths (ProgramData for service compatibility)
    if os.name == 'nt':  # Windows
        BASE_DIR = Path("C:/ProgramData/EnterpriseMonitoring")
    else:  # Unix/Linux fallback
        BASE_DIR = Path("/var/lib/enterprise-monitoring")
    
    DATA_DIR = BASE_DIR / "data"
    LOG_DIR = BASE_DIR / "logs"
    CONFIG_DIR = BASE_DIR / "config"
    SCREENSHOT_DIR = DATA_DIR / "screenshots"
    EXPORT_DIR = BASE_DIR / "Exports"  # NEW: For JSON exports
    
    # Database
    DATABASE_PATH = DATA_DIR / "monitoring.db"
    
    # Monitoring Settings
    SCREENSHOT_INTERVAL = 1.0  # seconds (1 fps time-lapse)
    CLIPBOARD_POLL_INTERVAL = 0.5  # seconds
    APP_USAGE_POLL_INTERVAL = 1.0  # seconds
    
    # Screenshot Settings
    SCREENSHOT_QUALITY = 50  # JPEG quality (0-100)
    SCREENSHOT_SCALE = 0.5  # Scale to 50% to save space
    
    # Data Retention (Local Storage)
    RETENTION_DAYS = 30  # Keep data locally for 30 days
    MAX_SCREENSHOT_AGE_DAYS = 7  # Keep screenshots for 7 days
    
    # NEW: Server Sync Settings (Grammarly-Style Cloud Sync)
    ENABLE_SERVER_SYNC = True  # Set to False to disable cloud sync
    SERVER_URL = "https://api.enterprisemonitoring.com/v1/sync"  # Change to your server
    API_KEY = "sk_live_placeholder_key_change_in_production"  # CHANGE THIS IN PRODUCTION
    SYNC_INTERVAL_SECONDS = 300  # Sync every 5 minutes (300 seconds)
    SYNC_BATCH_SIZE = 100  # Max records per sync request
    SYNC_RETRY_ATTEMPTS = 3  # Number of retry attempts
    SYNC_RETRY_DELAY = 60  # Delay between retries (seconds)
    
    # NEW: Temporary Local Storage for Offline Sync
    # Data is kept locally for 3-5 days even after syncing, in case server is unreachable
    LOCAL_RETENTION_DAYS = 5  # Keep synced data locally for 5 days as backup
    
    # Performance
    MAX_QUEUE_SIZE = 1000  # Max events to queue before dropping
    IPC_RECONNECT_DELAY = 5  # seconds
    IPC_TIMEOUT = 30  # seconds
    
    # Encryption
    ENCRYPTION_ENABLED = True
    
    # NEW: Client Identification
    _client_id = None
    
    @classmethod
    def get_client_id(cls) -> str:
        """
        Get or generate unique client ID for server identification
        
        This ID is used to identify this specific installation to the server.
        It's generated once and stored in config file.
        
        Returns:
            str: Unique client identifier (UUID)
        """
        if cls._client_id:
            return cls._client_id
        
        config_file = cls.get_config_file()
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    if 'client_id' in config:
                        cls._client_id = config['client_id']
                        return cls._client_id
            except Exception:
                pass
        
        # Generate new client ID
        cls._client_id = str(uuid.uuid4())
        
        # Save to config
        try:
            cls.ensure_directories()
            existing_config = cls.load_custom_config()
            existing_config['client_id'] = cls._client_id
            cls.save_custom_config(existing_config)
        except Exception:
            pass
        
        return cls._client_id
    
    @classmethod
    def ensure_directories(cls):
        """Create all required directories"""
        for directory in [cls.DATA_DIR, cls.LOG_DIR, cls.CONFIG_DIR, 
                         cls.SCREENSHOT_DIR, cls.EXPORT_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_config_file(cls) -> Path:
        """Get path to configuration file"""
        return cls.CONFIG_DIR / "settings.json"
    
    @classmethod
    def load_custom_config(cls) -> Dict[str, Any]:
        """Load custom configuration if exists"""
        config_file = cls.get_config_file()
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    @classmethod
    def save_custom_config(cls, config: Dict[str, Any]):
        """Save custom configuration"""
        cls.ensure_directories()
        config_file = cls.get_config_file()
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    @classmethod
    def update_from_custom_config(cls):
        """
        Update class variables from custom config file
        
        This allows users to override default settings by editing
        C:\ProgramData\EnterpriseMonitoring\config\settings.json
        """
        custom_config = cls.load_custom_config()
        
        # Update settings from custom config
        mapping = {
            'screenshot_interval': 'SCREENSHOT_INTERVAL',
            'screenshot_quality': 'SCREENSHOT_QUALITY',
            'screenshot_scale': 'SCREENSHOT_SCALE',
            'clipboard_poll_interval': 'CLIPBOARD_POLL_INTERVAL',
            'app_usage_poll_interval': 'APP_USAGE_POLL_INTERVAL',
            'retention_days': 'RETENTION_DAYS',
            'max_screenshot_age_days': 'MAX_SCREENSHOT_AGE_DAYS',
            'encryption_enabled': 'ENCRYPTION_ENABLED',
            'enable_server_sync': 'ENABLE_SERVER_SYNC',
            'server_url': 'SERVER_URL',
            'api_key': 'API_KEY',
            'sync_interval_seconds': 'SYNC_INTERVAL_SECONDS',
        }
        
        for config_key, class_attr in mapping.items():
            if config_key in custom_config:
                setattr(cls, class_attr, custom_config[config_key])