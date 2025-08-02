# Updated ASGI configuration for poker_project/asgi.py
"""
ASGI config for poker_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

# Detect Railway environment and set appropriate settings
if os.getenv('RAILWAY_ENVIRONMENT'):
    default_settings = 'poker_project.settings.railway'
else:
    default_settings = 'poker_project.settings.development'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', default_settings)

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Now import the routing and middleware after Django is initialized
from poker_api.middleware import JWTAuthMiddleware
import poker_api.routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddleware(
            URLRouter(
                poker_api.routing.websocket_urlpatterns
            )
        )
    ),
})