"""
Simplified ASGI configuration for debugging Railway deployment issues.
This version only handles HTTP requests, no WebSocket functionality.
"""

import os
import django
from django.core.asgi import get_asgi_application

# Detect Railway environment and set appropriate settings
if os.getenv('RAILWAY_ENVIRONMENT'):
    default_settings = 'poker_project.settings.railway'
else:
    default_settings = 'poker_project.settings.development'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', default_settings)

# Initialize Django ASGI application
django.setup()
application = get_asgi_application()