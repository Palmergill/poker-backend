"""
WSGI config for poker_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Detect Railway environment and set appropriate settings
if os.getenv('RAILWAY_ENVIRONMENT'):
    default_settings = 'poker_project.settings.railway'
else:
    default_settings = 'poker_project.settings'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', default_settings)

application = get_wsgi_application()
