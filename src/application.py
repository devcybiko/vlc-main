#!/usr/bin/env python3
"""
Simple Application base class for VLC Playlist Controller
"""
import argparse
import json
import logging
import os
from munch import DefaultMunch

class Application:
    def __init__(self, description="VLC Playlist Controller"):
        self._arg_parser = argparse.ArgumentParser(description=description)
        self._arg_parse(self._arg_parser)
        self.args = self._arg_parser.parse_args()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = self._config_load()

    def _arg_parse(self, parser):
        parser.add_argument("--config", default="~/vlc-main/config.json",
                          help="Path to configuration file (default: ~/vlc-main/config.json)")
        parser.add_argument("--debug", action="store_true", help="Enable debug mode")
        return parser

    def _config_load(self) -> DefaultMunch:
        """
        Load configuration from JSON files.
        """
        config = DefaultMunch()
        
        # Get config path from args or use default
        config_path = getattr(self.args, 'config', '~/vlc-main/config.json')
        
        # Expand user path
        config_path = os.path.expanduser(config_path)
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    json_config = json.load(f)
                    config.update(DefaultMunch.fromDict(json_config))
            else:
                self.logger.warning(f"Config file not found: {config_path}")
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            
        return config

    def go(self):
        print("Running the application...")