"""
Abstract base classes for financial data providers.

This module defines the interface that all data providers must implement,
ensuring consistency and allowing easy switching between data sources.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class DataProviderError(Exception):
    """Base exception for data provider errors."""
    pass


class RateLimitError(DataProviderError):
    """Raised when rate limit is exceeded."""
    pass


class ValidationError(DataProviderError):
    """Raised when data validation fails."""
    pass


@dataclass
class StockInfo:
    """Standardized stock information structure."""
    symbol: str
    name: str
    sector: Optional[str] = None
    exchange: Optional[str] = None
    currency: str = 'USD'
    market_cap: Optional[int] = None
    current_price: Optional[Decimal] = None
    target_price: Optional[Decimal] = None
    last_updated: Optional[datetime] = None


@dataclass
class PriceData:
    """Standardized price data structure."""
    symbol: str
    date: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    adjusted_close: Decimal
    volume: int


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, calls_per_minute: int = 60, calls_per_hour: int = 2000):
        self.calls_per_minute = calls_per_minute
        self.calls_per_hour = calls_per_hour
        self.minute_calls = []
        self.hour_calls = []
    
    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        current_time = time.time()
        
        # Clean old calls
        self.minute_calls = [t for t in self.minute_calls if current_time - t < 60]
        self.hour_calls = [t for t in self.hour_calls if current_time - t < 3600]
        
        # Check minute limit
        if len(self.minute_calls) >= self.calls_per_minute:
            sleep_time = 60 - (current_time - self.minute_calls[0])
            if sleep_time > 0:
                logger.info(f"Rate limit reached, sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
        
        # Check hour limit
        if len(self.hour_calls) >= self.calls_per_hour:
            sleep_time = 3600 - (current_time - self.hour_calls[0])
            if sleep_time > 0:
                logger.info(f"Hourly rate limit reached, sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
        
        # Record this call
        current_time = time.time()
        self.minute_calls.append(current_time)
        self.hour_calls.append(current_time)


class BaseDataProvider(ABC):
    """
    Abstract base class for all financial data providers.
    
    This class defines the interface that all data providers must implement,
    ensuring consistency across different data sources.
    """
    
    def __init__(self, rate_limit_calls_per_minute: int = 60):
        self.rate_limiter = RateLimiter(calls_per_minute=rate_limit_calls_per_minute)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def get_stock_info(self, symbol: str) -> StockInfo:
        """
        Get basic information about a stock.
        
        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL', 'MSFT')
            
        Returns:
            StockInfo object with stock details
            
        Raises:
            DataProviderError: If data cannot be retrieved
        """
        pass
    
    @abstractmethod
    def get_price_history(self, symbol: str, start_date: datetime, 
                         end_date: Optional[datetime] = None) -> List[PriceData]:
        """
        Get historical price data for a stock.
        
        Args:
            symbol: Stock ticker symbol
            start_date: Start date for historical data
            end_date: End date for historical data (defaults to today)
            
        Returns:
            List of PriceData objects ordered by date
            
        Raises:
            DataProviderError: If data cannot be retrieved
        """
        pass
    
    @abstractmethod
    def get_current_price(self, symbol: str) -> Decimal:
        """
        Get current/latest price for a stock.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Current price as Decimal
            
        Raises:
            DataProviderError: If price cannot be retrieved
        """
        pass
    
    @abstractmethod
    def search_stocks(self, query: str) -> List[Dict[str, str]]:
        """
        Search for stocks by name or symbol.
        
        Args:
            query: Search query (company name or partial symbol)
            
        Returns:
            List of dictionaries with 'symbol' and 'name' keys
            
        Raises:
            DataProviderError: If search fails
        """
        pass
    
    @abstractmethod
    def validate_symbol(self, symbol: str) -> bool:
        """
        Validate that a symbol exists and is tradeable.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            True if symbol is valid, False otherwise
        """
        pass
    
    def _make_api_call(self, func, *args, **kwargs):
        """
        Make an API call with rate limiting.
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        self.rate_limiter.wait_if_needed()
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"API call failed: {e}")
            raise DataProviderError(f"API call failed: {e}")
    
    def _validate_price_data(self, data: PriceData) -> PriceData:
        """
        Validate and clean price data.
        
        Args:
            data: PriceData object to validate
            
        Returns:
            Validated PriceData object
            
        Raises:
            ValidationError: If validation fails
        """
        # Check for negative prices
        if any(price < 0 for price in [data.open_price, data.high_price, 
                                      data.low_price, data.close_price, data.adjusted_close]):
            raise ValidationError(f"Negative prices found for {data.symbol} on {data.date}")
        
        # Check logical price relationships
        if data.high_price < data.low_price:
            raise ValidationError(f"High price < Low price for {data.symbol} on {data.date}")
        
        if not (data.low_price <= data.open_price <= data.high_price):
            raise ValidationError(f"Open price outside high/low range for {data.symbol} on {data.date}")
        
        if not (data.low_price <= data.close_price <= data.high_price):
            raise ValidationError(f"Close price outside high/low range for {data.symbol} on {data.date}")
        
        # Check volume
        if data.volume < 0:
            raise ValidationError(f"Negative volume for {data.symbol} on {data.date}")
        
        return data
    
    def get_sector_etf_mapping(self) -> Dict[str, str]:
        """
        Get mapping of sectors to their representative ETFs.
        
        Returns:
            Dictionary mapping sector names to ETF symbols
        """
        return {
            'Technology': 'XLK',
            'Financials': 'XLF', 
            'Healthcare': 'XLV',
            'Energy': 'XLE',
            'Consumer Discretionary': 'XLY',
            'Industrials': 'XLI',
            'Utilities': 'XLU',
            'Materials': 'XLB',
            'Real Estate': 'XLRE',
            'Communication Services': 'XLC',
            'Consumer Staples': 'XLP',
        }