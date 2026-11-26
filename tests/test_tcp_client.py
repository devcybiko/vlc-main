#!/usr/bin/env python3
"""
Unit tests for TcpClient class
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
        def dummy_handler(args):
            pass
            
        self.client.register_message_handler('test', dummy_handler)
        self.assertIn('test', self.client.message_handlers)
        self.assertEqual(self.client.message_handlers['test'], dummy_handler)
        
    @patch('socket.socket')
    def test_connect_success(self, mock_socket_class):
        """Test successful client connection sends an identify line"""
        # Mock the socket to return a valid socket object
        mock_socket = Mock()
        mock_socket_class.return_value = mock_socket
        
        # Mock the connect method
        mock_socket.connect.return_value = None
        
        result = self.client.connect()
        
        self.assertTrue(result)
        self.assertTrue(self.client.connected)
        mock_socket.connect.assert_called_once_with(('127.0.0.1', 8080))
        mock_socket.send.assert_called_once_with(b"identify test_client\n")
        
    @patch('socket.socket')
    def test_connect_failure(self, mock_socket_class):
        """Test client connection failure"""
        # Mock the socket to raise an exception
        mock_socket_class.side_effect = Exception("Connection error")
        
        result = self.client.connect()
        
        self.assertFalse(result)
        self.assertFalse(self.client.connected)
        
    def test_connect_idempotent(self):
        """Test that connecting when already connected is a no-op"""
        self.client.connected = True
        self.client.socket = Mock()
        with patch.object(self.client, 'socket', Mock()) as mock_socket:
            result = self.client.connect()
        self.assertTrue(result)
        mock_socket.connect.assert_not_called()

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
        
    def test_send_message_not_connected(self):
        """Test sending a message without a connection fails"""
        result = self.client.send_message("status ok")
        self.assertFalse(result)

    def test_send_message_connected(self):
        """Test sending a text line to the server"""
        self.client.connected = True
        with patch.object(self.client, 'socket', Mock()) as mock_socket:
            result = self.client.send_message("status ok")

        self.assertTrue(result)
        mock_socket.send.assert_called_once_with(b"status ok\n")

    def test_process_message_known_command(self):
        """Test that a registered handler is invoked with the args list"""
        received = {}

        def handler(args):
            received['args'] = args

        self.client.register_message_handler('sync', handler)
        self.client._process_message('sync', ['pe1.mp4', '12.00'])

        self.assertEqual(received['args'], ['pe1.mp4', '12.00'])

    def test_process_message_handler_error_is_logged(self):
        """Test that a handler exception is logged, not raised"""
        def handler(args):
            raise RuntimeError("boom")

        self.client.register_message_handler('sync', handler)
        with patch.object(self.client.logger, 'error') as mock_logger:
            self.client._process_message('sync', [])

        self.assertTrue(any("boom" in str(c.args[0]) for c in mock_logger.call_args_list))

    def test_process_message_unknown_command(self):
        """Test processing unknown command"""
        with patch.object(self.client.logger, 'warning') as mock_logger:
            # This should not raise an exception
            self.client._process_message('unknown', [])
            mock_logger.assert_called_once()


if __name__ == '__main__':
    unittest.main()