#!/usr/bin/env python3
"""
TCP Server implementation for VLC Playlist Controller
Handles client connections and synchronization messages.

Wire protocol: newline-terminated text lines.
The server sends "sync <video-name> <secs.nn>" to all connected clients.
Clients send "identify <client-id>" when they connect.
"""
import logging
import socket
import threading
from typing import Callable, List

class TcpServer:
    def __init__(self, host: str = '0.0.0.0', port: int = 8080, max_clients: int = 10):
        self.host = host
        self.port = port
        self.max_clients = max_clients
        self.socket: socket.socket | None = None
        self.running = False
        self.connected_clients: List[socket.socket] = []
        self._lock = threading.Lock()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.message_handlers: dict[str, Callable] = {}

    def register_message_handler(self, command: str, handler: Callable):
        """Register a handler for a command; called as handler(args, client_socket)"""
        self.message_handlers[command] = handler

    def start(self):
        """Start the TCP server to accept client connections"""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(self.max_clients)
            self.socket = server_socket
            self.running = True

            self.logger.info(f"TCP server listening on {self.host}:{self.port}")

            def accept_connections():
                while self.running:
                    try:
                        client_socket, address = server_socket.accept()
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
        with self._lock:
            clients = self.connected_clients[:]
            self.connected_clients.clear()

        for client in clients:
            try:
                client.close()
            except Exception as e:
                self.logger.error(f"Error closing client connection: {e}")

    def add_client(self, client_socket: socket.socket):
        """Track a newly connected client"""
        with self._lock:
            self.connected_clients.append(client_socket)

    def remove_client(self, client_socket: socket.socket):
        """Stop tracking a client"""
        with self._lock:
            if client_socket in self.connected_clients:
                self.connected_clients.remove(client_socket)

    def broadcast(self, line: str):
        """Send a text line to all connected clients

        Clients that can no longer be written to are dropped from the list.
        """
        payload = line.encode('utf-8')
        with self._lock:
            clients = self.connected_clients[:]

        for client in clients:
            try:
                client.send(payload)
            except Exception as e:
                self.logger.error(f"Failed to broadcast to client: {e}")
                self.remove_client(client)

    def _handle_client_connection(self, client_socket, address):
        """Handle an individual client connection"""
        self.logger.info(f"Client connected from {address}")
        self.add_client(client_socket)

        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break

                text = data.decode('utf-8', errors='replace')
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    self._process_message(parts[0], parts[1:], client_socket)

        except Exception as e:
            self.logger.error(f"Client handling error: {e}")
        finally:
            self.remove_client(client_socket)
            client_socket.close()
            self.logger.info(f"Client {address} disconnected")

    def _process_message(self, command: str, args: list, client_socket):
        """Process a message line from a connected client"""
        if command in self.message_handlers:
            try:
                handler = self.message_handlers[command]
                handler(args, client_socket)
            except Exception as e:
                self.logger.error(f"Error in message handler for {command}: {e}")
        else:
            self.logger.warning(f"Unknown command from client: {command}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    server = TcpServer()
    server.register_message_handler('identify', lambda args, sock:
                                    print(f"Client identified: {args}"))
    server.start()
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        server.stop()
