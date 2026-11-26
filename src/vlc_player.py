#!/usr/bin/env python3
"""
VLC Player management for the playlist controller
"""
import logging
import os
import socket
import subprocess
from time import sleep
from typing import Dict, List, Optional

class VlcPlayer:
    # VLC remote-control (rc) TCP interface, used by clients to sample and
    # set the playback position without restarting VLC.
    RC_HOST = '0.0.0.0'
    RC_PORT = 1127
    RC_TIMEOUT_SECS = 2.0
    RC_PASSWORD="password"

    def __init__(self, config: Dict):
        self.config = config
        self.process = None
        self.current_video = None
        self.logger = logging.getLogger(self.__class__.__name__)
        # Extra VLC options appended at launch (e.g. the rc interface on
        # clients). Empty by default so the server VLC is unaffected.
        self.extra_options: List[str] = []
        self.sock = None

    def _read_until(self, terminator):
        """Reads stream bytes non-blockingly until terminator is found."""
        while terminator not in self.buffer:
            data = self.sock.recv(4096).decode('utf-8', errors='ignore')
            if not data:
                raise ConnectionError("VLC disconnected.")
            print("data", data)
            self.buffer += data
        
        # Split out the requested data chunk up to the terminator
        line, _, self.buffer = self.buffer.partition(terminator)
        return line

    def _connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(("127.0.0.1", self.RC_PORT))
        self.buffer = ""
        self._read_until("\nPassword: ")
        self.sock.sendall(f"{self.RC_PASSWORD}\n".encode())
        self._read_until("> ") # Clear the welcome prompt

    @staticmethod
    def client_options() -> List[str]:
        """VLC options that enable the rc TCP interface for clients"""
        return [
            f'--extraintf=telnet',
            f'--telnet-host=0.0.0.0',
            f'--telnet-port={VlcPlayer.RC_PORT}',
            f'--telnet-password={VlcPlayer.RC_PASSWORD}',
        ]

    def start_video(self, video_path: str, start_time: float = 0.0) -> bool:
        """Start playing a video with VLC, optionally from a timestamp

        Raises:
            FileNotFoundError: if video_path does not exist

        Relative paths are resolved against config['player']['video_directory'].
        """
        self.stop_video() # stop it if it's already running
        if not os.path.isabs(video_path):
            video_dir = self.config.get('player', {}).get('video_directory', '')
            if video_dir:
                video_path = os.path.join(video_dir, video_path)
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Build VLC command from config
        vlc_config = self.config.get('vlc', {})
        cmd = [vlc_config.get('executable', 'cvlc')]
        cmd.extend(vlc_config.get('options', []))
        cmd.extend(self.extra_options)
        if start_time > 0:
            cmd.append(f"--start-time={start_time:.3f}")

        # Add video file
        cmd.append(video_path)
        
        print(f"Starting VLC with command: {' '.join(cmd)}")
        self.process = subprocess.Popen(cmd)
        self.current_video = video_path
        self._connect()
        return True
            
    def stop_video(self) -> bool:
        """Stop the currently playing video"""
        if self.process and self.process.poll() is None:
            try:
                # Try graceful shutdown first
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate gracefully
                self.process.kill()
                self.process.wait()
            except Exception as e:
                self.logger.error(f"Error stopping VLC: {e}")
                
        self.process = None
        self.current_video = None
        return True
        
    def get_time(self):
        """Instantly samples the video timestamp."""
        self.sock.sendall(b"get_time\n")
        # Telnet echoes back 'get_time\r\n<timestamp>\r\n> '
        response = self._read_until("> ")
        
        # Parse out just the number
        lines = [l.strip() for l in response.splitlines() if l.strip()]
        for line in lines:
            print("line:", line)
            if line.isdigit():
                return int(line)
        return 0

    def seek_to(self, seconds):
        """Instantly seeks to a specific timestamp."""
        self.sock.sendall(f"seek {seconds}\n".encode())
        self._read_until("> ") # Clear buffer up to next prompt

    def is_running(self) -> bool:
        """Check if VLC process is running"""
        return self.process is not None and self.process.poll() is None