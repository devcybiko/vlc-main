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
            'player': {
                'default_video': 'default.mp4'
            },
            'location': {
                'latitude': 37.3229,
                'longitude': -77.3064,
                'timezone': 'America/New_York'
            },
            'schedule': {
                'videos': ['video1.mp4', 'video2.mp4', 'video3.mp4'],
                'start': '17:30',
                'end': '22:00'
            }
        }
        self.scheduler = ScheduleManager(self.config)
        
    def _dt(self, hour, minute, tz=timezone.utc):
        """Build a tz-aware datetime for a test case"""
        return datetime(2026, 11, 22, hour, minute, tzinfo=tz)
        
    def test_init(self):
        """Test ScheduleManager initialization"""
        self.assertEqual(self.scheduler.videos, ['video1.mp4', 'video2.mp4', 'video3.mp4'])
        self.assertEqual(str(self.scheduler.start_time), '17:30:00')
        self.assertEqual(str(self.scheduler.end_time), '22:00:00')
        
    def test_parse_hhmm(self):
        """Test HH:MM parsing"""
        self.assertEqual(str(self.scheduler._parse_hhmm('08:05')), '08:05:00')
        self.assertIsNone(self.scheduler._parse_hhmm(None))
        self.assertIsNone(self.scheduler._parse_hhmm('garbage'))
        self.assertIsNone(self.scheduler._parse_hhmm('25:99'))
        
    def test_in_window_uses_local_timezone(self):
        """Test window evaluation in the configured timezone (not UTC)"""
        # 22:30 UTC == 17:30 America/New_York (EST) -> window starts here
        self.assertTrue(self.scheduler.in_window(self._dt(22, 30)))
        # 23:00 UTC == 18:00 local -> inside the window
        self.assertTrue(self.scheduler.in_window(self._dt(23, 0)))
        # 02:59 UTC == 21:59 local (previous day) -> still inside
        self.assertTrue(self.scheduler.in_window(self._dt(2, 59)))
        # 03:00 UTC == 22:00 local (previous day) -> window is over
        self.assertFalse(self.scheduler.in_window(self._dt(3, 0)))
        # 22:29 UTC == 17:29 local -> one minute before the window
        self.assertFalse(self.scheduler.in_window(self._dt(22, 29)))
        
    def test_in_window_naive_datetime(self):
        """Test that naive datetimes are treated as local time"""
        naive = datetime(2026, 11, 22, 18, 0)
        self.assertTrue(self.scheduler.in_window(naive))
        
    def test_in_window_no_times_always_true(self):
        """Test that missing start/end means the window is always open"""
        self.config['schedule'] = {'videos': ['video1.mp4']}
        scheduler = ScheduleManager(self.config)
        self.assertTrue(scheduler.in_window(self._dt(0, 0)))
        self.assertTrue(scheduler.in_window(self._dt(23, 59)))
        
    def test_in_window_overnight(self):
        """Test a window that wraps past midnight"""
        self.config['schedule'] = {
            'videos': ['video1.mp4'],
            'start': '22:00',
            'end': '02:00'
        }
        scheduler = ScheduleManager(self.config)
        # 03:00 UTC == 22:00 local (EST) -> window opens
        self.assertTrue(scheduler.in_window(self._dt(3, 0)))
        # 06:30 UTC == 01:30 local -> still in the window (after midnight)
        self.assertTrue(scheduler.in_window(self._dt(6, 30)))
        # 07:00 UTC == 02:00 local -> window closed
        self.assertFalse(scheduler.in_window(self._dt(7, 0)))
        # 12:00 UTC == 07:00 local -> outside
        self.assertFalse(scheduler.in_window(self._dt(12, 0)))
        
    def test_get_current_video_in_window(self):
        """Test video selection by index inside the window"""
        local_noon = self._dt(23, 0)  # 18:00 local
        self.assertEqual(self.scheduler.get_current_video(local_noon, 0), 'video1.mp4')
        self.assertEqual(self.scheduler.get_current_video(local_noon, 1), 'video2.mp4')
        self.assertEqual(self.scheduler.get_current_video(local_noon, 2), 'video3.mp4')
        # Indices wrap around the list
        self.assertEqual(self.scheduler.get_current_video(local_noon, 3), 'video1.mp4')
        
    def test_get_current_video_outside_window(self):
        """Test that the default video is returned outside the window"""
        local_noon = self._dt(12, 0)  # 07:00 local, before the window
        self.assertEqual(self.scheduler.get_current_video(local_noon, 0), 'default.mp4')
        
    def test_get_current_video_no_videos(self):
        """Test fallback to the default when no videos are configured"""
        self.config['schedule'] = {'videos': [], 'start': '17:30', 'end': '22:00'}
        scheduler = ScheduleManager(self.config)
        self.assertEqual(scheduler.get_current_video(self._dt(23, 0)), 'default.mp4')
        
    def test_next_video_advances(self):
        """Test that next_video returns the following entry in the list"""
        local_noon = self._dt(23, 0)  # 18:00 local
        self.assertEqual(self.scheduler.next_video(local_noon, 'video1.mp4'), 'video2.mp4')
        self.assertEqual(self.scheduler.next_video(local_noon, 'video2.mp4'), 'video3.mp4')
        # Wraps back to the first video
        self.assertEqual(self.scheduler.next_video(local_noon, 'video3.mp4'), 'video1.mp4')
        
    def test_next_video_unknown_current(self):
        """Test that an unknown current video falls back to the first entry"""
        local_noon = self._dt(23, 0)  # 18:00 local
        self.assertEqual(self.scheduler.next_video(local_noon, 'other.mp4'), 'video1.mp4')
        
    def test_next_video_outside_window(self):
        """Test that next_video returns the default outside the window"""
        early = self._dt(12, 0)  # 07:00 local
        self.assertEqual(self.scheduler.next_video(early, 'video1.mp4'), 'default.mp4')
        
    def test_unknown_timezone_falls_back_to_utc(self):
        """Test that an invalid timezone name falls back to UTC"""
        self.config['location'] = {'timezone': 'Not/AZone'}
        scheduler = ScheduleManager(self.config)
        # 17:30 UTC now that the window is evaluated in UTC
        self.assertTrue(scheduler.in_window(self._dt(17, 30)))
        self.assertFalse(scheduler.in_window(self._dt(17, 29)))
        

if __name__ == '__main__':
    unittest.main()
