"""
Shared Configuration Module
Used by both Service Watchdog and User Agent
"""

import os
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
    
    # Database
    DATABASE_PATH = DATA_DIR / "monitoring.db"
    
    # Monitoring Settings
    SCREENSHOT_INTERVAL = 1.0  # seconds (1 fps time-lapse)
    CLIPBOARD_POLL_INTERVAL = 0.5  # seconds
    APP_USAGE_POLL_INTERVAL = 1.0  # seconds
    
    # Screenshot Settings
    SCREENSHOT_QUALITY = 50  # JPEG quality (0-100)
    SCREENSHOT_SCALE = 0.5  # Scale to 50% to save space
    
    # Data Retention
    RETENTION_DAYS = 30
    MAX_SCREENSHOT_AGE_DAYS = 7
    
    # Performance
    MAX_QUEUE_SIZE = 1000  # Max events to queue before dropping
    IPC_RECONNECT_DELAY = 5  # seconds
    IPC_TIMEOUT = 30  # seconds
    
    # Encryption
    ENCRYPTION_ENABLED = True
    
    @classmethod
    def ensure_directories(cls):
        """Create all required directories"""
        for directory in [cls.DATA_DIR, cls.LOG_DIR, cls.CONFIG_DIR, cls.SCREENSHOT_DIR]:
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
