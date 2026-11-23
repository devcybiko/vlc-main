#!/usr/bin/env python3
"""
VLC Playlist Controller for Raspberry Pi
Based on the requirements in GOALS.md
"""
import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

from glslib import Application
from vlc_player import VlcPlayer
from scheduler import ScheduleManager

class VlcPlaylist(Application):
    def __init__(self, description="VLC Playlist Controller"):
        super().__init__(description)
        self.vlc_player = VlcPlayer(self.config)
        self.schedule_manager = ScheduleManager(self.config)
        self.running = False
        
    def _arg_parse(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add custom arguments for the VLC controller"""
        parser.add_argument("--dry-run", action="store_true", help="Evaluate scheduling without actual playback")
        return parser
        
    def _validate_config(self) -> bool:
        """Validate the configuration"""
        required_sections = ['player', 'location', 'vlc', 'schedule']
        for section in required_sections:
            if section not in self.config:
                self.logger.error(f"Missing required configuration section: {section}")
                return False
                
        # Validate location
        location = self.config['location']
        if 'latitude' not in location or 'longitude' not in location:
            self.logger.error("Location must include latitude and longitude")
            return False
            
        # Validate schedule entries
        for i, entry in enumerate(self.config['schedule']):
            if 'video' not in entry:
                self.logger.error(f"Schedule entry {i} missing video file")
                return False
                
        return True
        
    def _get_current_schedule_entry(self, dt: datetime) -> dict:
        """Get the current schedule entry based on time"""
        # This is a placeholder - actual implementation will go here
        # based on the scheduling logic from GOALS.md
        return self.config['schedule'][0] if self.config['schedule'] else None
        
    def _select_video(self, dt: datetime) -> str:
        """Select the appropriate video file based on schedule"""
        entry = self._get_current_schedule_entry(dt)
        if entry:
            return entry.get('video')
        return self.config.get('player', {}).get('default_video')
        
    def start(self):
        """Start the playlist controller"""
        self.logger.info("Starting VLC Playlist Controller")
        
        # Validate configuration
        if not self._validate_config():
            self.logger.error("Invalid configuration")
            sys.exit(1)
            
        self.running = True
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Initial video selection and playback
        now = datetime.now(timezone.utc)
        video_file = self._select_video(now)
        
        if not self.config.get('dry_run'):
            if video_file:
                self.logger.info(f"Starting with video: {video_file}")
                self.vlc_player.start_video(video_file)
            else:
                self.logger.warning("No video selected - check configuration")
        else:
            self.logger.info("Dry run mode - evaluating schedule without playback")
            
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        
    def stop(self):
        """Stop the playlist controller gracefully"""
        if not self.running:
            return
            
        self.running = False
        self.logger.info("Stopping VLC Playlist Controller")
        self.vlc_player.stop_video()
        
    def run(self):
        """Main execution loop"""
        self.start()
        
        try:
            while self.running:
                # In a real implementation, this would check for schedule changes
                # and manage video transitions
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        finally:
            self.stop()

def main():
    """Main entry point"""
    controller = VlcPlaylist()
    controller.run()

if __name__ == "__main__":
    main()