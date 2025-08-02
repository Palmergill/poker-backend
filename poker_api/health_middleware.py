"""
Middleware to allow HTTP requests for health check endpoint only.
This prevents SSL redirects from interfering with Railway health checks.
"""

from django.http import HttpResponsePermanentRedirect
from django.conf import settings


class HealthCheckSSLExemptMiddleware:
    """
    Middleware that exempts the health check endpoint from SSL redirects.
    This allows Railway health checks to work over HTTP while maintaining
    HTTPS redirects for all other endpoints.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if this is a health check request
        if request.path == '/health/':
            # Temporarily disable SSL redirect for this request
            original_ssl_redirect = getattr(settings, 'SECURE_SSL_REDIRECT', False)
            settings.SECURE_SSL_REDIRECT = False
            
            response = self.get_response(request)
            
            # Restore original SSL redirect setting
            settings.SECURE_SSL_REDIRECT = original_ssl_redirect
            
            return response
        
        # For all other requests, proceed normally
        return self.get_response(request)