# Poker App Backend

Django REST API backend for the multiplayer poker application with WebSocket support for real-time gameplay.

**Note:** This is the backend-only repository. The React frontend is deployed separately.

## Railway Deployment

This backend is configured for Railway deployment as a separate service from the frontend.

### Environment Variables

Set these in your Railway backend service:

**Required:**
- `SECRET_KEY` - Django secret key
- `DATABASE_URL` - PostgreSQL connection URL (auto-provided by Railway)
- `REDIS_URL` - Redis connection URL (auto-provided by Railway)

**Optional:**
- `FRONTEND_URL` - Frontend application URL for CORS (e.g., https://your-frontend.railway.app)
- `CORS_ALLOWED_ORIGINS` - Additional CORS origins (comma-separated)
- `LOG_LEVEL` - Logging level (default: INFO)

### Deployment Steps

1. Create a new Railway service
2. Connect this repository
3. Add PostgreSQL and Redis services
4. Set environment variables
5. Deploy

### API Endpoints

- `/api/` - REST API endpoints
- `/ws/` - WebSocket connections for real-time game updates
- `/admin/` - Django admin interface

## Project Overview

This application allows users to:

- Create accounts and manage their profiles
- Deposit and withdraw funds (simulated)
- Join poker tables with different stakes
- Play Texas Hold'em poker in real-time with other players

## Tech Stack

### Backend

- Python 3.x
- Django & Django REST Framework
- Django Channels for WebSockets
- PostgreSQL database
- JWT Authentication

### Frontend

- React
- React Router for navigation
- Axios for API requests
- WebSockets for real-time game updates

## Installation and Setup

### Prerequisites

- Python 3.8+
- Node.js 14+ and npm
- PostgreSQL
- Redis (for WebSockets)

### Database Setup

1. Install PostgreSQL if you haven't already
2. Create a database named `poker_db`:
   ```
   createdb poker_db
   ```
3. Update the database credentials in `poker_project/settings.py` if needed

### Backend Setup

1. Clone the repository
2. Set up a virtual environment:
   ```
   python -m venv venv
   ```
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
5. Apply migrations:
   ```
   python manage.py migrate
   ```
6. Create a superuser:
   ```
   python manage.py createsuperuser
   ```
7. Run the server:
   ```
   python manage.py runserver
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```
   cd poker-frontend
   ```
2. Install dependencies:
   ```
   npm install
   ```
3. Run the development server:
   ```
   npm start
   ```

## Using the VS Code Quick Start

For convenience, a startup script and VS Code configuration have been provided:

1. Make sure the `start_poker_app.py` file is in your project root
2. Create a `.vscode` directory at your project root
3. Place `tasks.json` and `launch.json` in the `.vscode` directory
4. In VS Code, use the shortcuts:
   - `Ctrl+Shift+B` to start the entire application
   - `F5` to debug the Django backend

Alternatively, use the Command Palette (`Ctrl+Shift+P`) and select "Tasks: Run Task" to see available tasks.

## Project Structure

### Backend (Django)

- `poker_project/` - Main Django project
- `poker_api/` - Django app containing API views, models, and serializers
  - `models.py` - Database models for tables, players, games
  - `views.py` - API endpoints
  - `serializers.py` - JSON serializers
  - `consumers.py` - WebSocket consumers for real-time updates
  - `services/` - Business logic for game operations
  - `utils/` - Utility functions for card handling, hand evaluation

### Frontend (React)

- `poker-frontend/src/` - Source code
  - `components/` - React components
  - `services/` - API service functions
  - `App.js` - Main application component with routing

## API Endpoints

- `/api/token/` - Obtain JWT token pair
- `/api/token/refresh/` - Refresh JWT token
- `/api/register/` - Register new user
- `/api/tables/` - List poker tables
- `/api/tables/{id}/` - Get specific table
- `/api/tables/{id}/join_table/` - Join a table
- `/api/games/{id}/` - Get game state
- `/api/games/{id}/start/` - Start a game
- `/api/games/{id}/leave/` - Leave a game
- `/api/games/{id}/action/` - Take game actions
- `/api/players/me/` - Get current player info
- `/api/players/deposit/` - Deposit funds
- `/api/players/withdraw/` - Withdraw funds

## WebSocket Connections

- `ws://localhost:8000/ws/game/{game_id}/` - Real-time game updates

## Game Flow

1. Users register and log in
2. Users can view and join available tables
3. Once seated at a table, users can start a game if enough players are present
4. The game proceeds with standard Texas Hold'em rules:
   - Players are dealt two hole cards
   - Betting rounds are interspersed with community cards being revealed
   - Winning hands are determined based on standard poker hand rankings

## Credits

This application was built using Django REST Framework and React, with the poker game logic implemented in Python.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
