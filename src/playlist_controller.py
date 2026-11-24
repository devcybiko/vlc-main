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
from datetime import datetime

from glslib import Application
from vlc_player import VlcPlayer
from scheduler import ScheduleManager
from tcp_server import TcpServer
from tcp_client import TcpClient

class VlcPlaylist(Application):
    def __init__(self):
        super().__init__("VLC Playlist Controller", debug_level=15, config_json="vlc-00.json")
        print("Initializing VLC Playlist")
        self.vlc_player = VlcPlayer(self.config)
        self.schedule_manager = ScheduleManager(self.config)
        self.running = False
        self.tcp_server = None
        self.tcp_client = None
        self.video_index = 0
        self.playing = False
        
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
        required_sections = ['player', 'vlc', 'schedule']
        for section in required_sections:
            if section not in self.config:
                self.logger.error(f"Missing required configuration section: {section}")
                return False

        # Validate the schedule
        schedule = self.config['schedule']
        if not isinstance(schedule, dict):
            self.logger.error("Schedule must be a dict with 'videos', 'start' and 'end'")
            return False
        if not schedule.get('videos'):
            self.logger.error("Schedule must list at least one video")
            return False

        return True

    def _local_now(self):
        """Current time in the configured location timezone"""
        return datetime.now(self.schedule_manager.tz)

    def _start_video_by_name(self, video_file):
        """Start a video and track playback state; returns True on success"""
        if self.vlc_player.start_video(video_file):
            self.playing = True
            return True
        self.logger.error(f"Failed to start video: {video_file}")
        return False

    def _start_initial_video(self):
        """Start playback with the video that should be playing right now"""
        video_file = self.schedule_manager.get_current_video(self._local_now(), self.video_index)
        if not video_file:
            self.logger.warn("No video selected - check configuration")
            return
        self.logger.info(f"Starting with video: {video_file}")
        self._start_video_by_name(video_file)

    def _advance_video(self):
        """Advance to the next scheduled video after one ends"""
        if self.schedule_manager.videos:
            self.video_index = (self.video_index + 1) % len(self.schedule_manager.videos)
        video_file = self.schedule_manager.get_current_video(self._local_now(), self.video_index)
        if not video_file:
            self.logger.warn("No video selected - check configuration")
            return
        self.logger.info(f"Starting next video: {video_file}")
        self._start_video_by_name(video_file)

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
        
    def _start_client(self):
        """Start the TCP client to connect to the parent server"""
        client_config = self.config.get('client', {}).get('tcp', {})
        host = client_config.get('host', '192.168.1.100')
        port = client_config.get('port', 8080)
        
        self.tcp_client = TcpClient(host, port)
        
        if not self.tcp_client.run():
            self.tcp_client = None
            return False
        
        self.logger.info("TCP client started for parent server connection")
        return True
        
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
        if self.config.get('dry_run'):
            self.logger.info("Dry run mode - evaluating schedule without playback")
        else:
            self._start_initial_video()
            
    def run(self):
        """Main execution loop"""
        self.start()
        
        try:
            while self.running:
                if not self.config.get('dry_run'):
                    if self.playing and not self.vlc_player.is_running():
                        # The current video ended - start the next one
                        self._advance_video()
                    elif not self.playing:
                        # Nothing playing (initial start or a failed start)
                        self._start_initial_video()
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        finally:
            self.stop()
            
    def stop(self):
        """Stop the controller and clean up VLC and network resources"""
        self.running = False
        
        try:
            self.vlc_player.stop_video()
        except Exception as e:
            self.logger.error(f"Error stopping VLC player: {e}")
            
        if self.tcp_server is not None:
            try:
                self.tcp_server.stop()
            except Exception as e:
                self.logger.error(f"Error stopping TCP server: {e}")
                
        if self.tcp_client is not None:
            try:
                self.tcp_client.disconnect()
            except Exception as e:
                self.logger.error(f"Error stopping TCP client: {e}")
                
        self.logger.info("VLC Playlist Controller stopped")
        
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