# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django-based Texas Hold'em poker backend with WebSocket support for real-time multiplayer gameplay. The application uses Django REST Framework for API endpoints and Django Channels for WebSocket connections.

## Development Commands

### Database Operations
- `python manage.py migrate` - Apply database migrations
- `python manage.py makemigrations` - Create new migrations after model changes
- `python manage.py createsuperuser` - Create admin user
- `python manage.py create_test_table` - Custom command to create test poker table

### Running the Application
- `python manage.py runserver` - Start development server (default: localhost:8000)
- `python manage.py runserver 0.0.0.0:8000` - Run server accessible on network

### Testing
- `python run_tests.py` - Run all tests with custom test runner
- `python run_tests.py --quick` - Run critical test subset
- `python run_tests.py --category unit` - Run specific test category (unit/integration/api/websocket/browser/frontend)
- `python run_tests.py --coverage` - Run tests with coverage reporting
- `python run_tests.py --verbose` - Verbose test output
- `pytest` - Alternative test runner (configured in pytest.ini)
- `pytest -m "not slow"` - Run tests excluding slow markers

### Test Categories
- `unit` - Unit tests for models, utilities
- `integration` - Integration tests for game flow
- `api` - API endpoint tests
- `websocket` - WebSocket functionality tests  
- `browser` - Browser-based end-to-end tests using Selenium
- `frontend` - Frontend integration tests

## Architecture

### Core Applications
- `poker_api/` - Main Django app containing all poker logic
- `poker_project/` - Django project configuration with environment-specific settings

### Settings Structure
The project uses environment-specific settings in `poker_project/settings/`:
- `base.py` - Common settings
- `development.py` - Local development
- `production.py` - Production deployment  
- `railway.py` - Railway deployment
- `test_settings.py` - Test configuration

Environment detection is handled in `manage.py` - Railway environment automatically uses railway settings.

### Key Models (poker_api/models.py)
- `PokerTable` - Poker table configuration (blinds, buy-ins, max players)
- `Player` - Player profiles linked to Django User (includes bot players)
- `Game` - Individual poker game instances with state management
- `PlayerGame` - Player participation in specific games (chips, position, etc.)
- `GameAction` - Individual player actions (bet, call, fold, etc.)
- `HandHistory` - Complete game history for analysis

### Business Logic Structure
- `services/game_service.py` - Core game state management
- `utils/game_manager.py` - Game flow orchestration
- `utils/hand_evaluator.py` - Poker hand ranking logic
- `utils/card_utils.py` - Card and deck utilities
- `utils/bot_engine.py` - AI bot decision-making logic
- `consumers.py` - WebSocket message handling for real-time updates

### WebSocket Architecture
Real-time updates are handled through Django Channels:
- Game state changes broadcast to all players at table
- Individual player actions trigger state updates
- Connection endpoint: `ws://localhost:8000/ws/game/{game_id}/`

### Bot Integration
The system supports AI bot players:
- Bot players are created as Django Users with `is_bot=True` flag
- Bot decision-making is handled in `utils/bot_engine.py`
- Bots participate in games alongside human players seamlessly

## Database Configuration

### Development
Uses Django's default SQLite for local development.

### Production/Railway
Configured for PostgreSQL via `DATABASE_URL` environment variable.
Redis is used for WebSocket channel layers via `REDIS_URL`.

## Testing Infrastructure

The project has comprehensive test coverage across multiple categories:
- Custom test runner in `run_tests.py` provides categorized test execution
- Selenium-based browser tests for full end-to-end validation
- pytest configuration in `pytest.ini` with coverage reporting
- Separate test settings isolate test database operations

When working with tests, always run the appropriate category based on changes made.