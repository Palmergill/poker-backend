#!/usr/bin/env python
"""
Test runner script for the poker application.

This script provides various options for running tests:
- All tests
- Specific test categories
- With coverage reporting
- With verbose output
"""

import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner
import subprocess


def setup_django():
    """Set up Django environment for testing."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_project.test_settings')
    django.setup()


def run_all_tests(verbosity=1, coverage=False):
    """Run all tests."""
    print("🃏 Running all poker application tests...")
    
    if coverage:
        print("📊 Running with coverage reporting...")
        cmd = [
            'coverage', 'run', '--source=.', '--omit=*/migrations/*,*/venv/*,*/poker-frontend/*',
            'manage.py', 'test', 'poker_api', f'--verbosity={verbosity}'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ All tests passed!")
            print("\n📊 Coverage Report:")
            subprocess.run(['coverage', 'report'])
            subprocess.run(['coverage', 'html'])
            print("📁 HTML coverage report generated in htmlcov/")
        else:
            print("❌ Some tests failed!")
            print(result.stdout)
            print(result.stderr)
        
        return result.returncode == 0
    else:
        TestRunner = get_runner(settings)
        test_runner = TestRunner(verbosity=verbosity)
        failures = test_runner.run_tests(['tests'])
        
        if failures == 0:
            print("✅ All tests passed!")
            return True
        else:
            print(f"❌ {failures} test(s) failed!")
            return False


def run_category_tests(category, verbosity=1):
    """Run tests for a specific category."""
    test_map = {
        'models': 'tests.unit.test_models',
        'unit': 'tests.unit',
        'integration': 'tests.integration',
        'api': 'tests.api',
        'websockets': 'tests.websocket',
        'frontend': 'tests.frontend',
        'browser': 'tests.browser',
    }
    
    if category not in test_map:
        print(f"❌ Unknown category: {category}")
        print(f"Available categories: {', '.join(test_map.keys())}")
        return False
    
    print(f"🃏 Running {category} tests...")
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=verbosity)
    failures = test_runner.run_tests([test_map[category]])
    
    if failures == 0:
        print(f"✅ {category} tests passed!")
        return True
    else:
        print(f"❌ {failures} {category} test(s) failed!")
        return False


def run_quick_tests():
    """Run a quick subset of critical tests."""
    print("🚀 Running quick test suite...")
    
    critical_tests = [
        'tests.unit.test_models.ModelTestCase.test_poker_table_creation',
        'tests.unit.test_models.CardUtilsTestCase.test_card_creation',
        'tests.unit.test_models.HandEvaluatorTestCase.test_royal_flush',
        'tests.unit.test_models.GameServiceTestCase.test_create_game',
        'tests.unit.test_models.APITestCase.test_register_user_endpoint',
    ]
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=1)
    failures = test_runner.run_tests(critical_tests)
    
    if failures == 0:
        print("✅ Quick tests passed!")
        return True
    else:
        print(f"❌ {failures} quick test(s) failed!")
        return False


def check_test_database():
    """Check if test database can be created."""
    try:
        from django.db import connection
        from django.core.management import call_command
        
        print("🔍 Checking test database setup...")
        # This will create and destroy a test database
        call_command('check', '--database', 'default')
        print("✅ Test database setup is OK")
        return True
    except Exception as e:
        print(f"❌ Test database setup failed: {e}")
        return False


def main():
    """Main test runner function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run poker application tests')
    parser.add_argument(
        '--category', 
        choices=['models', 'unit', 'integration', 'api', 'websockets', 'frontend', 'browser'],
        help='Run tests for specific category only'
    )
    parser.add_argument(
        '--quick', 
        action='store_true',
        help='Run quick subset of critical tests'
    )
    parser.add_argument(
        '--coverage', 
        action='store_true',
        help='Run with coverage reporting'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose test output'
    )
    parser.add_argument(
        '--check-db',
        action='store_true',
        help='Check test database setup'
    )
    
    args = parser.parse_args()
    
    # Set up Django
    setup_django()
    
    verbosity = 2 if args.verbose else 1
    
    if args.check_db:
        return 0 if check_test_database() else 1
    
    if args.quick:
        success = run_quick_tests()
    elif args.category:
        success = run_category_tests(args.category, verbosity)
    else:
        success = run_all_tests(verbosity, args.coverage)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())