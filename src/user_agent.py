"""
User Agent - ENHANCED VERSION
Runs in user session to capture screen, clipboard, and app usage
Fixed with robust error handling and IPC reconnection
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from threading import Thread, Event
import hashlib
import io

# Third-party imports
import mss
import pyperclip
from PIL import Image
import pystray
from pystray import MenuItem as item
import psutil

# Local imports (assume in same directory)
try:
    from config import Config
    from crypto_manager import CryptoManager
    from ipc_manager import IPCClient
except ImportError as e:
    print(f"ERROR: Failed to import modules: {e}")
    print("Make sure all required files are in the same directory")
    sys.exit(1)

# Windows-specific imports
try:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
except ImportError:
    print("ERROR: This application requires Windows")
    sys.exit(1)

# Configure logging
log_dir = Path('C:/ProgramData/EnterpriseMonitoring/logs')
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'agent.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ScreenMonitor:
    """Screen recording monitor using mss"""
    
    def __init__(self, ipc_client, interval=1.0):
        self.ipc_client = ipc_client
        self.interval = interval
        self.running = False
        self.thread = None
        self.screenshots_dir = Path('C:/ProgramData/EnterpriseMonitoring/data/screenshots')
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
    
    def start(self):
        """Start screen monitoring"""
        if not self.running:
            self.running = True
            self.thread = Thread(target=self._capture_loop, daemon=True, name="ScreenMonitor")
            self.thread.start()
            logger.info("Screen Monitor started")
    
    def stop(self):
        """Stop screen monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Screen Monitor stopped")
    
    def _capture_loop(self):
        """Main capture loop"""
        logger.info("Screenshot capture loop started")
        
        with mss.mss() as sct:
            while self.running:
                try:
                    # Capture screenshot
                    monitor = sct.monitors[1]  # Primary monitor
                    screenshot = sct.grab(monitor)
                    
                    # Convert to PIL Image
                    img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
                    
                    # Scale down to 50%
                    new_size = (screenshot.width // 2, screenshot.height // 2)
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # Get active window info
                    active_window, active_app = self._get_active_window()
                    
                    # Save to file
                    timestamp = datetime.now()
                    filename = f"screenshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
                    filepath = self.screenshots_dir / filename
                    
                    img.save(filepath, 'JPEG', quality=50, optimize=True)
                    
                    # Get file size
                    file_size = filepath.stat().st_size
                    
                    # Send to Watchdog via IPC
                    data = {
                        'type': 'screenshot',
                        'timestamp': timestamp.isoformat(),
                        'filepath': str(filepath),
                        'file_size_bytes': file_size,
                        'resolution': f"{new_size[0]}x{new_size[1]}",
                        'active_window': active_window,
                        'active_app': active_app
                    }
                    
                    msg_type = data.pop('type') 
                    self.ipc_client.send_message(msg_type, data)
                    logger.info("Screen Monitor initialized")
                    
                    # Wait for next capture
                    time.sleep(self.interval)
                    
                except Exception as e:
                    logger.error(f"Error in screen capture loop: {e}", exc_info=True)
                    time.sleep(self.interval)
    
    def _get_active_window(self):
        """Get active window title and process name using ctypes"""
        try:
            # Get foreground window
            hwnd = user32.GetForegroundWindow()
            
            if hwnd == 0:
                return "Unknown", "Unknown"
            
            # Get window title
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                title = "Unknown"
            else:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                title = buffer.value
            
            # Get process name
            try:
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                
                process = psutil.Process(pid.value)
                app_name = process.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                app_name = "Unknown"
            
            return title, app_name
            
        except Exception as e:
            logger.debug(f"Error getting active window: {e}")
            return "Unknown", "Unknown"


class ClipboardMonitor:
    """Clipboard monitoring with ROBUST error handling"""
    
    def __init__(self, ipc_client, crypto_manager, interval=0.5):
        self.ipc_client = ipc_client
        self.crypto_manager = crypto_manager
        self.interval = interval
        self.running = False
        self.thread = None
        self.last_hash = None
    
    def start(self):
        """Start clipboard monitoring"""
        if not self.running:
            self.running = True
            self.thread = Thread(target=self._monitor_loop, daemon=True, name="ClipboardMonitor")
            self.thread.start()
            logger.info("Clipboard Monitor started")
    
    def stop(self):
        """Stop clipboard monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Clipboard Monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop with BULLETPROOF error handling"""
        logger.info("Clipboard monitor loop started")
        
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while self.running:
            try:
                # Try to get clipboard content
                content = None
                content_type = None
                
                # CRITICAL: Wrap clipboard access in try-except
                # pyperclip can raise exceptions if clipboard is locked
                try:
                    content = pyperclip.paste()
                    content_type = 'text'
                except Exception as clipboard_error:
                    # Common when clipboard is locked by another app
                    logger.debug(f"Clipboard locked or unavailable: {clipboard_error}")
                    time.sleep(self.interval)
                    continue
                
                # Skip if empty
                if not content or not isinstance(content, str):
                    time.sleep(self.interval)
                    continue
                
                # Calculate hash to detect changes
                content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                
                # Check if content changed
                if content_hash != self.last_hash:
                    self.last_hash = content_hash
                    
                    # Get source application
                    _, source_app = self._get_active_window()
                    
                    # Create preview (first 200 chars)
                    preview = content[:200] if len(content) > 200 else content
                    
                    # Encrypt full content
                    encrypted_content = None
                    if self.crypto_manager:
                        try:
                            encrypted_content = self.crypto_manager.encrypt(content)
                        except Exception as e:
                            logger.error(f"Encryption failed: {e}")
                    
                    # Send to Watchdog
                    data = {
                        'type': 'clipboard_event',
                        'timestamp': datetime.now().isoformat(),
                        'content_type': content_type,
                        'content_preview': preview,
                        'encrypted_content': encrypted_content,
                        'content_hash': content_hash,
                        'source_app': source_app
                    }
                    
                    msg_type = data.pop('type') 
                    self.ipc_client.send_message(msg_type, data)
                    logger.debug(f"Clipboard event logged: {len(content)} chars from {source_app}")
         
                # Reset error counter on success
                consecutive_errors = 0
                
                # Wait before next check
                time.sleep(self.interval)
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in clipboard monitor loop: {e}", exc_info=True)
                
                # If too many errors, give up
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(f"Clipboard monitor failed {consecutive_errors} times, stopping")
                    self.running = False
                    break
                
                # Wait longer after error
                time.sleep(self.interval * 2)
    
    def _get_active_window(self):
        """Get active window title and process name"""
        try:
            hwnd = user32.GetForegroundWindow()
            if hwnd == 0:
                return "Unknown", "Unknown"
            
            # Get window title
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                title = "Unknown"
            else:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                title = buffer.value
            
            # Get process name
            try:
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                process = psutil.Process(pid.value)
                app_name = process.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                app_name = "Unknown"
            
            return title, app_name
            
        except Exception as e:
            logger.debug(f"Error getting active window: {e}")
            return "Unknown", "Unknown"


class AppUsageMonitor:
    """Application usage monitoring with window tracking"""
    
    def __init__(self, ipc_client, interval=1.0):
        self.ipc_client = ipc_client
        self.interval = interval
        self.running = False
        self.thread = None
        self.current_app = None
        self.current_window = None
        self.session_start = None
    
    def start(self):
        """Start app usage monitoring"""
        if not self.running:
            self.running = True
            self.thread = Thread(target=self._monitor_loop, daemon=True, name="AppUsageMonitor")
            self.thread.start()
            logger.info("App Usage Monitor started")
    
    def stop(self):
        """Stop app usage monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("App Usage Monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info("App usage monitor loop started")
        
        while self.running:
            try:
                # Get current active window
                window_title, app_name = self._get_active_window()
                
                # Create session identifier
                session_id = f"{app_name}|{window_title}"
                
                # Check if app/window changed
                if session_id != f"{self.current_app}|{self.current_window}":
                    # Log previous session if exists
                    if self.current_app and self.session_start:
                        duration = (datetime.now() - self.session_start).total_seconds()
                        
                        if duration >= 1.0:  # Only log if duration > 1 second
                            data = {
                                'type': 'app_usage',
                                'timestamp': self.session_start.isoformat(),
                                'app_name': self.current_app,
                                'window_title': self.current_window,
                                'duration_seconds': round(duration, 2)
                            }
                            
                            msg_type = data.pop('type') 
                            self.ipc_client.send_message(msg_type, data)
                            logger.debug(f"App usage logged: {self.current_app} - {duration:.1f}s")
                    
                    # Start new session
                    self.current_app = app_name
                    self.current_window = window_title
                    self.session_start = datetime.now()
                
                # Wait before next check
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"Error in app usage monitor loop: {e}", exc_info=True)
                time.sleep(self.interval)
    
    def _get_active_window(self):
        """Get active window title and process name with ROBUST error handling"""
        try:
            # Get foreground window
            hwnd = user32.GetForegroundWindow()
            
            if hwnd == 0:
                return "Unknown", "Unknown"
            
            # Get window title
            try:
                length = user32.GetWindowTextLengthW(hwnd)
                if length == 0:
                    title = "Unknown"
                else:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value
            except Exception as e:
                logger.debug(f"Error getting window title: {e}")
                title = "Unknown"
            
            # Get process name
            try:
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                
                # Use psutil for process info
                process = psutil.Process(pid.value)
                app_name = process.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.debug(f"Error getting process name: {e}")
                app_name = "Unknown"
            except Exception as e:
                logger.debug(f"Unexpected error getting process: {e}")
                app_name = "Unknown"
            
            return title, app_name
            
        except Exception as e:
            logger.error(f"Error in _get_active_window: {e}", exc_info=True)
            return "Unknown", "Unknown"


class TrayIcon:
    """System tray icon for user control"""
    
    def __init__(self, on_quit):
        self.on_quit = on_quit
        self.icon = None
    
    def create_image(self):
        """Create tray icon image"""
        from PIL import Image, ImageDraw
        
        # Create 64x64 icon
        image = Image.new('RGB', (64, 64), color='white')
        draw = ImageDraw.Draw(image)
        
        # Draw simple monitor icon
        draw.rectangle([10, 15, 54, 45], outline='black', width=3, fill='lightblue')
        draw.rectangle([28, 45, 36, 50], fill='black')
        draw.rectangle([20, 50, 44, 52], fill='black')
        
        return image
    
    def run(self):
        """Run tray icon"""
        menu = pystray.Menu(
            item('Enterprise Monitoring Agent', lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item('Quit', self.on_quit)
        )
        
        self.icon = pystray.Icon(
            "enterprise_agent",
            self.create_image(),
            "Enterprise Monitoring Agent",
            menu
        )
        
        logger.info("Tray icon created")
        self.icon.run()
    
    def stop(self):
        """Stop tray icon"""
        if self.icon:
            self.icon.stop()


class UserAgent:
    """Main User Agent application"""
    
    def __init__(self):
        logger.info("=" * 70)
        logger.info("USER AGENT INITIALIZING")
        logger.info("Version: 2.0.0")
        logger.info("=" * 70)
        
        # Initialize components
        logger.info("Initializing encryption...")
        self.crypto_manager = CryptoManager()
        
        logger.info("Initializing IPC client...")
        self.ipc_client = IPCClient()
        
        logger.info("Initializing monitors...")
        self.screen_monitor = ScreenMonitor(self.ipc_client)
        self.clipboard_monitor = ClipboardMonitor(self.ipc_client, self.crypto_manager)
        self.app_monitor = AppUsageMonitor(self.ipc_client)
        
        self.tray_icon = None
        
        logger.info("User Agent initialized successfully")
    
    def start(self):
        """Start User Agent"""
        logger.info("Starting User Agent...")
        
        # Connect to Service Watchdog
        logger.info("Connecting to Service Watchdog...")
        max_retries = 10
        retry_delay = 2
        
        for attempt in range(1, max_retries + 1):
            if self.ipc_client.connect():
                logger.info("Connected to Service Watchdog")
                break
            else:
                logger.warning(f"Connection attempt {attempt}/{max_retries} failed, retrying...")
                time.sleep(retry_delay)
        else:
            logger.warning("Could not connect to Service Watchdog, will continue trying in background")
        
        # Start monitors
        logger.info("Starting monitors...")
        self.screen_monitor.start()
        self.clipboard_monitor.start()
        self.app_monitor.start()
        
        # Create tray icon
        self.tray_icon = TrayIcon(self.quit)
        
        logger.info("User Agent started successfully")
        
        # Run tray icon (blocks until quit)
        self.tray_icon.run()
    
    def quit(self):
        """Quit User Agent"""
        logger.info("Quit requested from tray menu")
        
        logger.info("Stopping User Agent...")
        
        # Stop monitors
        self.screen_monitor.stop()
        self.clipboard_monitor.stop()
        self.app_monitor.stop()
        
        # Disconnect IPC
        self.ipc_client.disconnect()
        
        # Stop tray icon
        if self.tray_icon:
            self.tray_icon.stop()
        
        logger.info("User Agent stopped")


def main():
    """Main entry point"""
    try:
        agent = UserAgent()
        agent.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()