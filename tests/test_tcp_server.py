#!/usr/bin/env python3
"""
Unit tests for TcpServer class
"""
import socket
import threading
import time
import unittest
from unittest.mock import Mock, patch

# Add src to path so we can import our modules
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from tcp_server import TcpServer


class TestTcpServer(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.server = TcpServer('127.0.0.1', 0, 5)  # Use random port
        self.test_message_handlers = {}
        
    def tearDown(self):
        """Clean up after each test method."""
        if hasattr(self, 'server') and self.server.running:
            self.server.stop()
            
    def test_init(self):
        """Test TcpServer initialization"""
        self.assertEqual(self.server.host, '127.0.0.1')
        self.assertEqual(self.server.port, 0)
        self.assertEqual(self.server.max_clients, 5)
        self.assertFalse(self.server.running)
        self.assertEqual(len(self.server.connected_clients), 0)
        
    def test_register_message_handler(self):
        """Test registering message handlers"""
        def dummy_handler(args, client_socket):
            pass
            
        self.server.register_message_handler('test', dummy_handler)
        self.assertIn('test', self.server.message_handlers)
        self.assertEqual(self.server.message_handlers['test'], dummy_handler)
        
    @patch('socket.socket')
    def test_start_server_success(self, mock_socket_class):
        """Test successful server start"""
        # Mock the socket to return a valid socket object
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket
        
        # Test that server starts without error
        self.server.start()
        
        # Verify socket was created and configured properly
        mock_socket_class.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
        mock_socket.setsockopt.assert_called_once()
        mock_socket.bind.assert_called_once()
        mock_socket.listen.assert_called_once()
        
    @patch('socket.socket')
    def test_start_server_failure(self, mock_socket_class):
        """Test server start failure"""
        # Mock the socket to raise an exception
        mock_socket_class.side_effect = Exception("Socket error")
        
        # Test that server handles the error gracefully
        self.server.start()
        self.assertFalse(self.server.running)
        
    def test_stop_server(self):
        """Test stopping server"""
        # Start the server (this is a no-op since we don't actually bind in tests)
        self.server.running = True
        
        # Stop the server
        self.server.stop()
        
        # Verify server state
        self.assertFalse(self.server.running)
        self.assertEqual(len(self.server.connected_clients), 0)
        
    def test_process_message_known_command(self):
        """Test that a registered handler is invoked with args and socket"""
        mock_socket = Mock()
        received = {}

        def handler(args, client_socket):
            received['args'] = args
            received['socket'] = client_socket

        self.server.register_message_handler('identify', handler)
        self.server._process_message('identify', ['client_1'], mock_socket)

        self.assertEqual(received['args'], ['client_1'])
        self.assertIs(received['socket'], mock_socket)

    def test_process_message_handler_error_is_logged(self):
        """Test that a handler exception is logged, not raised"""
        def handler(args, client_socket):
            raise RuntimeError("boom")

        self.server.register_message_handler('identify', handler)
        with patch.object(self.server.logger, 'error') as mock_logger:
            self.server._process_message('identify', [], Mock())

        self.assertTrue(any("boom" in str(c.args[0]) for c in mock_logger.call_args_list))

    def test_process_message_unknown_command(self):
        """Test processing unknown command"""
        with patch.object(self.server.logger, 'warning') as mock_logger:
            # This should not raise an exception
            self.server._process_message('unknown', [], None)
            mock_logger.assert_called_once()

    def test_broadcast_sends_line_to_all_clients(self):
        """Test that broadcast writes the sync line to every connected client"""
        client_a = Mock()
        client_b = Mock()
        self.server.add_client(client_a)
        self.server.add_client(client_b)

        self.server.broadcast("sync pe1.mp4 0.0")

        client_a.send.assert_called_once_with(b"sync pe1.mp4 0.0")
        client_b.send.assert_called_once_with(b"sync pe1.mp4 0.0")

    def test_broadcast_drops_dead_client(self):
        """Test that a client whose send fails is removed from the list"""
        live = Mock()
        dead = Mock()
        dead.send.side_effect = OSError("gone")
        self.server.add_client(live)
        self.server.add_client(dead)

        with patch.object(self.server.logger, 'error'):
            self.server.broadcast("sync pe1.mp4 12.00")

        self.assertEqual(self.server.connected_clients, [live])
        live.send.assert_called_once()

    def test_broadcast_with_no_clients(self):
        """Test that broadcasting with no clients is a no-op"""
        self.server.broadcast("sync pe1.mp4 0.0")  # Should not raise

    def test_remove_client(self):
        """Test that remove_client removes a tracked client"""
        client = Mock()
        self.server.add_client(client)
        self.server.remove_client(client)
        self.assertEqual(self.server.connected_clients, [])
        # Removing an untracked client is a no-op
        self.server.remove_client(client)

    def test_client_connection_roundtrip(self):
        """Integration test: a real client socket receives a broadcast line"""
        # Reserve an ephemeral port
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(('127.0.0.1', 0))
        self.server.port = probe.getsockname()[1]
        probe.close()

        self.server.start()
        self.assertTrue(self.server.running)

        conn = socket.create_connection(('127.0.0.1', self.server.port))
        try:
            # Wait for the server to track the connection
            deadline = time.time() + 2
            while time.time() < deadline and not self.server.connected_clients:
                time.sleep(0.01)
            self.assertTrue(self.server.connected_clients)

            # The client sends "identify" and receives the sync broadcast
            conn.sendall(b"identify client_1\n")
            self.server.broadcast("sync pe1.mp4 0.0")
            self.assertEqual(conn.recv(1024), b"sync pe1.mp4 0.0")
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
