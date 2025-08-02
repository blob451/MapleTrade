"""
Constants for MapleTrade application.

This module centralizes all magic numbers and configuration constants
used throughout the application.
"""

from decimal import Decimal


class TimeConstants:
    """Time-related constants in seconds."""
    
    # Cache timeouts
    CACHE_MARKET_DATA = 3600          # 1 hour
    CACHE_ANALYSIS_RESULTS = 14400    # 4 hours
    CACHE_HEALTH_CHECK = 300          # 5 minutes
    CACHE_SHORT = 60                  # 1 minute
    
    # Update intervals
    STOCK_UPDATE_INTERVAL = 3600      # 1 hour
    ANALYSIS_VALIDITY_PERIOD = 86400  # 24 hours
    
    # API timeouts
    YAHOO_FINANCE_TIMEOUT = 30        # 30 seconds
    HEALTH_CHECK_DB_TIMEOUT = 10      # 10 seconds
    HEALTH_CHECK_API_TIMEOUT = 15     # 15 seconds


class AnalysisConstants:
    """Analysis-related constants."""
    
    # Analysis parameters
    DEFAULT_ANALYSIS_MONTHS = 6
    MIN_ANALYSIS_MONTHS = 1
    MAX_ANALYSIS_MONTHS = 60
    
    # Trading days
    TRADING_DAYS_PER_YEAR = 252
    TRADING_DAYS_PER_MONTH = 21
    
    # Minimum data requirements
    MIN_PRICE_POINTS_FOR_ANALYSIS = 10
    MIN_RETURNS_FOR_VOLATILITY = 5
    
    # Signal confidence thresholds
    HIGH_CONFIDENCE = 'HIGH'
    MEDIUM_CONFIDENCE = 'MEDIUM'
    LOW_CONFIDENCE = 'LOW'


class VolatilityConstants:
    """Volatility-related constants."""
    
    # Default thresholds
    DEFAULT_VOLATILITY_THRESHOLD = Decimal('0.42')
    
    # Risk categories by volatility
    LOW_RISK_THRESHOLD = Decimal('0.30')
    MEDIUM_RISK_THRESHOLD = Decimal('0.45')
    
    # Sector-specific thresholds (examples)
    SECTOR_THRESHOLDS = {
        'TECH': Decimal('0.42'),
        'FINANCE': Decimal('0.35'),
        'HEALTHCARE': Decimal('0.30'),
        'UTILITIES': Decimal('0.20'),
        'ENERGY': Decimal('0.45'),
        'DEFAULT': Decimal('0.40')
    }


class RateLimitConstants:
    """Rate limiting constants."""
    
    # Requests per minute
    DEFAULT_RATE_LIMIT = 60
    YAHOO_FINANCE_RATE_LIMIT = 10
    
    # Retry parameters
    MAX_RETRIES = 3
    RETRY_DELAY = 60  # seconds


class ModelConstants:
    """Model-related constants."""
    
    # Field lengths
    SYMBOL_MAX_LENGTH = 10
    NAME_MAX_LENGTH = 200
    SECTOR_NAME_MAX_LENGTH = 100
    
    # Default values
    DEFAULT_CURRENCY = 'USD'
    DEFAULT_ENGINE_VERSION = '1.0.0'
    
    # Defensive sectors
    DEFENSIVE_SECTOR_CODES = ['UTIL', 'CONS', 'HLTH', 'REAL']


class CacheKeys:
    """Cache key templates."""
    
    # Analysis cache keys
    ANALYSIS_RESULT = "analysis_{symbol}_{months}"
    
    # Price data cache keys
    PRICE_DATA = "price_data_{symbol}_{start_date}_{end_date}"
    
    # Stock info cache keys
    STOCK_INFO = "stock_info_{symbol}"
    
    # Health check cache keys
    HEALTH_CHECK = "health_test"
    
    @staticmethod
    def get_analysis_key(symbol: str, months: int) -> str:
        """Generate analysis cache key."""
        return CacheKeys.ANALYSIS_RESULT.format(symbol=symbol, months=months)
    
    @staticmethod
    def get_price_data_key(symbol: str, start_date: str, end_date: str) -> str:
        """Generate price data cache key."""
        return CacheKeys.PRICE_DATA.format(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
    
    @staticmethod
    def get_stock_info_key(symbol: str) -> str:
        """Generate stock info cache key."""
        return CacheKeys.STOCK_INFO.format(symbol=symbol)


# Error messages
class ErrorMessages:
    """Standardized error messages."""
    
    # Validation errors
    SYMBOL_REQUIRED = "Symbol is required"
    INVALID_ANALYSIS_PERIOD = f"Analysis months must be between {AnalysisConstants.MIN_ANALYSIS_MONTHS} and {AnalysisConstants.MAX_ANALYSIS_MONTHS}"
    
    # Data errors
    INSUFFICIENT_DATA = "Insufficient price data for analysis"
    STOCK_NOT_FOUND = "Stock {symbol} not found"
    
    # Calculation errors
    RETURN_CALC_FAILED = "Return calculation failed: {error}"
    VOLATILITY_CALC_FAILED = "Volatility calculation failed: {error}"
    
    # System errors
    INTERNAL_SERVER_ERROR = "Internal server error"
    SERVICE_UNAVAILABLE = "Service temporarily unavailable"