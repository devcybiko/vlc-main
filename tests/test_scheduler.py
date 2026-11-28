#!/usr/bin/env python3
"""
Unit tests for ScheduleManager class
"""
import unittest
from datetime import datetime

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
        
    def _dt(self, hour, minute):
        """Build a naive local datetime for a test case"""
        return datetime(2026, 11, 22, hour, minute)

    def _aware_dt(self, hour, minute):
        """Build a tz-aware datetime representing a local wall time"""
        return datetime(2026, 11, 22, hour, minute).astimezone()
        
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
        
    def test_in_window_naive_datetime(self):
        """Test that naive datetimes are treated as local time"""
        # 17:30 local -> window starts here
        self.assertTrue(self.scheduler.in_window(self._dt(17, 30)))
        # 18:00 local -> inside the window
        self.assertTrue(self.scheduler.in_window(self._dt(18, 0)))
        # 21:59 local -> still inside
        self.assertTrue(self.scheduler.in_window(self._dt(21, 59)))
        # 22:00 local -> window is over (end-exclusive)
        self.assertFalse(self.scheduler.in_window(self._dt(22, 0)))
        # 17:29 local -> one minute before the window
        self.assertFalse(self.scheduler.in_window(self._dt(17, 29)))
        # 08:00 local -> well before the window
        self.assertFalse(self.scheduler.in_window(self._dt(8, 0)))

    def test_in_window_aware_datetime(self):
        """Test that aware datetimes are converted to the system local timezone"""
        # Local wall times expressed as tz-aware datetimes
        self.assertTrue(self.scheduler.in_window(self._aware_dt(17, 30)))
        self.assertTrue(self.scheduler.in_window(self._aware_dt(18, 0)))
        self.assertFalse(self.scheduler.in_window(self._aware_dt(17, 29)))
        self.assertFalse(self.scheduler.in_window(self._aware_dt(23, 0)))

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
        # 22:00 local -> window opens
        self.assertTrue(scheduler.in_window(self._dt(22, 0)))
        # 01:30 local -> still in the window (after midnight)
        self.assertTrue(scheduler.in_window(self._dt(1, 30)))
        # 02:00 local -> window closed
        self.assertFalse(scheduler.in_window(self._dt(2, 0)))
        # 07:00 local -> outside
        self.assertFalse(scheduler.in_window(self._dt(7, 0)))
        
    def test_get_current_video_in_window(self):
        """Test video selection by index inside the window"""
        in_window = self._dt(18, 0)  # 18:00 local
        self.assertEqual(self.scheduler.get_current_video(in_window, 0), 'video1.mp4')
        self.assertEqual(self.scheduler.get_current_video(in_window, 1), 'video2.mp4')
        self.assertEqual(self.scheduler.get_current_video(in_window, 2), 'video3.mp4')
        # Indices wrap around the list
        self.assertEqual(self.scheduler.get_current_video(in_window, 3), 'video1.mp4')
        
    def test_get_current_video_outside_window(self):
        """Test that the default video is returned outside the window"""
        before = self._dt(7, 0)  # 07:00 local, before the window
        self.assertEqual(self.scheduler.get_current_video(before, 0), 'default.mp4')
        
    def test_get_current_video_no_videos(self):
        """Test fallback to the default when no videos are configured"""
        self.config['schedule'] = {'videos': [], 'start': '17:30', 'end': '22:00'}
        scheduler = ScheduleManager(self.config)
        self.assertEqual(scheduler.get_current_video(self._dt(23, 0)), 'default.mp4')
        
    def test_next_video_advances(self):
        """Test that next_video returns the following entry in the list"""
        in_window = self._dt(18, 0)  # 18:00 local
        self.assertEqual(self.scheduler.next_video(in_window, 'video1.mp4'), 'video2.mp4')
        self.assertEqual(self.scheduler.next_video(in_window, 'video2.mp4'), 'video3.mp4')
        # Wraps back to the first video
        self.assertEqual(self.scheduler.next_video(in_window, 'video3.mp4'), 'video1.mp4')
        
    def test_next_video_unknown_current(self):
        """Test that an unknown current video falls back to the first entry"""
        in_window = self._dt(18, 0)  # 18:00 local
        self.assertEqual(self.scheduler.next_video(in_window, 'other.mp4'), 'video1.mp4')
        
    def test_next_video_outside_window(self):
        """Test that next_video returns the default outside the window"""
        early = self._dt(12, 0)  # 12:00 local
        self.assertEqual(self.scheduler.next_video(early, 'video1.mp4'), 'default.mp4')
        

if __name__ == '__main__':
    unittest.main()
