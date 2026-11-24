#!/usr/bin/env python3
"""
VLC Player management for the playlist controller
"""
import logging
import os
import subprocess
from typing import Dict, Optional

class VlcPlayer:
    def __init__(self, config: Dict):
        self.config = config
        self.process = None
        self.current_video = None
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def start_video(self, video_path: str) -> bool:
        """Start playing a video with VLC

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
            
        # Add video file
        cmd.append(video_path)
        
        try:
            self.logger.info(f"Starting VLC with command: {' '.join(cmd)}")
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
        
    def is_running(self) -> bool:
        """Check if VLC process is running"""
        return self.process is not None and self.process.poll() is None