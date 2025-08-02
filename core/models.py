"""
Core models for MapleTrade application.

This module serves as a compatibility layer for imports.
All models have been moved to their respective apps.
"""

def get_stock_model():
    """Get Stock model to avoid circular import."""
    from data.models import Stock
    return Stock

def get_sector_model():
    """Get Sector model to avoid circular import."""
    from data.models import Sector
    return Sector

def get_pricedata_model():
    """Get PriceData model to avoid circular import."""
    from data.models import PriceData
    return PriceData

def get_analysisresult_model():
    """Get AnalysisResult model to avoid circular import."""
    from analytics.models import AnalysisResult
    return AnalysisResult

def get_userportfolio_model():
    """Get UserPortfolio model to avoid circular import."""
    from users.models import UserPortfolio
    return UserPortfolio

def get_portfoliostock_model():
    """Get PortfolioStock model to avoid circular import."""
    from users.models import PortfolioStock
    return PortfolioStock

class _ModelProxy:
    @property
    def Stock(self):
        return get_stock_model()
    
    @property
    def Sector(self):
        return get_sector_model()
    
    @property
    def PriceData(self):
        return get_pricedata_model()
    
    @property
    def AnalysisResult(self):
        return get_analysisresult_model()
    
    @property
    def UserPortfolio(self):
        return get_userportfolio_model()
    
    @property
    def PortfolioStock(self):
        return get_portfoliostock_model()

# Create a single instance
models = _ModelProxy()

__all__ = ['models']