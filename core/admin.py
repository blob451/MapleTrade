"""
Admin configuration for MapleTrade core models.

Note: Most models have been moved to their respective apps.
This file now only imports and customizes the admin as needed.
"""

from django.contrib import admin

# The models are now in their respective apps:
# - Stock, Sector, PriceData → data app
# - AnalysisResult → analytics app  
# - UserPortfolio, PortfolioStock → users app

# Customize admin site header
admin.site.site_header = 'MapleTrade Administration'
admin.site.site_title = 'MapleTrade Admin'
admin.site.index_title = 'Welcome to MapleTrade Administration'