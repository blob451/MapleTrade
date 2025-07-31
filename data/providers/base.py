"""
Base classes and interfaces for data providers.

This module defines the abstract base classes and data structures
that all data providers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Any
import time
import logging
from collections import deque


# Custom exceptions
class DataProviderError(Exception):
    """Base exception for data provider errors."""
    pass


class RateLimitError(DataProviderError):
    """Raised when API rate limit is exceeded."""
    pass


class ValidationError(DataProviderError):
    """Raised when data validation fails."""
    pass


# Data structures
@dataclass
class StockInfo:
    """Basic stock information."""
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
    """Historical price data point."""
    symbol: str
    date: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    adjusted_close: Decimal
    volume: int
    
    def __post_init__(self):
        """Validate data after initialization."""
        if self.high_price < self.low_price:
            raise ValidationError(f"High price {self.high_price} is less than low price {self.low_price}")
        
        if not (self.low_price <= self.open_price <= self.high_price):
            raise ValidationError(f"Open price {self.open_price} is outside high/low range")
        
        if not (self.low_price <= self.close_price <= self.high_price):
            raise ValidationError(f"Close price {self.close_price} is outside high/low range")


@dataclass
class FinancialData:
    """Company financial metrics."""
    symbol: str
    revenue: Optional[Decimal] = None
    earnings: Optional[Decimal] = None
    pe_ratio: Optional[Decimal] = None
    peg_ratio: Optional[Decimal] = None
    price_to_book: Optional[Decimal] = None
    debt_to_equity: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    roa: Optional[Decimal] = None
    profit_margin: Optional[Decimal] = None
    last_updated: Optional[datetime] = None


# Abstract base class
class BaseDataProvider(ABC):
    """
    Abstract base class for all data providers.
    
    Provides common functionality like rate limiting and logging,
    while defining the interface that concrete providers must implement.
    """
    
    def __init__(self, rate_limit_calls_per_minute: int = 60):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.rate_limit_calls_per_minute = rate_limit_calls_per_minute
        self._call_times = deque(maxlen=rate_limit_calls_per_minute)
        self._last_call_time = 0
    
    @abstractmethod
    def get_stock_info(self, symbol: str) -> StockInfo:
        """
        Get basic information about a stock.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            StockInfo object with current data
            
        Raises:
            DataProviderError: If data cannot be fetched
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
            end_date: End date for historical data (default: today)
            
        Returns:
            List of PriceData objects, ordered by date
            
        Raises:
            DataProviderError: If data cannot be fetched
        """
        pass
    
    @abstractmethod
    def get_current_price(self, symbol: str) -> Decimal:
        """
        Get current price for a stock.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Current price as Decimal
            
        Raises:
            DataProviderError: If price cannot be fetched
        """
        pass
    
    def get_financial_data(self, symbol: str) -> FinancialData:
        """
        Get financial metrics for a stock.
        
        Default implementation returns empty data.
        Providers can override to add financial data support.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            FinancialData object
        """
        return FinancialData(symbol=symbol)
    
    def search_stocks(self, query: str) -> List[Dict[str, str]]:
        """
        Search for stocks by name or symbol.
        
        Default implementation returns empty list.
        Providers can override to add search support.
        
        Args:
            query: Search query
            
        Returns:
            List of dicts with 'symbol' and 'name' keys
        """
        return []
    
    def validate_symbol(self, symbol: str) -> bool:
        """
        Check if a symbol is valid.
        
        Default implementation tries to fetch stock info.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            True if symbol is valid, False otherwise
        """
        try:
            self.get_stock_info(symbol)
            return True
        except DataProviderError:
            return False
    
    def _check_rate_limit(self):
        """Check if we're within rate limits."""
        if not self.rate_limit_calls_per_minute:
            return
        
        current_time = time.time()
        
        # Remove calls older than 1 minute
        while self._call_times and current_time - self._call_times[0] > 60:
            self._call_times.popleft()
        
        # Check if we've hit the limit
        if len(self._call_times) >= self.rate_limit_calls_per_minute:
            wait_time = 60 - (current_time - self._call_times[0])
            if wait_time > 0:
                self.logger.warning(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                time.sleep(wait_time + 0.1)  # Add small buffer
    
    def _record_call(self):
        """Record an API call for rate limiting."""
        if self.rate_limit_calls_per_minute:
            self._call_times.append(time.time())
    
    def _make_api_call(self, func, *args, **kwargs):
        """
        Make an API call with rate limiting and error handling.
        
        Args:
            func: The function to call
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            The result of the function call
            
        Raises:
            RateLimitError: If rate limit is exceeded
            DataProviderError: For other API errors
        """
        # Enforce rate limit if the subclass has the method
        if hasattr(self, '_enforce_rate_limit'):
            self._enforce_rate_limit()
        
        self._check_rate_limit()
        
        try:
            result = func(*args, **kwargs)
            self._record_call()
            return result
        except Exception as e:
            error_msg = str(e)
            if '429' in error_msg or 'rate limit' in error_msg.lower():
                self.logger.warning(f"Rate limit hit: {error_msg}")
                raise RateLimitError(f"Rate limit exceeded: {error_msg}")
            else:
                raise DataProviderError(f"API call failed: {error_msg}")
    
    def _validate_price_data(self, price_data: PriceData) -> PriceData:
        """
        Validate price data for consistency.
        
        Args:
            price_data: PriceData to validate
            
        Returns:
            Validated PriceData
            
        Raises:
            ValidationError: If validation fails
        """
        # Validation happens in PriceData.__post_init__
        # This method is here for additional provider-specific validation
        
        # Check for unrealistic values
        if price_data.close_price <= 0:
            raise ValidationError(f"Invalid close price: {price_data.close_price}")
        
        if price_data.volume < 0:
            raise ValidationError(f"Invalid volume: {price_data.volume}")
        
        # Check for extreme price movements (>50% in a day)
        price_range = price_data.high_price - price_data.low_price
        if price_range / price_data.low_price > 0.5:
            self.logger.warning(
                f"Large price movement detected for {price_data.symbol} on {price_data.date}: "
                f"Low: {price_data.low_price}, High: {price_data.high_price}"
            )
        
        return price_data