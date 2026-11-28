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
from datetime import datetime

from glslib import Application
from vlc_player import VlcPlayer
from scheduler import ScheduleManager
from tcp_server import TcpServer
from tcp_client import TcpClient

class VlcPlaylist(Application):
    def __init__(self):
        super().__init__("VLC Playlist Controller", debug_level=15, config_json="vlc-main.json")
        print("Initializing VLC Playlist")
        self.vlc_player = VlcPlayer(self.config)
        self.schedule_manager = ScheduleManager(self.config)
        self.running = False
        self.tcp_server = None
        self.tcp_client = None
        self.video_index = 0
        self.playing = False
        self._video_start_time: float | None = None
        self._last_sync_time: float | None = None
        # Maximum drift (seconds) between the client's actual position and
        # the sync target before the client resyncs.
        self.sync_delta = float(self.config.schedule.sync_delta)
        
    def _arg_parse(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add custom arguments for the VLC controller"""
        super()._arg_parse(parser)
        parser.add_argument("--dry-run", action="store_true", help="Evaluate scheduling without actual playback")
        parser.add_argument("--client", action="store_true", help="Run in client mode, connecting to parent server")
        return parser
        
    def _handle_client_identify(self, args, client_socket):
        """Handle "identify <client-id>" from a newly connected client"""
        self.logger.info(f"Client identified: {args}")

    def _handle_sync_command(self, args):
        """Handle "sync <video-name> <secs.nn>" from the parent server

        If the named video is different from the one currently playing, stop
        the current video and start the named one at the given timestamp.
        If it is the same video, seek it to the given timestamp.
        """
        if len(args) != 2:
            self.logger.warn(f"Malformed sync command: {args}")
            return
        video_name, secs_text = args
        try:
            secs = float(secs_text) + 1
        except ValueError:
            self.logger.warn(f"Malformed sync timestamp: {secs_text}")
            return

        self.logger.info(f"Sync command: {video_name} at {secs}s")
        current = self.vlc_player.current_video
        if current and os.path.basename(current) == video_name:
            # Same video - only disturb playback if we're actually out of sync
            position = self.vlc_player.get_time()
            if position is None:
                # rc interface unreachable - fall back to a hard resync
                self.logger.warn(
                    f"Cannot sample position via rc; resyncing {video_name} to {secs:.2f}s"
                )
            elif abs(position - secs) <= self.sync_delta:
                self.logger.info(
                    f"In sync for {video_name} "
                    f"(local {position:.2f}s, target {secs:.2f}s, "
                    f"drift {abs(position - secs):.2f}s <= {self.sync_delta:.2f}s)"
                )
                self.playing = True
                self._last_sync_time = time.time()
                return
            else:
                self.logger.info(
                    f"Resyncing {video_name}: local {position:.2f}s, "
                    f"target {secs:.2f}s (drift > {self.sync_delta:.2f}s)"
                )
            if not self.vlc_player.seek_to(secs):
                self.logger.error(f"Failed to seek {video_name} to {secs}s")
                return
            self.playing = True
            self._video_start_time = time.time()
            self._last_sync_time = time.time()
            return

        # Different video (or nothing playing) - stop and start the named video
        self.vlc_player.stop_video()
        self.playing = False
        self._start_video_by_name(video_name, start_time=secs)
        
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
        """Current time in the system's local timezone"""
        return datetime.now().astimezone()

    def _start_video_by_name(self, video_file, start_time: float = 0.0):
        """Start a video and track playback state; returns True on success"""
        if self.vlc_player.start_video(video_file, start_time=start_time):
            self.playing = True
            self._video_start_time = time.time()
            self._last_sync_time = time.time()
            self._broadcast_sync(0.0)
            return True
        self.logger.error(f"Failed to start video: {video_file}")
        return False

    def _broadcast_sync(self, secs: float):
        """Send "sync <video name> <secs.nn>" to all connected clients"""
        print(f"Broadcasting sync: {secs}")
        if self.tcp_server is None:
            return
        video = self.vlc_player.current_video
        if not video:
            return
        label = "0.0" if secs == 0.0 else f"{secs:.2f}"
        self.tcp_server.broadcast(f"sync {os.path.basename(video)} {label}")

    def _send_periodic_sync(self):
        """Broadcast the current video position every schedule.sync_secs"""
        if self.tcp_server is None or not self.playing:
            return
        if self._video_start_time is None or self._last_sync_time is None:
            return
        sync_secs = self.config.get('schedule', {}).get('sync_secs', 0)
        if not sync_secs:
            return
        now = time.time()
        if now - self._last_sync_time >= sync_secs:
            self._last_sync_time = now
            curr_time = self.vlc_player.get_time()
            if curr_time is None:
                return
            self._broadcast_sync(curr_time)

    def _start_initial_video(self):
        """Start playback with the video that should be playing right now"""
        video_file = self.schedule_manager.get_current_video(self._local_now(), self.video_index)
        if not video_file:
            self.logger.warn("No video selected - check configuration")
            return
        self.logger.info(f"Starting with video: {video_file}")
        self._start_video_by_name(video_file)

    def _is_playing_scheduled(self) -> bool:
        """Whether the currently playing file is one of the scheduled videos"""
        current = self.vlc_player.current_video
        if not current:
            return False
        return os.path.basename(current) in self.schedule_manager.videos

    def _check_window_boundary(self):
        """Switch playback when we cross the schedule window boundary

        At the end time the scheduled loop stops and the default video
        plays again; at the start time the scheduled videos resume.
        """
        if self.schedule_manager.in_window(self._local_now()):
            if not self._is_playing_scheduled():
                self.logger.info("Schedule window opened - switching to scheduled video")
                self.vlc_player.stop_video()
                self.playing = False
        elif self._is_playing_scheduled():
            self.logger.info("Schedule window ended - switching to default video")
            self.vlc_player.stop_video()
            self.playing = False

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
        # The config's server.tcp.host is the address clients use to reach
        # this server. The server itself binds to all interfaces unless
        # bind_host is set explicitly.
        bind_host = server_config.get('bind_host', '0.0.0.0')
        port = server_config.get('port', 8080)
        max_clients = server_config.get('max_clients', 10)

        self.tcp_server = TcpServer(bind_host, port, max_clients)
        
        # Register message handlers
        self.tcp_server.register_message_handler('identify', self._handle_client_identify)
        
        # Start the server
        self.tcp_server.start()
        self.logger.info("TCP server started for client connections")
        
    def _start_client(self):
        """Start the TCP client to connect to the parent server

        Server host/port come from server.tcp in the config file.
        """
        server_tcp = self.config.get('server', {}).get('tcp', {})
        host = server_tcp.get('host', '127.0.0.1')
        port = server_tcp.get('port', 8080)

        self.tcp_client = TcpClient(host, port)
        self.tcp_client.register_message_handler('sync', self._handle_sync_command)
        
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
            server_config = self.config.get('server')
            if isinstance(server_config, dict) and 'tcp' in server_config:
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
                    else:
                        # Video still running - check for window boundary crossings
                        self._check_window_boundary()
                    self._send_periodic_sync()
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