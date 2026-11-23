#!/usr/bin/env python3
"""
TCP Client implementation for VLC Playlist Controller
Handles connection to parent server and synchronization messages
"""
import json
import logging
import socket
import threading
import time
from typing import Callable, List

class TcpClient:
    def __init__(self, server_host: str, server_port: int, client_id: str = None):
        self.server_host = server_host
        self.server_port = server_port
        self.client_id = client_id or f"client_{int(time.time())}"
        self.socket = None
        self.running = False
        self.connected = False
        self.logger = logging.getLogger(self.__class__.__name__)
        self.message_handlers = {}
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # seconds
        
    def register_message_handler(self, command: str, handler: Callable):
        """Register a handler function for a specific message command"""
        self.message_handlers[command] = handler
        
    def connect(self):
        """Connect to the parent server"""
        if self.connected:
            return True
            
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_host, self.server_port))
            self.connected = True
            self.reconnect_attempts = 0
            
            # Send identification
            identify_msg = {
                "command": "identify",
                "type": "vlc_client",
                "id": self.client_id
            }
            self.send_message(identify_msg)
            
            self.logger.info(f"Connected to server {self.server_host}:{self.server_port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to server {self.server_host}:{self.server_port}: {e}")
            self.connected = False
            return False
            
    def disconnect(self):
        """Disconnect from the parent server"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                self.logger.error(f"Error closing socket: {e}")
        self.connected = False
        
    def start_listening(self):
        """Start listening for messages from the server"""
        if not self.connected:
            return
            
        self.running = True
            
        def listen_loop():
            while self.running and self.connected:
                try:
                    data = self.socket.recv(1024)
                    if not data:
                        # Connection closed by server
                        self.logger.info("Server connection closed")
                        self.connected = False
                        break
                        
                    try:
                        message = json.loads(data.decode('utf-8'))
                        self._process_message(message)
                    except json.JSONDecodeError:
                        self.logger.error("Invalid JSON message from server")
                        
                except socket.error as e:
                    if self.running:  # Only log if we're still trying to run
                        self.logger.error(f"Socket error while listening: {e}")
                        # Attempt to reconnect
                        self._attempt_reconnect()
                except Exception as e:
                    if self.running:
                        self.logger.error(f"Error while listening for messages: {e}")
                        self._attempt_reconnect()
                        
        listen_thread = threading.Thread(target=listen_loop)
        listen_thread.daemon = True
        listen_thread.start()
        
    def _attempt_reconnect(self):
        """Attempt to reconnect to the server"""
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            self.logger.info(f"Attempting to reconnect... ({self.reconnect_attempts}/{self.max_reconnect_attempts})")
            
            time.sleep(self.reconnect_delay)
            
            if self.connect():
                self.reconnect_attempts = 0
                self.logger.info("Reconnected successfully")
                
    def _process_message(self, message):
        """Process messages from the server"""
        command = message.get('command')
        
        if command in self.message_handlers:
            try:
                handler = self.message_handlers[command]
                handler(message)
            except Exception as e:
                self.logger.error(f"Error in message handler for {command}: {e}")
        else:
            self.logger.warning(f"Unknown command from server: {command}")
            
    def send_message(self, message):
        """Send a message to the server"""
        if not self.connected or not self.socket:
            self.logger.error("Not connected to server")
            return False
            
        try:
            self.socket.send(json.dumps(message).encode('utf-8'))
            return True
        except Exception as e:
            self.logger.error(f"Failed to send message to server: {e}")
            self.connected = False
            return False
            
    def is_connected(self):
        """Check if client is connected to the server"""
        return self.connected and self.running
        
    def run(self):
        """Main run loop - connect and start listening"""
        if not self.connect():
            self.logger.error("Failed to connect to server")
            return False
            
        self.start_listening()
        return True