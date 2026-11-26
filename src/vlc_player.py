#!/usr/bin/env python3
"""
VLC Player management for the playlist controller
"""
import logging
import os
import socket
import subprocess
from typing import Dict, List, Optional

class VlcPlayer:
    # VLC remote-control (rc) TCP interface, used by clients to sample and
    # set the playback position without restarting VLC.
    RC_HOST = '0.0.0.0'
    RC_PORT = 1127
    RC_TIMEOUT_SECS = 2.0

    def __init__(self, config: Dict):
        self.config = config
        self.process = None
        self.current_video = None
        self.logger = logging.getLogger(self.__class__.__name__)
        # Extra VLC options appended at launch (e.g. the rc interface on
        # clients). Empty by default so the server VLC is unaffected.
        self.extra_options: List[str] = []
        self.rc_host = self.RC_HOST
        self.rc_port = self.RC_PORT
        self.rc_timeout = self.RC_TIMEOUT_SECS

    @staticmethod
    def client_options() -> List[str]:
        """VLC options that enable the rc TCP interface for clients"""
        return [
            '--extraintf=rc',
            f'--rc-host={VlcPlayer.RC_HOST}:VlcPlayer.RC_PORT',
        ]

    def start_video(self, video_path: str, start_time: float = 0.0) -> bool:
        """Start playing a video with VLC, optionally from a timestamp

        Raises:
            FileNotFoundError: if video_path does not exist

        Relative paths are resolved against config['player']['video_directory'].
        """
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
        
        try:
            print(f"Starting VLC with command: {' '.join(cmd)}")
            self.process = subprocess.Popen(cmd)
            self.current_video = video_path
            return True
        except Exception as e:
            self.logger.error(f"Failed to start VLC: {e}")
            return False
            
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
        
    def _rc_command(self, command: str) -> Optional[str]:
        """Send one command to VLC's rc TCP interface

        Returns the last non-empty response line, or None if VLC is not
        reachable (no connection, timeout, or empty reply).
        """
        print("rc cmd:", command)
        try:
            with socket.create_connection(
                (self.rc_host, self.rc_port), timeout=self.rc_timeout
            ) as sock:
                sock.sendall((command + '\n').encode('utf-8'))
                data = sock.recv(4096).decode('utf-8', errors='replace')
        except (OSError, socket.timeout) as e:
            self.logger.error(f"rc interface unavailable: {e}")
            return None
        lines = [line.strip() for line in data.splitlines() if line.strip()]
        print("rc:", lines)
        return lines[-1] if lines else None

    def get_time(self) -> Optional[float]:
        """Current playback position in seconds, sampled from VLC's rc
        interface. Returns None if VLC is not reachable or not reporting
        a position.
        """
        response = self._rc_command('get_time')
        if response is None:
            return None
        return self._parse_time(response)

    @staticmethod
    def _parse_time(text: str) -> Optional[float]:
        """Parse a VLC rc time reply: plain seconds ("45", "45.5") or
        colon-separated "H:MM:SS.fff" / "MM:SS.fff".
        """
        text = text.strip().strip('"')
        if not text:
            return None

        def _num(part: str) -> Optional[float]:
            part = part.strip()
            if part.count('.') > 1 or not part.replace('.', '', 1).isdigit():
                return None
            return float(part)

        if ':' not in text:
            return _num(text)
        parts = text.split(':')
        if len(parts) > 3:
            return None
        total = 0.0
        for part in parts:
            value = _num(part)
            if value is None:
                return None
            total = total * 60 + value
        return total

    def seek_to(self, seconds: float) -> bool:
        """Seek the currently playing video to a timestamp

        Prefers VLC's rc TCP interface ('seek' command), which is instant.
        Falls back to restarting the current video with --start-time when
        the rc interface is unavailable.
        """
        video_path = self.current_video
        if not video_path:
            self.logger.error("Cannot seek: no video is playing")
            return False

        if self._rc_command(f'seek {int(round(seconds))}') is not None:
            return True

        self.stop_video()
        return self.start_video(video_path, start_time=seconds)

    def is_running(self) -> bool:
        """Check if VLC process is running"""
        return self.process is not None and self.process.poll() is None