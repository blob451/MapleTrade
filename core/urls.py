"""
Core app URL configuration.
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Home and dashboard
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Portfolio analysis
    path('portfolio/<int:portfolio_id>/analyze/', views.analyze_portfolio, name='analyze_portfolio'),
    
    # Stock analysis
    path('analyze/stock/', views.analyze_stock, name='analyze_stock'),
    path('analyze/stock/<str:symbol>/', views.analyze_stock, name='analyze_stock_symbol'),
    
    # Stock operations
    path('stocks/search/', views.stock_search, name='stock_search'),
    path('stocks/add/', views.add_to_portfolio, name='add_to_portfolio'),
    path('stocks/compare/', views.compare_stocks, name='compare_stocks'),
    path('stocks/screen/', views.screen_stocks, name='screen_stocks'),
    
    # Market data
    path('market/overview/', views.market_overview, name='market_overview'),
    
    # API endpoints
    path('api/portfolio/<int:portfolio_id>/value/', views.api_portfolio_value, name='api_portfolio_value'),
    path('api/portfolio/<int:portfolio_id>/allocation/', views.api_portfolio_allocation, name='api_portfolio_allocation'),
    path('api/batch-update-prices/', views.api_batch_update_prices, name='api_batch_update_prices'),
    
    # Health check
    path('health/', views.health_check, name='health_check'),
]