#!/usr/bin/env python3
"""
VLC Playlist Controller for Raspberry Pi
Based on the requirements in GOALS.md
"""
import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

from glslib import Application
from vlc_player import VlcPlayer
from scheduler import ScheduleManager
from tcp_server import TcpServer
from tcp_client import TcpClient

class VlcPlaylist(Application):
    def __init__(self, description="VLC Playlist Controller"):
        super().__init__(description, debug_level=15)
        print("Initializing VLC Playlist")
        self.vlc_player = VlcPlayer(self.config)
        self.schedule_manager = ScheduleManager(self.config)
        self.running = False
        self.tcp_server = None
        
    def _arg_parse(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add custom arguments for the VLC controller"""
        super()._arg_parse(parser)
        parser.add_argument("--dry-run", action="store_true", help="Evaluate scheduling without actual playback")
        parser.add_argument("--client", action="store_true", help="Run in client mode, connecting to parent server")
        return parser
        
    def _handle_sync_request(self, message, client_socket):
        """Handle sync request from client"""
        timestamp = message.get('timestamp')
        video_position = message.get('video_position')
        
        self.logger.info(f"Received sync request - timestamp: {timestamp}, position: {video_position}")
        
        # In a real implementation, this would seek the currently playing video
        # to the specified position
        response = {
            "command": "sync_ack",
            "timestamp": timestamp,
            "status": "success"
        }
        
        try:
            client_socket.send(json.dumps(response).encode('utf-8'))
        except Exception as e:
            self.logger.error(f"Failed to send sync ack: {e}")
            
    def _handle_client_identify(self, message, client_socket):
        """Handle client identification message"""
        self.logger.info(f"Client identified: {message}")
        
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
        
    def _get_current_schedule_entry(self, dt):
        """Get the current schedule entry based on time"""
        # This is a placeholder - actual implementation will go here
        # based on the scheduling logic from GOALS.md
        return self.config['schedule'][0] if self.config['schedule'] else None
        
    def _select_video(self, dt):
        """Select the appropriate video file based on schedule"""
        entry = self._get_current_schedule_entry(dt)
        if entry:
            return entry.get('video')
        return self.config.get('player', {}).get('default_video')
        
    def _start_server(self):
        """Start the TCP server to accept client connections"""
        server_config = self.config.get('server', {}).get('tcp', {})
        host = server_config.get('host', '0.0.0.0')
        port = server_config.get('port', 8080)
        max_clients = server_config.get('max_clients', 10)
        
        self.tcp_server = TcpServer(host, port, max_clients)
        
        # Register message handlers
        self.tcp_server.register_message_handler('sync', self._handle_sync_request)
        self.tcp_server.register_message_handler('identify', self._handle_client_identify)
        
        # Start the server
        self.tcp_server.start()
        self.logger.info("TCP server started for client connections")
        
    def start(self):
        """Start the playlist controller"""
        print("Starting...")
        self.logger.info("Starting VLC Playlist Controller")
        
        # Validate configuration
        if not self._validate_config():
            self.logger.error("Invalid configuration")
            sys.exit(1)
            
        self.running = True
        
        # Handle client mode
        if self.args.client:
            self.logger.info("Running in client mode")
            if not self._start_client():
                self.logger.error("Failed to start client mode")
                sys.exit(1)
        else:
            # Start TCP server if this is a server instance
            if 'server' in self.config and 'tcp' in self.config['server']:
                self._start_server()
        
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
            
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

def main():
    """Main entry point"""
    controller = VlcPlaylist()
    controller.run()

if __name__ == "__main__":
    main()