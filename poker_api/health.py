"""
Minimal health check module for Railway deployment.
This module has no model imports to avoid Django app initialization issues.
"""

import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache


@csrf_exempt
@never_cache
def minimal_health_check(request):
    """
    Ultra-minimal health check endpoint that doesn't import any models.
    Perfect for Railway deployment health checks.
    
    This view is exempt from CSRF protection and SSL redirects to ensure
    Railway health checks work properly.
    """
    # Set security headers to indicate this is safe for HTTP access
    response = JsonResponse({
        'status': 'healthy',
        'timestamp': time.time(),
        'service': 'poker_api'
    }, status=200)
    
    # Add headers to prevent caching and indicate health check
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Health-Check'] = 'true'
    
    return response


def basic_health_check(request):
    """
    Basic health check with minimal database connectivity test.
    """
    health_data = {
        'status': 'healthy',
        'timestamp': time.time(),
        'service': 'poker_api',
        'checks': {}
    }
    
    # Test database connectivity without importing models
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_data['checks']['database'] = 'healthy'
    except Exception as e:
        health_data['checks']['database'] = f'unhealthy: {str(e)}'
        health_data['status'] = 'unhealthy'
        return JsonResponse(health_data, status=503)
    
    return JsonResponse(health_data, status=200)