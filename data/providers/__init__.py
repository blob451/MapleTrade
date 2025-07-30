"""
Data providers package for MapleTrade.

This package contains abstract base classes and concrete implementations
for fetching financial data from various sources.
"""

from .base import BaseDataProvider, DataProviderError, RateLimitError, ValidationError
from .yahoo_finance import YahooFinanceProvider

# Import additional exceptions from core
from core.exceptions import (
    InvalidSymbolError, DataQualityError, DataSourceUnavailableError,
    InsufficientDataError, ServiceUnavailableError
)

__all__ = [
    'BaseDataProvider',
    'DataProviderError', 
    'RateLimitError',
    'ValidationError',
    'YahooFinanceProvider',
    
    # Additional exceptions
    'InvalidSymbolError',
    'DataQualityError', 
    'DataSourceUnavailableError',
    'InsufficientDataError',
    'ServiceUnavailableError',
]