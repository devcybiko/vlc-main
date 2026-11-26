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
                'end': '18:00',
                'sync_secs': 15
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
        mock_vlc.start_video.assert_called_once_with('test_video_1.mp4', start_time=0.0)
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
        mock_vlc.start_video.assert_called_once_with('test_video_2.mp4', start_time=0.0)
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
        mock_vlc.start_video.assert_called_once_with('test_video_1.mp4', start_time=0.0)

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

    def test_is_playing_scheduled(self):
        """Test scheduled-vs-default detection by file name"""
        with patch.object(self.controller, 'vlc_player') as mock_vlc:
            mock_vlc.current_video = '/home/greg/videos/test_video_1.mp4'
            self.assertTrue(self.controller._is_playing_scheduled())
            mock_vlc.current_video = '/home/greg/videos/test.mp4'
            self.assertFalse(self.controller._is_playing_scheduled())
            mock_vlc.current_video = None
            self.assertFalse(self.controller._is_playing_scheduled())

    def test_window_end_stops_scheduled_video(self):
        """Test that reaching the end time stops the scheduled loop"""
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller.schedule_manager, 'in_window',
                          return_value=False), \
             patch.object(self.controller, '_is_playing_scheduled',
                          return_value=True):
            self.controller.playing = True
            self.controller._check_window_boundary()

        mock_vlc.stop_video.assert_called_once()
        self.assertFalse(self.controller.playing)

    def test_window_end_ignores_default_video(self):
        """Test that an out-of-window default video is left untouched"""
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller.schedule_manager, 'in_window',
                          return_value=False), \
             patch.object(self.controller, '_is_playing_scheduled',
                          return_value=False):
            self.controller.playing = True
            self.controller._check_window_boundary()

        mock_vlc.stop_video.assert_not_called()
        self.assertTrue(self.controller.playing)

    def test_window_start_stops_default_video(self):
        """Test that reaching the start time interrupts the default video"""
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller.schedule_manager, 'in_window',
                          return_value=True), \
             patch.object(self.controller, '_is_playing_scheduled',
                          return_value=False):
            self.controller.playing = True
            self.controller._check_window_boundary()

        mock_vlc.stop_video.assert_called_once()
        self.assertFalse(self.controller.playing)

    def test_window_inside_keeps_scheduled_video(self):
        """Test that a scheduled video inside the window is left running"""
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller.schedule_manager, 'in_window',
                          return_value=True), \
             patch.object(self.controller, '_is_playing_scheduled',
                          return_value=True):
            self.controller.playing = True
            self.controller._check_window_boundary()

        mock_vlc.stop_video.assert_not_called()
        self.assertTrue(self.controller.playing)

    def test_run_checks_boundary_while_playing(self):
        """Test that the run loop checks the window boundary on each tick"""
        with patch.object(self.controller, 'start'), \
             patch.object(self.controller, 'stop'), \
             patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch('playlist_controller.time.sleep', side_effect=KeyboardInterrupt), \
             patch.object(self.controller, '_check_window_boundary') as mock_check:
            self.controller.running = True
            self.controller.playing = True
            mock_vlc.is_running.return_value = True
            self.controller.run()

        mock_check.assert_called_once()

    def test_validate_config_bad_schedule(self):
        """Test that a non-dict schedule is rejected"""
        original_config = self.controller.config
        self.controller.config['schedule'] = [{'video': 'x.mp4'}]
        with patch.object(self.controller, 'logger'):
            self.assertFalse(self.controller._validate_config())

        self.controller.config = original_config

    def test_handle_sync_command_different_video(self):
        """Test sync with a different video stops the current and starts the named one"""
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller, '_broadcast_sync'):
            mock_vlc.current_video = '/videos/pe1.mp4'
            mock_vlc.start_video.return_value = True

            self.controller._handle_sync_command(['pe2.mp4', '30.5'])

            mock_vlc.stop_video.assert_called_once()
            mock_vlc.seek_to.assert_not_called()
            mock_vlc.start_video.assert_called_once_with('pe2.mp4', start_time=30.5)
            self.assertTrue(self.controller.playing)

    def test_handle_sync_command_same_video(self):
        """Test sync with the same video seeks the current playback"""
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller, '_broadcast_sync'):
            mock_vlc.current_video = '/videos/pe2.mp4'
            mock_vlc.seek_to.return_value = True

            self.controller._handle_sync_command(['pe2.mp4', '12.00'])

            mock_vlc.stop_video.assert_not_called()
            mock_vlc.start_video.assert_not_called()
            mock_vlc.seek_to.assert_called_once_with(12.0)
            self.assertTrue(self.controller.playing)

    def test_handle_sync_command_same_video_seek_failure(self):
        """Test a failed seek logs an error and does not start a new video"""
        with patch.object(self.controller, 'logger') as mock_logger, \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller, '_broadcast_sync'):
            mock_vlc.current_video = '/videos/pe2.mp4'
            mock_vlc.seek_to.return_value = False

            self.controller._handle_sync_command(['pe2.mp4', '12.00'])

            mock_vlc.start_video.assert_not_called()
            self.assertTrue(any("Failed to seek" in str(c.args[0]) for c in mock_logger.error.call_args_list))

    def test_handle_sync_command_nothing_playing(self):
        """Test sync with no current video starts the named video"""
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller, '_broadcast_sync'):
            mock_vlc.current_video = None
            mock_vlc.start_video.return_value = True

            self.controller._handle_sync_command(['pe3.mp4', '0.0'])

            mock_vlc.stop_video.assert_called_once()
            mock_vlc.seek_to.assert_not_called()
            mock_vlc.start_video.assert_called_once_with('pe3.mp4', start_time=0.0)

    def test_handle_sync_command_malformed_args(self):
        """Test a sync line with the wrong argument count is rejected"""
        with patch.object(self.controller, 'logger') as mock_logger, \
             patch.object(self.controller, 'vlc_player') as mock_vlc:
            self.controller._handle_sync_command(['pe2.mp4'])

            mock_vlc.start_video.assert_not_called()
            mock_vlc.seek_to.assert_not_called()
            mock_vlc.stop_video.assert_not_called()
            mock_logger.warn.assert_called_once()

    def test_handle_sync_command_bad_timestamp(self):
        """Test a sync line with a bad timestamp is rejected"""
        with patch.object(self.controller, 'logger') as mock_logger, \
             patch.object(self.controller, 'vlc_player') as mock_vlc:
            self.controller._handle_sync_command(['pe2.mp4', 'not-a-number'])

            mock_vlc.start_video.assert_not_called()
            mock_vlc.seek_to.assert_not_called()
            mock_vlc.stop_video.assert_not_called()
            mock_logger.warn.assert_called_once()

    def test_handle_client_identify(self):
        """Test handling client identification"""
        with patch.object(self.controller, 'logger') as mock_logger:
            self.controller._handle_client_identify(['client_1'], Mock())

        mock_logger.info.assert_called_once()
            
    @patch('playlist_controller.TcpClient')
    def test_start_client_success(self, mock_tcp_client_class):
        """Test successful client start"""
        mock_client = Mock()
        mock_tcp_client_class.return_value = mock_client
        mock_client.run.return_value = True
        
        result = self.controller._start_client()
        
        self.assertTrue(result)
        mock_tcp_client_class.assert_called_once_with('127.0.0.1', 8080)  # No client or server section
        
    @patch('playlist_controller.TcpClient')
    def test_start_client_failure(self, mock_tcp_client_class):
        """Test client start failure"""
        mock_client = Mock()
        mock_tcp_client_class.return_value = mock_client
        mock_client.run.return_value = False
        
        result = self.controller._start_client()
        
        self.assertFalse(result)
        
    @patch('playlist_controller.TcpClient')
    def test_start_client_uses_server_tcp_config(self, mock_tcp_client_class):
        """Test client start uses host/port from server.tcp"""
        mock_client = Mock()
        mock_tcp_client_class.return_value = mock_client
        mock_client.run.return_value = True

        self.controller.config['server'] = {
            'tcp': {
                'host': 'vlc-00',
                'port': 8080,
                'max_clients': 10
            }
        }

        result = self.controller._start_client()

        self.assertTrue(result)
        mock_tcp_client_class.assert_called_once_with('vlc-00', 8080)
        self.assertIs(self.controller.tcp_client, mock_client)

    @patch('playlist_controller.TcpClient')
    def test_start_client_registers_sync_handler(self, mock_tcp_client_class):
        """Test the client registers a handler for sync commands"""
        mock_client = Mock()
        mock_tcp_client_class.return_value = mock_client
        mock_client.run.return_value = True

        self.controller._start_client()

        mock_client.register_message_handler.assert_called_once_with(
            'sync', self.controller._handle_sync_command)

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

    def _swap_server_tcp(self, tcp: dict):
        """Temporarily replace the controller's server.tcp config section"""
        original = self.controller.config.get('server')
        self.controller.config['server'] = {'tcp': tcp}
        return original

    def _restore_server(self, original):
        """Restore the server config section swapped by _swap_server_tcp"""
        if original is None:
            self.controller.config.pop('server', None)
        else:
            self.controller.config['server'] = original

    @patch('playlist_controller.TcpServer')
    def test_start_server_binds_all_interfaces_by_default(self, mock_tcp_server_class):
        """Server binds to 0.0.0.0 even when config host is a hostname"""
        original = self._swap_server_tcp(
            {'host': 'vlc-00', 'port': 8080, 'max_clients': 10})
        try:
            with patch.object(self.controller, 'logger'):
                self.controller._start_server()
            mock_tcp_server_class.assert_called_once_with('0.0.0.0', 8080, 10)
        finally:
            self._restore_server(original)

    @patch('playlist_controller.TcpServer')
    def test_start_server_honors_bind_host(self, mock_tcp_server_class):
        """An explicit bind_host overrides the default bind address"""
        original = self._swap_server_tcp(
            {'host': 'vlc-00', 'bind_host': '192.168.1.197', 'port': 8080})
        try:
            with patch.object(self.controller, 'logger'):
                self.controller._start_server()
            mock_tcp_server_class.assert_called_once_with('192.168.1.197', 8080, 10)
        finally:
            self._restore_server(original)

    def test_start_video_broadcasts_sync_zero(self):
        """Test that starting a video broadcasts 'sync <video name> 0.0' to clients"""
        mock_server = Mock()
        self.controller.tcp_server = mock_server
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc:
            mock_vlc.start_video.return_value = True
            mock_vlc.current_video = '/videos/pe1.mp4'
            self.controller._start_video_by_name('pe1.mp4')

        mock_server.broadcast.assert_called_once_with('sync pe1.mp4 0.0')

    def test_start_video_no_broadcast_without_server(self):
        """Test that starting a video is a no-op for sync when no server is running"""
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch.object(self.controller, 'tcp_server', Mock()) as mock_server:
            mock_vlc.start_video.return_value = True
            self.controller.tcp_server = None
            self.controller._start_video_by_name('pe1.mp4')

        mock_server.broadcast.assert_not_called()

    def test_broadcast_sync_formats_two_decimals(self):
        """Test that periodic sync lines use the 'sync <name> <ss.nn>' format"""
        mock_server = Mock()
        self.controller.tcp_server = mock_server
        with patch.object(self.controller, 'vlc_player') as mock_vlc:
            mock_vlc.current_video = '/videos/pe2.mp4'
            self.controller._broadcast_sync(12.5)

        mock_server.broadcast.assert_called_once_with('sync pe2.mp4 12.50')

    def test_send_periodic_sync(self):
        """Test that the periodic sync broadcasts the current video position"""
        mock_server = Mock()
        self.controller.tcp_server = mock_server
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch('playlist_controller.time.time', side_effect=[116.0, 116.0]):
            mock_vlc.current_video = '/videos/pe1.mp4'
            self.controller.playing = True
            self.controller._video_start_time = 100.0
            self.controller._last_sync_time = 100.0
            self.controller._send_periodic_sync()

        mock_server.broadcast.assert_called_once_with('sync pe1.mp4 16.00')

    def test_send_periodic_sync_not_due(self):
        """Test that no sync is sent before sync_secs have elapsed"""
        mock_server = Mock()
        self.controller.tcp_server = mock_server
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc, \
             patch('playlist_controller.time.time', return_value=110.0):
            mock_vlc.current_video = '/videos/pe1.mp4'
            self.controller.playing = True
            self.controller._video_start_time = 100.0
            self.controller._last_sync_time = 100.0
            self.controller._send_periodic_sync()

        mock_server.broadcast.assert_not_called()

    def test_send_periodic_sync_without_sync_secs(self):
        """Test that no periodic sync is sent when schedule.sync_secs is unset"""
        mock_server = Mock()
        self.controller.tcp_server = mock_server
        self.controller.config['schedule'] = {
            'videos': ['test_video_1.mp4'],
            'start': '08:00',
            'end': '18:00'
        }
        self.controller.playing = True
        self.controller._video_start_time = 100.0
        self.controller._last_sync_time = 100.0
        with patch.object(self.controller, 'logger'), \
             patch.object(self.controller, 'vlc_player') as mock_vlc:
            mock_vlc.current_video = '/videos/pe1.mp4'
            self.controller._send_periodic_sync()

        mock_server.broadcast.assert_not_called()

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