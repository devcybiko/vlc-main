#!/usr/bin/env python3
"""
Unit tests for VlcPlaylist controller class
"""
import json
import os
import signal
import sys
import unittest
from unittest.mock import Mock, patch

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from glslib import Application
from playlist_controller import VlcPlaylist


class TestVlcPlaylist(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Build the controller through its real constructor, stubbing only
        # CLI argument parsing and configuration loading.
        config_dict = {
            'player': {
                'default_video': 'test.mp4'
            },
            'location': {
                'latitude': 37.3229,
                'longitude': -77.3064
            },
            'vlc': {
                'options': ['--test']
            },
            'schedule': [
                {
                    'video': 'test_video_1.mp4',
                    'start': '08:00',
                    'end': '18:00'
                }
            ]
        }
        with patch.object(sys, 'argv', [__file__]), \
             patch.object(Application, '_config_load', return_value=config_dict):
            self.controller = VlcPlaylist()
            self.controller.logger = Mock()
            
    def test_init(self):
        """Test VlcPlaylist initialization"""
        self.assertIsNotNone(self.controller.vlc_player)
        self.assertIsNotNone(self.controller.schedule_manager)
        self.assertFalse(self.controller.running)
        self.assertIsNone(self.controller.tcp_server)
        self.assertIsNone(self.controller.tcp_client)
        
    def test_arg_parse(self):
        """Test argument parsing"""
        parser = Mock()
        result = self.controller._arg_parse(parser)
        
        # Verify it returns the parser and adds our arguments
        self.assertIs(result, parser)
        parser.add_argument.assert_any_call("--dry-run", action="store_true", help="Evaluate scheduling without actual playback")
        parser.add_argument.assert_any_call("--client", action="store_true", help="Run in client mode, connecting to parent server")
            
    def test_handle_sync_request(self):
        """Test handling sync request"""
        # This should not raise an exception
        mock_socket = Mock()
        message = {
            'timestamp': 1234567890,
            'video_position': 300.5
        }
        
        with patch.object(self.controller, 'logger'):
            self.controller._handle_sync_request(message, mock_socket)
            # Should not raise any exceptions
            
    def test_handle_client_sync(self):
        """Test handling client sync"""
        # This should not raise an exception
        mock_socket = Mock()
        message = {
            'timestamp': 1234567890,
            'video_position': 300.5
        }
        
        with patch.object(self.controller, 'logger'):
            self.controller._handle_sync_request(message, mock_socket)
            # Should not raise any exceptions
            
    def test_handle_client_identify(self):
        """Test handling client identification"""
        # This should not raise an exception
        mock_socket = Mock()
        message = {
            'command': 'identify',
            'type': 'vlc_client'
        }
        
        with patch.object(self.controller, 'logger'):
            self.controller._handle_client_identify(message, mock_socket)
            # Should not raise any exceptions
            
    @patch('playlist_controller.TcpClient')
    def test_start_client_success(self, mock_tcp_client_class):
        """Test successful client start"""
        mock_client = Mock()
        mock_tcp_client_class.return_value = mock_client
        mock_client.run.return_value = True
        
        result = self.controller._start_client()
        
        self.assertTrue(result)
        mock_tcp_client_class.assert_called_once_with('192.168.1.100', 8080)  # Default from config
        
    @patch('playlist_controller.TcpClient')
    def test_start_client_failure(self, mock_tcp_client_class):
        """Test client start failure"""
        mock_client = Mock()
        mock_tcp_client_class.return_value = mock_client
        mock_client.run.return_value = False
        
        result = self.controller._start_client()
        
        self.assertFalse(result)
        
    def test_validate_config_success(self):
        """Test successful config validation"""
        # Test with valid config
        result = self.controller._validate_config()
        self.assertTrue(result)
        
    def test_validate_config_missing_sections(self):
        """Test config validation with missing sections"""
        # Temporarily modify config to remove a required section
        original_config = self.controller.config
        del self.controller.config['player']
        
        result = self.controller._validate_config()
        self.assertFalse(result)
        
        # Restore original config
        self.controller.config = original_config
        
    @patch('playlist_controller.TcpServer')
    def test_start_server(self, mock_tcp_server_class):
        """Test server start functionality"""
        # This should not raise an exception
        with patch.object(self.controller, 'logger'):
            self.controller._start_server()
            # Should not raise any exceptions
            
    def test_stop_no_connections(self):
        """Test stopping when no connections are active"""
        # This should not raise an exception
        with patch.object(self.controller, 'logger'):
            self.controller.stop()
            # Should not raise any exceptions


if __name__ == '__main__':
    unittest.main()