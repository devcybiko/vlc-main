#!/usr/bin/env python3
"""
Unit tests for TcpClient class
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

from tcp_client import TcpClient


class TestTcpClient(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.client = TcpClient('127.0.0.1', 8080, 'test_client')
        
    def tearDown(self):
        """Clean up after each test method."""
        if hasattr(self, 'client') and self.client.connected:
            self.client.disconnect()
            
    def test_init(self):
        """Test TcpClient initialization"""
        self.assertEqual(self.client.server_host, '127.0.0.1')
        self.assertEqual(self.client.server_port, 8080)
        self.assertEqual(self.client.client_id, 'test_client')
        self.assertFalse(self.client.connected)
        self.assertFalse(self.client.running)
        self.assertEqual(self.client.reconnect_attempts, 0)
        
    def test_init_with_auto_id(self):
        """Test TcpClient initialization with auto-generated ID"""
        client = TcpClient('127.0.0.1', 8080)
        self.assertTrue(client.client_id.startswith('client_'))
        
    def test_register_message_handler(self):
        """Test registering message handlers"""
        def dummy_handler(message):
            pass
            
        self.client.register_message_handler('test', dummy_handler)
        self.assertIn('test', self.client.message_handlers)
        self.assertEqual(self.client.message_handlers['test'], dummy_handler)
        
    @patch('socket.socket')
    def test_connect_success(self, mock_socket_class):
        """Test successful client connection"""
        # Mock the socket to return a valid socket object
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket
        
        # Mock the connect method
        mock_socket.connect.return_value = None
        
        # Mock the recv to simulate server response
        mock_socket.recv.return_value = json.dumps({
            "command": "identify",
            "type": "vlc_server"
        }).encode('utf-8')
        
        result = self.client.connect()
        
        self.assertTrue(result)
        self.assertTrue(self.client.connected)
        mock_socket.connect.assert_called_once_with(('127.0.0.1', 8080))
        
    @patch('socket.socket')
    def test_connect_failure(self, mock_socket_class):
        """Test client connection failure"""
        # Mock the socket to raise an exception
        mock_socket_class.side_effect = Exception("Connection error")
        
        result = self.client.connect()
        
        self.assertFalse(result)
        self.assertFalse(self.client.connected)
        
    def test_disconnect(self):
        """Test disconnect functionality"""
        # Set up a fake connected state for testing
        self.client.connected = True
        self.client.running = True
        
        with patch.object(self.client, 'socket', Mock()):
            self.client.disconnect()
            
            self.assertFalse(self.client.connected)
            self.assertFalse(self.client.running)
            
    def test_is_connected(self):
        """Test is_connected method"""
        # Test when not connected
        self.assertFalse(self.client.is_connected())
        
        # Test when connected
        self.client.connected = True
        self.client.running = True
        self.assertTrue(self.client.is_connected())
        
    def test_send_message(self):
        """Test sending messages"""
        # Test sending without connection
        result = self.client.send_message({"command": "test"})
        self.assertFalse(result)
        
    def test_process_message_unknown_command(self):
        """Test processing unknown command"""
        with patch.object(self.client.logger, 'warning') as mock_logger:
            message = {'command': 'unknown'}
            # This should not raise an exception
            self.client._process_message(message)
            mock_logger.assert_called_once()


if __name__ == '__main__':
    unittest.main()