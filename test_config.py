#!/usr/bin/env python3
"""
Simple test to verify config loading works
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from application import Application

# Test configuration loading
app = Application()
print("Configuration loaded successfully!")
print(f"Config keys: {list(app.config.keys())}")
if 'player' in app.config:
    print(f"Default video: {app.config.player.default_video}")