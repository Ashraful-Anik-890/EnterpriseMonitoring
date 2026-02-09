"""
Encryption Manager
Handles encryption/decryption of sensitive data
"""

import base64
import hashlib
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Union
import logging

logger = logging.getLogger(__name__)


class CryptoManager:
    """Manages encryption for sensitive monitoring data"""
    
    def __init__(self, key_path: Path = None):
        """
        Initialize crypto manager
        
        Args:
            key_path: Path to encryption key file (auto-generated if not exists)
        """
        self.key_path = key_path or Path("C:/ProgramData/EnterpriseMonitoring/config/.encryption_key")
        self.cipher = self._load_or_create_cipher()
    
    def _load_or_create_cipher(self) -> Fernet:
        """Load existing encryption key or create new one"""
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if self.key_path.exists():
                with open(self.key_path, 'rb') as f:
                    key = f.read()
                logger.info("Loaded existing encryption key")
            else:
                # Generate new key
                key = Fernet.generate_key()
                with open(self.key_path, 'wb') as f:
                    f.write(key)
                
                # Hide key file on Windows
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(str(self.key_path), 0x02)  # Hidden
                except Exception:
                    pass
                
                logger.info("Generated new encryption key")
            
            return Fernet(key)
            
        except Exception as e:
            logger.error(f"Error initializing encryption: {e}")
            raise
    
    def encrypt(self, data: Union[str, bytes]) -> str:
        """
        Encrypt data
        
        Args:
            data: String or bytes to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            encrypted = self.cipher.encrypt(data)
            return base64.b64encode(encrypted).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data
        
        Args:
            encrypted_data: Base64-encoded encrypted string
            
        Returns:
            Decrypted string
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise
    
    def hash_data(self, data: str) -> str:
        """
        Create SHA256 hash of data
        
        Args:
            data: String to hash
            
        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
