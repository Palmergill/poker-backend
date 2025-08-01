# poker_project/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.views.static import serve
from django.conf import settings
from django.http import HttpResponse
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from poker_api.views import simple_health_check
import os

def serve_react_app(request):
    """Serve the React app's index.html for client-side routing"""
    try:
        index_path = os.path.join(settings.BASE_DIR, 'poker-frontend', 'build', 'index.html')
        
        # Check if React build exists
        if os.path.exists(index_path):
            with open(index_path, 'r') as f:
                return HttpResponse(f.read(), content_type='text/html')
        else:
            # Fallback: serve a simple HTML page explaining the issue
            fallback_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Poker App - Build Issue</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                    .error { color: #d32f2f; }
                </style>
            </head>
            <body>
                <h1>Poker Application</h1>
                <p class="error">React frontend build not found. Please check deployment logs.</p>
                <p>Available endpoints:</p>
                <ul style="display: inline-block; text-align: left;">
                    <li><a href="/admin/">Django Admin</a></li>
                    <li><a href="/api/">API Documentation</a></li>
                    <li><a href="/health/">Health Check</a></li>
                </ul>
            </body>
            </html>
            """
            return HttpResponse(fallback_html, content_type='text/html')
            
    except Exception as e:
        print(f"Error serving React app: {e}")
        return HttpResponse(f"Error: {e}", content_type='text/plain', status=500)

def serve_manifest(request):
    """Serve the React app's manifest.json"""
    try:
        import json
        from django.http import JsonResponse
        with open(os.path.join(settings.BASE_DIR, 'poker-frontend', 'build', 'manifest.json'), 'r') as f:
            manifest_data = json.load(f)
        return JsonResponse(manifest_data)
    except FileNotFoundError:
        from django.http import Http404
        raise Http404("Manifest not found")

urlpatterns = [
    # API and admin routes
    path('admin/', admin.site.urls),
    path('api/', include('poker_api.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('health/', simple_health_check, name='simple_health_check'),
    
    # React app specific files
    path('manifest.json', serve_manifest, name='manifest'),
    
    # Static files from React build (for assets like CSS, JS)
    re_path(r'^static/(?P<path>.*)$', serve, {
        'document_root': os.path.join(settings.BASE_DIR, 'poker-frontend', 'build', 'static'),
    }),
    
    # Serve React app for all other routes (catch-all for client-side routing)
    re_path(r'^.*$', serve_react_app, name='react_app'),
]