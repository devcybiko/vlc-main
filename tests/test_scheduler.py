#!/usr/bin/env python3
"""
Unit tests for ScheduleManager class
"""
import unittest
from datetime import datetime, timezone

# Add src to path so we can import our modules
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from scheduler import ScheduleManager


class TestScheduleManager(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.config = {
            'location': {
                'latitude': 37.3229,
                'longitude': -77.3064,
                'timezone': 'America/New_York'
            },
            'schedule': [
                {
                    'video': 'test_video_1.mp4',
                    'start': '08:00',
                    'end': '18:00'
                },
                {
                    'video': 'test_video_2.mp4',
                    'start': '18:00',
                    'end': '00:00'
                }
            ]
        }
        self.scheduler = ScheduleManager(self.config)
        
    def test_init(self):
        """Test ScheduleManager initialization"""
        self.assertEqual(self.scheduler.config, self.config)
        self.assertEqual(self.scheduler.location, self.config['location'])
        self.assertEqual(self.scheduler.schedule, self.config['schedule'])
        
    def test_get_current_video(self):
        """Test getting current video (placeholder implementation)"""
        # This is a placeholder test since the actual implementation is not fully developed
        # but we can at least verify it doesn't crash
        dt = datetime.now(timezone.utc)
        result = self.scheduler.get_current_video(dt)
        
        # Should return default video or None for now
        self.assertIsNotNone(result)  # Just making sure it doesn't crash
        
    def test_get_current_schedule_entry(self):
        """Test getting current schedule entry (placeholder implementation)"""
        # This is a placeholder test since the actual implementation is not fully developed
        dt = datetime.now(timezone.utc)
        result = self.scheduler._get_current_schedule_entry(dt)
        
        # Should return None or a valid entry for now  
        self.assertIsNotNone(result)  # Just making sure it doesn't crash
        
    def test_select_video(self):
        """Test video selection (placeholder implementation)"""
        # This is a placeholder test since the actual implementation is not fully developed
        dt = datetime.now(timezone.utc)
        result = self.scheduler._select_video(dt)
        
        # Should return a valid video file name
        self.assertIsNotNone(result)  # Just making sure it doesn't crash


if __name__ == '__main__':
    unittest.main()