"""
IPC Manager
Handles socket-based communication between Service Watchdog and User Agent
"""

import socket
import json
import struct
import threading
import time
from typing import Dict, Any, Callable, Optional
import logging
from queue import Queue, Full

from config import Config

logger = logging.getLogger(__name__)


class IPCMessage:
    """IPC message structure"""
    
    def __init__(self, msg_type: str, data: Dict[str, Any], auth_token: str = None):
        """
        Create IPC message
        
        Args:
            msg_type: Message type (screenshot, clipboard, app_usage, ping, etc.)
            data: Message payload
            auth_token: Authentication token
        """
        self.msg_type = msg_type
        self.data = data
        self.auth_token = auth_token or Config.IPC_AUTH_TOKEN
        self.timestamp = time.time()
    
    def to_json(self) -> str:
        """Convert message to JSON string"""
        return json.dumps({
            'msg_type': self.msg_type,
            'data': self.data,
            'auth_token': self.auth_token,
            'timestamp': self.timestamp
        }, default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'IPCMessage':
        """Create message from JSON string"""
        obj = json.loads(json_str)
        msg = cls(
            msg_type=obj['msg_type'],
            data=obj['data'],
            auth_token=obj.get('auth_token')
        )
        msg.timestamp = obj.get('timestamp', time.time())
        return msg


class IPCServer:
    """
    IPC Server (Used by Service Watchdog)
    Listens for connections from User Agent and processes messages
    """
    
    def __init__(self, host: str = Config.IPC_HOST, port: int = Config.IPC_PORT):
        """
        Initialize IPC server
        
        Args:
            host: Host to bind to (localhost)
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.server_thread: Optional[threading.Thread] = None
        self.message_handlers: Dict[str, Callable] = {}
        self.connected_clients = []
        
        logger.info(f"IPC Server initialized on {host}:{port}")
    
    def register_handler(self, msg_type: str, handler: Callable[[Dict[str, Any]], None]):
        """
        Register message handler
        
        Args:
            msg_type: Message type to handle
            handler: Callback function to process message data
        """
        self.message_handlers[msg_type] = handler
        logger.info(f"Registered handler for message type: {msg_type}")
    
    def start(self):
        """Start IPC server"""
        if self.running:
            logger.warning("IPC Server already running")
            return
        
        self.running = True
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()
        
        logger.info("IPC Server started")
    
    def stop(self):
        """Stop IPC server"""
        self.running = False
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        
        # Close all client connections
        for client in self.connected_clients:
            try:
                client.close()
            except Exception:
                pass
        
        logger.info("IPC Server stopped")
    
    def _server_loop(self):
        """Main server loop"""
        try:
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)  # Non-blocking accept
            
            logger.info(f"IPC Server listening on {self.host}:{self.port}")
            
            while self.running:
                try:
                    # Accept connection
                    client_socket, address = self.server_socket.accept()
                    logger.info(f"Client connected from {address}")
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket,),
                        daemon=True
                    )
                    client_thread.start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        logger.error(f"Server accept error: {e}")
                    time.sleep(1)
        
        except Exception as e:
            logger.error(f"Server loop error: {e}")
        finally:
            logger.info("Server loop ended")
    
    def _handle_client(self, client_socket: socket.socket):
        """Handle client connection"""
        self.connected_clients.append(client_socket)
        
        try:
            while self.running:
                # Receive message length (4 bytes)
                length_data = self._recv_exact(client_socket, 4)
                if not length_data:
                    break
                
                msg_length = struct.unpack('!I', length_data)[0]
                
                # Receive message data
                msg_data = self._recv_exact(client_socket, msg_length)
                if not msg_data:
                    break
                
                # Process message
                try:
                    message = IPCMessage.from_json(msg_data.decode('utf-8'))
                    
                    # Verify auth token
                    if message.auth_token != Config.IPC_AUTH_TOKEN:
                        logger.warning("Invalid auth token received")
                        continue
                    
                    # Handle message
                    self._process_message(message)
                    
                except Exception as e:
                    logger.error(f"Message processing error: {e}")
        
        except Exception as e:
            logger.error(f"Client handler error: {e}")
        finally:
            try:
                client_socket.close()
            except Exception:
                pass
            
            if client_socket in self.connected_clients:
                self.connected_clients.remove(client_socket)
            
            logger.info("Client disconnected")
    
    def _recv_exact(self, sock: socket.socket, n: int) -> bytes:
        """Receive exactly n bytes from socket"""
        data = b''
        while len(data) < n:
            try:
                chunk = sock.recv(n - len(data))
                if not chunk:
                    return b''
                data += chunk
            except Exception as e:
                logger.error(f"Socket receive error: {e}")
                return b''
        return data
    
    def _process_message(self, message: IPCMessage):
        """Process received message"""
        handler = self.message_handlers.get(message.msg_type)
        
        if handler:
            try:
                handler(message.data)
            except Exception as e:
                logger.error(f"Handler error for {message.msg_type}: {e}")
        else:
            logger.warning(f"No handler registered for message type: {message.msg_type}")


class IPCClient:
    """
    IPC Client (Used by User Agent)
    Connects to Service Watchdog and sends monitoring data
    """
    
    def __init__(self, host: str = Config.IPC_HOST, port: int = Config.IPC_PORT):
        """
        Initialize IPC client
        
        Args:
            host: Server host
            port: Server port
        """
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.lock = threading.Lock()
        
        # Message queue for when disconnected
        self.message_queue = Queue(maxsize=Config.MAX_QUEUE_SIZE)
        
        logger.info(f"IPC Client initialized for {host}:{port}")
    
    def connect(self) -> bool:
        """
        Connect to IPC server
        
        Returns:
            True if connected successfully
        """
        with self.lock:
            if self.connected:
                return True
            
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(Config.IPC_TIMEOUT)
                self.socket.connect((self.host, self.port))
                self.connected = True
                
                logger.info(f"Connected to IPC server at {self.host}:{self.port}")
                
                # Flush queued messages
                self._flush_queue()
                
                return True
                
            except Exception as e:
                logger.error(f"Connection failed: {e}")
                self.connected = False
                return False
    
    def disconnect(self):
        """Disconnect from server"""
        with self.lock:
            if self.socket:
                try:
                    self.socket.close()
                except Exception:
                    pass
                self.socket = None
            
            self.connected = False
            logger.info("Disconnected from IPC server")
    
    def send_message(self, msg_type: str, data: Dict[str, Any]) -> bool:
        """
        Send message to server
        
        Args:
            msg_type: Message type
            data: Message data
            
        Returns:
            True if sent successfully
        """
        message = IPCMessage(msg_type, data)
        
        # If not connected, queue message
        if not self.connected:
            try:
                self.message_queue.put_nowait(message)
                logger.debug(f"Queued message: {msg_type} (queue size: {self.message_queue.qsize()})")
                return False
            except Full:
                logger.warning(f"Message queue full, dropping message: {msg_type}")
                return False
        
        # Send message
        return self._send_message_direct(message)
    
    def _send_message_direct(self, message: IPCMessage) -> bool:
        """Send message directly to server"""
        with self.lock:
            try:
                if not self.connected or not self.socket:
                    return False
                
                # Serialize message
                msg_data = message.to_json().encode('utf-8')
                msg_length = len(msg_data)
                
                # Send length (4 bytes) + data
                length_bytes = struct.pack('!I', msg_length)
                self.socket.sendall(length_bytes + msg_data)
                
                logger.debug(f"Sent message: {message.msg_type}")
                return True
                
            except Exception as e:
                logger.error(f"Send error: {e}")
                self.connected = False
                return False
    
    def _flush_queue(self):
        """Send all queued messages"""
        count = 0
        while not self.message_queue.empty():
            try:
                message = self.message_queue.get_nowait()
                if self._send_message_direct(message):
                    count += 1
                else:
                    # Put back in queue if send failed
                    self.message_queue.put_nowait(message)
                    break
            except Exception:
                break
        
        if count > 0:
            logger.info(f"Flushed {count} queued messages")
    
    def is_connected(self) -> bool:
        """Check if connected to server"""
        return self.connected
    
    def auto_reconnect_loop(self):
        """Auto-reconnect loop (run in separate thread)"""
        while True:
            if not self.connected:
                logger.info("Attempting to reconnect to IPC server...")
                self.connect()
            
            time.sleep(Config.IPC_RECONNECT_DELAY)
