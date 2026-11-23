#!/usr/bin/env python3
"""
TCP Server implementation for VLC Playlist Controller
Handles client connections and synchronization messages
"""
import json
import logging
import socket
import threading
from typing import List, Callable

class TcpServer:
    def __init__(self, host: str = '0.0.0.0', port: int = 8080, max_clients: int = 10):
        self.host = host
        self.port = port
        self.max_clients = max_clients
        self.socket = None
        self.running = False
        self.connected_clients = []
        self.logger = logging.getLogger(self.__class__.__name__)
        self.message_handlers = {}
        
    def register_message_handler(self, command: str, handler: Callable):
        """Register a handler function for a specific message command"""
        self.message_handlers[command] = handler
        
    def start(self):
        """Start the TCP server to accept client connections"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(self.max_clients)
            self.running = True
            
            self.logger.info(f"TCP server listening on {self.host}:{self.port}")
            
            def accept_connections():
                while self.running:
                    try:
                        client_socket, address = self.socket.accept()
                        client_thread = threading.Thread(
                            target=self._handle_client_connection,
                            args=(client_socket, address)
                        )
                        client_thread.daemon = True
                        client_thread.start()
                    except Exception as e:
                        if self.running:  # Only log if we're still running
                            self.logger.error(f"Error accepting connection: {e}")
                            
            server_thread = threading.Thread(target=accept_connections)
            server_thread.daemon = True
            server_thread.start()
            
        except Exception as e:
            self.logger.error(f"Failed to start TCP server: {e}")
            self.running = False
            
    def stop(self):
        """Stop the TCP server and close all connections"""
        self.running = False
        
        # Close server socket
        if self.socket:
            self.socket.close()
            
        # Close all client connections
        for client in self.connected_clients[:]:  # Create a copy to avoid modification during iteration
            try:
                client.close()
            except Exception as e:
                self.logger.error(f"Error closing client connection: {e}")
                
        self.connected_clients.clear()
        
    def _handle_client_connection(self, client_socket, address):
        """Handle individual client connection"""
        self.logger.info(f"Client connected from {address}")
        self.connected_clients.append(client_socket)
        
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                    
                try:
                    message = json.loads(data.decode('utf-8'))
                    self._process_message(message, client_socket)
                except json.JSONDecodeError:
                    self.logger.error("Invalid JSON message from client")
                    
        except Exception as e:
            self.logger.error(f"Client handling error: {e}")
        finally:
            if client_socket in self.connected_clients:
                self.connected_clients.remove(client_socket)
            client_socket.close()
            self.logger.info(f"Client {address} disconnected")
            
    def _process_message(self, message, client_socket):
        """Process messages from connected clients"""
        command = message.get('command')
        
        if command in self.message_handlers:
            try:
                handler = self.message_handlers[command]
                handler(message, client_socket)
            except Exception as e:
                self.logger.error(f"Error in message handler for {command}: {e}")
        else:
            self.logger.warning(f"Unknown command from client: {command}")
            
    def send_message(self, client_socket, message):
        """Send a message to a specific client"""
        try:
            client_socket.send(json.dumps(message).encode('utf-8'))
        except Exception as e:
            self.logger.error(f"Failed to send message to client: {e}")