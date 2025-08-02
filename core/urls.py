"""
URL configuration for core app.
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Analysis endpoints
    path('analyze/', views.analyze_stock, name='analyze-stock'),
    path('analyze/<str:symbol>/history/', views.get_analysis_history, name='analysis-history'),
    
    # Stock endpoints
    path('stocks/<str:symbol>/', views.get_stock_info, name='stock-info'),
    
    # Sector endpoints
    path('sectors/', views.list_sectors, name='list-sectors'),
    
    # Health check
    path('analytics/health/', views.health_check, name='health-check'),
]