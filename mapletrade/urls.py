"""
URL configuration for mapletrade project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
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
    
    # API will be added in future phases
    # path('api/', include('api.urls')),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom admin site configuration
admin.site.site_header = 'MapleTrade Administration'
admin.site.site_title = 'MapleTrade Admin'
admin.site.index_title = 'Welcome to MapleTrade Administration'