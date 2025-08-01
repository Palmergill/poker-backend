#!/usr/bin/env python
"""
Quick test runner using SQLite instead of PostgreSQL.
"""

import os
import sys
import django
from pathlib import Path
from django.conf import settings
from django.test.utils import get_runner

# Set up test environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_project.test_settings')
django.setup()

if __name__ == '__main__':
    print("🃏 Running poker tests with SQLite...")
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2)
    
    if len(sys.argv) > 1:
        # Run specific tests if provided
        test_labels = sys.argv[1:]
    else:
        # Run all poker_api tests
        test_labels = ['poker_api']
    
    failures = test_runner.run_tests(test_labels)
    
    if failures == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ {failures} test(s) failed!")
    
    sys.exit(failures)