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

class VlcTelnet:
    def __init__(self, host, port, password):
        self.TELNET_HOST = host
        self.TELNET_PORT = port
        self.TELNET_PASSWORD = password
        self.logger = logging.getLogger(self.__class__.__name__)

    def connect(self):
        for tries in range(5):
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.TELNET_HOST, self.TELNET_PORT))
                self.buffer = ""
                self.read_until("\nPassword: ")
                self.send(f"{self.TELNET_PASSWORD}\n")
                return
            except Exception:
                self.logger.warning(f"Connection failed: {tries+1} times... retrying")
                sleep(1)
        raise ConnectionError("Failed to connect to VLC.")

    def read_until(self, terminator):
        """Reads stream bytes non-blockingly until terminator is found."""
        while terminator not in self.buffer:
            data = self.sock.recv(4096).decode('utf-8', errors='ignore')
            if not data:
                raise ConnectionError("VLC disconnected.")
            self.buffer += data
        
        # Split out the requested data chunk up to the terminator
        line, _, self.buffer = self.buffer.partition(terminator)
        return line

    def send(self, cmd, prompt="> "):
        self.logger.warning(f"Sending: {cmd}")
        self.sock.sendall(f"{cmd}\n".encode())
        response = self.read_until(prompt)
        return response


class VlcPlayer:
    TELNET_HOST = "127.0.0.1"
    TELNET_PORT = 1127
    TELNET_PASSWORD="password"

    def __init__(self, config: Dict):
        self.config = config
        self.process = None
        self.current_video = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.sock = None
        self.buffer = ""
        # run "killall vlc" to stop any existing instances
        subprocess.run(["killall", "vlc"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def _telnet_options() -> List[str]:
        """VLC options that enable the rc TCP interface for clients"""
        return [
            f'--extraintf=telnet',
            f'--telnet-host=127.0.0.1',
            f'--telnet-port={VlcPlayer.TELNET_PORT}',
            f'--telnet-password={VlcPlayer.TELNET_PASSWORD}',
        ]

    def start_video(self, video_path: str, start_time: float = 0.0) -> bool:
        """Start playing a video with VLC, optionally from a timestamp

        Raises:
            FileNotFoundError: if video_path does not exist

        Relative paths are resolved against config['player']['video_directory'].
        """
        self.logger.warning(f"Starting video: {video_path}")
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
        cmd.extend(self._telnet_options())
        if start_time > 0:
            cmd.append(f"--start-time={start_time:.3f}")

        # Add video file
        cmd.append(video_path)
        
        self.logger.warning(f"Starting VLC with command: {' '.join(cmd)}")
        self.process = subprocess.Popen(cmd)
        self.current_video = video_path
        self.telnet = VlcTelnet(self.TELNET_HOST, self.TELNET_PORT, self.TELNET_PASSWORD)
        self.telnet.connect()
        return True
            
    def stop_video(self) -> bool:
        """Stop the currently playing video"""
        self.logger.warning("Stopping video")
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
        response = self.telnet.send("get_time")
        got_time = 0
        # Parse out just the number
        lines = [l.strip() for l in response.splitlines() if l.strip()]
        for line in lines:
            if line.isdigit():
                got_time = int(line)
        print(f"Got time: {got_time}")
        return got_time

    def seek_to(self, seconds):
        self.telnet.send(f"seek {int(seconds)}")
        sleep(0.1)
        return self.get_time()

    def is_running(self) -> bool:
        """Check if VLC process is running"""
        return self.process is not None and self.process.poll() is None