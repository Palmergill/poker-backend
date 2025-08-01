# Poker App Tests

This directory contains all tests for the poker application, organized by category.

## Directory Structure

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Shared test configuration
├── README.md                   # This file
├── unit/                       # Unit tests
│   ├── __init__.py
│   ├── test_models.py          # Django model tests
│   ├── test_redis.py           # Redis connection tests
│   ├── test_standalone.py      # Standalone utility tests
│   └── test_with_sqlite.py     # SQLite-specific tests
├── integration/                # Integration tests
│   ├── __init__.py
│   ├── test_complete_flow.py   # Full game flow tests
│   ├── test_betting_round.py   # Betting round logic tests
│   ├── test_hand_history_complete.py  # Hand history integration
│   ├── test_second_hand.py     # Multi-hand scenarios
│   ├── test_actual_second_hand.py     # Second hand edge cases
│   ├── test_flop_checking.py   # Post-flop checking tests
│   ├── test_edge_case.py       # Edge case scenarios
│   ├── test_big_blind_option.py       # Big blind option tests
│   ├── test_fix_verification.py       # Fix verification tests
│   ├── test_console_logging.py        # Console logging tests
│   └── test_full_hand_logging.py      # Full hand logging tests
├── api/                        # API endpoint tests
│   ├── __init__.py
│   ├── test_api_direct.py      # Direct API tests
│   └── test_hand_history_api.py       # Hand history API tests
├── websocket/                  # WebSocket tests
│   ├── __init__.py
│   ├── test_websockets.py      # WebSocket functionality tests
│   └── test_websocket_fix.py   # WebSocket fix verification
├── frontend/                   # Frontend-related tests
│   ├── __init__.py
│   └── test_frontend_logging.py       # Frontend logging tests
└── browser/                    # Browser integration tests
    ├── __init__.py
    └── test_three_player_game.py      # 3-player game flow test
```

## Running Tests

### Run All Tests
```bash
python run_tests.py
```

### Run Tests by Category
```bash
# Unit tests only
python run_tests.py --category unit

# Integration tests only
python run_tests.py --category integration

# API tests only
python run_tests.py --category api

# WebSocket tests only
python run_tests.py --category websockets

# Frontend tests only
python run_tests.py --category frontend

# Browser integration tests only
python run_tests.py --category browser
```

### Run with Coverage
```bash
python run_tests.py --coverage
```

### Run Individual Test Files
```bash
# Run a specific test file
python tests/unit/test_models.py

# Run from the tests directory
cd tests/integration
python test_complete_flow.py
```

### Django Test Runner
```bash
# Run using Django's test runner
python manage.py test tests

# Run specific test module
python manage.py test tests.unit.test_models

# Run with verbosity
python manage.py test tests --verbosity=2
```

## Test Categories

### Unit Tests
- Test individual components in isolation
- Fast execution
- No external dependencies (database, Redis, etc.)
- Mock external services

### Integration Tests
- Test complete workflows and interactions
- Test multiple components working together
- Use real database and services
- Test game logic and business rules

### API Tests
- Test REST API endpoints
- Test authentication and authorization
- Test request/response formats
- Test error handling

### WebSocket Tests
- Test real-time communication
- Test WebSocket connection management
- Test game state broadcasting
- Test authentication over WebSocket

### Frontend Tests
- Test frontend integration points
- Test logging and debugging features
- Test user interface workflows

### Browser Tests
- Full end-to-end browser automation using Selenium
- Test complete user workflows across multiple users
- Test real browser interactions and UI flows
- Test game creation, joining, playing, and cash out flows

## Writing New Tests

### Test File Naming
- Unit tests: `test_<component>.py`
- Integration tests: `test_<workflow>.py`
- API tests: `test_<api_feature>.py`
- WebSocket tests: `test_<websocket_feature>.py`

### Test Structure
```python
#!/usr/bin/env python3
"""
Description of what this test file tests.
"""

import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent  # Adjust based on depth
sys.path.insert(0, str(PROJECT_ROOT))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_project.settings')
django.setup()

# Your imports here
from django.test import TestCase
from poker_api.models import Game

class YourTestCase(TestCase):
    def test_something(self):
        # Your test code here
        pass

if __name__ == '__main__':
    # Run this test file directly
    unittest.main()
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure Django is set up before importing models
2. **Database Issues**: Use test database settings for tests
3. **Path Issues**: Use relative paths from project root
4. **Redis Issues**: Tests may need Redis running for WebSocket tests

### Test Database
Tests use a separate test database. If you encounter database issues:
```bash
python manage.py migrate --settings=poker_project.test_settings
```

### Environment Variables
Some tests may require specific environment variables:
```bash
export DJANGO_SETTINGS_MODULE=poker_project.settings
```