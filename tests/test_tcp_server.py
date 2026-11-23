#!/usr/bin/env python3
"""
Unit tests for TcpServer class
"""
import json
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
        def dummy_handler(message, client_socket):
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
        
    def test_process_message_unknown_command(self):
        """Test processing unknown command"""
        with patch.object(self.server.logger, 'warning') as mock_logger:
            message = {'command': 'unknown'}
            # This should not raise an exception
            self.server._process_message(message, None)
            mock_logger.assert_called_once()


if __name__ == '__main__':
    unittest.main()