#!/usr/bin/env python3
"""
Comprehensive test runner for VLC Playlist Controller
"""
import unittest
import sys
import os

def run_all_tests():
    """Run all unit tests"""
    # Add src to path so we can import our modules
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))
    
    # Discover and run all tests
    loader = unittest.TestLoader()
    start_dir = os.path.join(os.path.dirname(__file__))
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)