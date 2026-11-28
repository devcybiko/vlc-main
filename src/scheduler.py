#!/usr/bin/env python3
"""
Schedule management for the VLC playlist controller

The schedule config looks like:
    "schedule": {
        "videos": ["video1.mp4", "video2.mp4"],
        "start": "17:30",
        "end": "22:00"
    }

Within the window the listed videos play in order and loop back to the
first when the last one ends. Outside the window the configured
default video plays. Times are interpreted in the system's local
timezone; overnight windows (end <= start) wrap past midnight.
"""
import logging
from datetime import datetime, time
from typing import Dict, List, Optional

class ScheduleManager:
    def __init__(self, config: Dict):
        self.config = config
        schedule = config.get('schedule') or {}
        self.videos: List[str] = list(schedule.get('videos') or [])
        self.start_time = self._parse_hhmm(schedule.get('start'))
        self.end_time = self._parse_hhmm(schedule.get('end'))
        self.logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def _parse_hhmm(value: Optional[str]) -> Optional[time]:
        """Parse an 'HH:MM' string; returns None when absent or invalid"""
        if not value:
            return None
        try:
            hours, minutes = str(value).split(':')
            return time(int(hours), int(minutes))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _local_time(dt: datetime) -> time:
        """dt's time-of-day in the system's local timezone

        Naive datetimes are already local and used as-is; aware
        datetimes are converted to local time.
        """
        if dt.tzinfo is None:
            return dt.time()
        return dt.astimezone().time()

    def in_window(self, dt: datetime) -> bool:
        """Whether dt falls inside the schedule's start/end window"""
        if self.start_time is None or self.end_time is None:
            return True
        t = self._local_time(dt)
        if self.start_time <= self.end_time:
            return self.start_time <= t < self.end_time
        # Overnight window: end <= start wraps past midnight
        return t >= self.start_time or t < self.end_time

    def get_current_video(self, dt: datetime, index: int = 0) -> Optional[str]:
        """Video that should be playing at dt, cycling through self.videos by index"""
        if self.in_window(dt) and self.videos:
            return self.videos[index % len(self.videos)]
        return self.config.get('player', {}).get('default_video')

    def next_video(self, dt: datetime, current_video: Optional[str]) -> Optional[str]:
        """The video that follows current_video in the list (wrapping around)"""
        if self.in_window(dt) and self.videos:
            if current_video in self.videos:
                idx = self.videos.index(current_video)
            else:
                idx = len(self.videos) - 1
            return self.videos[(idx + 1) % len(self.videos)]
        return self.config.get('player', {}).get('default_video')
