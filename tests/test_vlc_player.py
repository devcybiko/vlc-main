#!/usr/bin/env python3
"""
Unit tests for VlcPlayer class
"""
import os
import unittest
from unittest.mock import Mock, patch

# Add src to path so we can import our modules
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from vlc_player import VlcPlayer


class TestVlcPlayer(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.config = {
            'vlc': {
                'options': ['--test-option']
            }
        }
        self.player = VlcPlayer(self.config)
        
    def test_init(self):
        """Test VlcPlayer initialization"""
        self.assertEqual(self.player.config, self.config)
        self.assertIsNone(self.player.process)
        self.assertIsNone(self.player.current_video)
        
    @patch('subprocess.Popen')
    def test_start_video_success(self, mock_popen):
        """Test successful video start"""
        # Mock a successful process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        result = self.player.start_video('/fake/video.mp4')
        
        self.assertTrue(result)
        self.assertEqual(self.player.current_video, '/fake/video.mp4')
        mock_popen.assert_called_once()
        
    @patch('subprocess.Popen')
    def test_start_video_file_not_found(self, mock_popen):
        """Test starting video when file doesn't exist"""
        # Mock the process but simulate file not found
        result = self.player.start_video('/nonexistent/video.mp4')
        
        # Should return False since file doesn't exist (but subprocess won't be called)
        self.assertFalse(result)
        
    @patch('subprocess.Popen')
    def test_start_video_exception(self, mock_popen):
        """Test starting video with exception"""
        mock_popen.side_effect = Exception("Process error")
        
        result = self.player.start_video('/fake/video.mp4')
        
        self.assertFalse(result)
        
    def test_stop_video_no_process(self):
        """Test stopping video when no process is running"""
        result = self.player.stop_video()
        
        self.assertTrue(result)
        self.assertIsNone(self.player.process)
        self.assertIsNone(self.player.current_video)
        
    @patch('subprocess.Popen')
    def test_stop_video_with_process(self, mock_popen):
        """Test stopping video with active process"""
        # Mock a successful process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Process is still running
        mock_popen.return_value = mock_process
        
        # Start a video first
        self.player.start_video('/fake/video.mp4')
        
        # Stop the video
        result = self.player.stop_video()
        
        self.assertTrue(result)
        self.assertIsNone(self.player.process)
        self.assertIsNone(self.player.current_video)
        
    def test_is_running_no_process(self):
        """Test is_running when no process"""
        self.assertFalse(self.player.is_running())
        
    @patch('subprocess.Popen')
    def test_is_running_with_process(self, mock_popen):
        """Test is_running with active process"""
        # Mock a successful process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Process is still running
        mock_popen.return_value = mock_process
        
        # Start a video first
        self.player.start_video('/fake/video.mp4')
        
        self.assertTrue(self.player.is_running())


if __name__ == '__main__':
    unittest.main()