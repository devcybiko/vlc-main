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
            'schedule': {
                'videos': ['test_video_1.mp4', 'test_video_2.mp4'],
                'start': '08:00',
                'end': '18:00'
            }
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
            
    def test_start_initial_video(self):
        """Test that the initial start plays the currently scheduled video"""
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller.schedule_manager, 'get_current_video',
                          return_value='test_video_1.mp4') as mock_select:
            mock_vlc.start_video.return_value = True
            self.controller._start_initial_video()

        mock_select.assert_called_once()
        mock_vlc.start_video.assert_called_once_with('test_video_1.mp4')
        self.assertTrue(self.controller.playing)

    def test_start_initial_video_failure(self):
        """Test that a failed start leaves playing False and logs the error"""
        with patch.object(self.controller, 'logger') as mock_logger, \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller.schedule_manager, 'get_current_video',
                          return_value='test_video_1.mp4'):
            mock_vlc.start_video.return_value = False
            self.controller._start_initial_video()

        self.assertFalse(self.controller.playing)
        self.assertTrue(any("test_video_1.mp4" in str(c.args[0]) for c in mock_logger.error.call_args_list))

    def test_start_initial_video_no_video(self):
        """Test that a missing selection logs a warning and does not start VLC"""
        with patch.object(self.controller, 'logger') as mock_logger, \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller.schedule_manager, 'get_current_video',
                          return_value=None):
            self.controller._start_initial_video()

        mock_vlc.start_video.assert_not_called()
        self.assertFalse(self.controller.playing)

    def test_advance_video(self):
        """Test that _advance_video moves to the next scheduled index"""
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller.schedule_manager, 'get_current_video',
                          return_value='test_video_2.mp4') as mock_select:
            mock_vlc.start_video.return_value = True
            self.controller._advance_video()

        self.assertEqual(self.controller.video_index, 1)
        mock_select.assert_called_once()
        mock_vlc.start_video.assert_called_once_with('test_video_2.mp4')
        self.assertTrue(self.controller.playing)

    def test_advance_video_wraps_around(self):
        """Test that the video index wraps back to the first entry"""
        self.controller.video_index = 1
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller.schedule_manager, 'get_current_video',
                          return_value='test_video_1.mp4'):
            mock_vlc.start_video.return_value = True
            self.controller._advance_video()

        self.assertEqual(self.controller.video_index, 0)
        mock_vlc.start_video.assert_called_once_with('test_video_1.mp4')

    def test_run_starts_next_when_video_ends(self):
        """Test that the run loop advances when the current video process exits"""
        with patch.object(self.controller, 'start'), \
             patch.object(self.controller, 'stop'), \
             patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch('playlist_controller.time.sleep', side_effect=KeyboardInterrupt), \
             patch.object(self.controller, '_advance_video') as mock_advance:
            self.controller.running = True
            self.controller.playing = True
            mock_vlc.is_running.return_value = False
            self.controller.run()

        mock_vlc.is_running.assert_called_once()
        mock_advance.assert_called_once()

    def test_run_starts_video_when_idle(self):
        """Test that the run loop starts a video when nothing is playing"""
        with patch.object(self.controller, 'start'), \
             patch.object(self.controller, 'stop'), \
             patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch('playlist_controller.time.sleep', side_effect=KeyboardInterrupt), \
             patch.object(self.controller, '_start_initial_video') as mock_start:
            self.controller.running = True
            self.controller.playing = False
            self.controller.run()

        mock_start.assert_called_once()

    def test_run_dry_run_skips_playback(self):
        """Test that dry-run mode never touches the player in the loop"""
        self.controller.config['dry_run'] = True
        with patch.object(self.controller, 'start'), \
             patch.object(self.controller, 'stop'), \
             patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch('playlist_controller.time.sleep', side_effect=KeyboardInterrupt):
            self.controller.running = True
            self.controller.playing = False
            self.controller.run()

        mock_vlc.start_video.assert_not_called()
        mock_vlc.is_running.assert_not_called()

    def test_validate_config_bad_schedule(self):
        """Test that a non-dict schedule is rejected"""
        original_config = self.controller.config
        self.controller.config['schedule'] = [{'video': 'x.mp4'}]
        with patch.object(self.controller, 'logger'):
            self.assertFalse(self.controller._validate_config())

        self.controller.config = original_config

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
        
    @patch('playlist_controller.TcpClient')
    def test_start_client_custom_config(self, mock_tcp_client_class):
        """Test client start uses host/port from configuration"""
        mock_client = Mock()
        mock_tcp_client_class.return_value = mock_client
        mock_client.run.return_value = True
        
        self.controller.config['client'] = {
            'tcp': {
                'host': '10.0.0.5',
                'port': 9999
            }
        }
        
        result = self.controller._start_client()
        
        self.assertTrue(result)
        mock_tcp_client_class.assert_called_once_with('10.0.0.5', 9999)
        self.assertIs(self.controller.tcp_client, mock_client)
        
    @patch('playlist_controller.TcpClient')
    def test_start_client_failure_clears_client(self, mock_tcp_client_class):
        """Test that a failed client start leaves no stale client behind"""
        mock_client = Mock()
        mock_tcp_client_class.return_value = mock_client
        mock_client.run.return_value = False
        
        result = self.controller._start_client()
        
        self.assertFalse(result)
        self.assertIsNone(self.controller.tcp_client)
        
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
            
    def test_stop_clears_running_flag(self):
        """Test that stop() clears the running flag"""
        self.controller.running = True
        
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc:
            self.controller.stop()
            
        self.assertFalse(self.controller.running)
        mock_vlc.stop_video.assert_called_once()
        
    def test_stop_stops_tcp_server(self):
        """Test that stop() stops an active TCP server"""
        mock_server = Mock()
        self.controller.tcp_server = mock_server
        
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc:
            self.controller.stop()
            
        mock_vlc.stop_video.assert_called_once()
        mock_server.stop.assert_called_once()
        
    def test_stop_disconnects_tcp_client(self):
        """Test that stop() disconnects an active TCP client"""
        mock_client = Mock()
        self.controller.tcp_client = mock_client
        
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc:
            self.controller.stop()
            
        mock_vlc.stop_video.assert_called_once()
        mock_client.disconnect.assert_called_once()
        
    def test_stop_survives_vlc_player_error(self):
        """Test that a VLC stop error does not prevent network cleanup"""
        mock_server = Mock()
        mock_client = Mock()
        self.controller.tcp_server = mock_server
        self.controller.tcp_client = mock_client
        
        with patch.object(self.controller, 'logger') as mock_logger, \
             patch.object(self.controller, 'vlc_player') as mock_vlc:
            mock_vlc.stop_video.side_effect = RuntimeError("vlc died")
            self.controller.stop()
            
        self.assertFalse(self.controller.running)
        mock_server.stop.assert_called_once()
        mock_client.disconnect.assert_called_once()
        self.assertTrue(any("vlc died" in str(call.args[0]) for call in mock_logger.error.call_args_list))
        
    def test_stop_survives_tcp_server_error(self):
        """Test that a TCP server stop error does not prevent client cleanup"""
        mock_server = Mock()
        mock_client = Mock()
        self.controller.tcp_server = mock_server
        self.controller.tcp_client = mock_client
        
        with patch.object(self.controller, 'logger') as mock_logger, \
             patch.object(self.controller, 'vlc_player') as mock_vlc:
            mock_server.stop.side_effect = RuntimeError("server error")
            self.controller.stop()
            
        mock_client.disconnect.assert_called_once()
        self.assertTrue(any("server error" in str(call.args[0]) for call in mock_logger.error.call_args_list))
        
    def test_stop_survives_tcp_client_error(self):
        """Test that a TCP client disconnect error is logged, not raised"""
        mock_client = Mock()
        self.controller.tcp_client = mock_client
        
        with patch.object(self.controller, 'logger') as mock_logger, \
             patch.object(self.controller, 'vlc_player') as mock_vlc:
            mock_client.disconnect.side_effect = RuntimeError("client error")
            self.controller.stop()
            
        self.assertTrue(any("client error" in str(call.args[0]) for call in mock_logger.error.call_args_list))
        
    def test_signal_handler_stops(self):
        """Test that the signal handler triggers a clean shutdown"""
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'stop') as mock_stop:
            self.controller._signal_handler(signal.SIGTERM, None)
            
        mock_stop.assert_called_once()


if __name__ == '__main__':
    unittest.main()