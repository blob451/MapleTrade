"""
URL configuration for mapletrade project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core.health import (
    health_check, health_check_simple,
    readiness_check, liveness_check
)

# Health check URLs - accessible without authentication
health_urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('health/simple/', health_check_simple, name='health_check_simple'),
    path('health/ready/', readiness_check, name='readiness_check'),
    path('health/live/', liveness_check, name='liveness_check'),
]

# Main URL patterns
urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),
    
    # Health checks (no authentication required)
    *health_urlpatterns,
    
    # API endpoints
    path('api/', include('core.urls')),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom admin site configuration
admin.site.site_header = 'MapleTrade Administration'
admin.site.site_title = 'MapleTrade Admin'
admin.site.index_title = 'Welcome to MapleTrade Administration'