"""
Yahoo Finance data provider implementation.

This module implements the BaseDataProvider interface using Yahoo Finance
as the data source, with proper rate limiting and error handling.
"""

import yfinance as yf
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import pandas as pd
import logging
import time
from functools import wraps
from django.conf import settings
from django.core.cache import cache

from .base import (
    BaseDataProvider, StockInfo, PriceData, 
    DataProviderError, ValidationError, RateLimitError
)

logger = logging.getLogger(__name__)


def rate_limit_handler(func):
    """Decorator to handle rate limiting with exponential backoff."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        max_retries = 3
        base_delay = 5  # Start with 5 seconds
        
        for attempt in range(max_retries):
            try:
                return func(self, *args, **kwargs)
            except (DataProviderError, Exception) as e:
                error_str = str(e)
                # Check if it's a rate limit error
                if any(x in error_str for x in ['429', 'Too Many Requests', 'rate limit']):
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"Rate limited, waiting {delay} seconds before retry (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(delay)
                        continue
                    else:
                        # Convert to RateLimitError on final attempt
                        raise RateLimitError(f"Rate limit exceeded after {max_retries} attempts: {error_str}")
                else:
                    # Not a rate limit error, raise immediately
                    raise
        
        # This should not be reached, but just in case
        return func(self, *args, **kwargs)
    
    return wrapper


class YahooFinanceProvider(BaseDataProvider):
    """
    Yahoo Finance implementation of BaseDataProvider.
    
    Provides stock data using the yfinance library with rate limiting
    and comprehensive error handling.
    """
    
    def __init__(self):
        # More conservative rate limit for Yahoo Finance
        super().__init__(rate_limit_calls_per_minute=10)  
        self.timeout = getattr(settings, 'YAHOO_FINANCE_TIMEOUT', 30)
        self._last_request_time = 0
        self._min_request_interval = 3  # Minimum 3 seconds between requests
    
    def _enforce_rate_limit(self):
        """Enforce minimum time between requests."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    @rate_limit_handler
    def get_stock_info(self, symbol: str) -> StockInfo:
        """Get basic stock information from Yahoo Finance."""
        # Check cache first
        cache_key = f"yf_stock_info:{symbol.upper()}"
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Using cached stock info for {symbol}")
            return cached_data
        
        self._enforce_rate_limit()
        
        try:
            def _fetch_info():
                ticker = yf.Ticker(symbol.upper())
                info = ticker.info
                
                # Check if we got valid data
                if not info or 'symbol' not in info:
                    # Try to get basic info from history
                    hist = ticker.history(period="1d")
                    if hist.empty:
                        raise DataProviderError(f"No data found for symbol: {symbol}")
                    
                    # Create minimal info from history
                    info = {
                        'symbol': symbol.upper(),
                        'regularMarketPrice': float(hist['Close'].iloc[-1]) if not hist.empty else None,
                        'currency': 'USD'
                    }
                
                return info
            
            info = self._make_api_call(_fetch_info)
            
            # Extract data with fallbacks
            stock_info = StockInfo(
                symbol=info.get('symbol', symbol.upper()),
                name=info.get('longName') or info.get('shortName') or symbol.upper(),
                sector=info.get('sector'),
                exchange=info.get('exchange'),
                currency=info.get('currency', 'USD'),
                market_cap=info.get('marketCap'),
                current_price=self._safe_decimal(
                    info.get('regularMarketPrice') or 
                    info.get('currentPrice') or 
                    info.get('price') or
                    info.get('previousClose')
                ),
                target_price=self._safe_decimal(info.get('targetMeanPrice')),
                last_updated=datetime.now()
            )
            
            # Cache for 15 minutes
            cache.set(cache_key, stock_info, 900)
            
            return stock_info
            
        except RateLimitError:
            raise  # Re-raise rate limit errors
        except Exception as e:
            logger.error(f"Failed to get stock info for {symbol}: {e}")
            raise DataProviderError(f"Failed to get stock info for {symbol}: {str(e)}")
    
    @rate_limit_handler
    def get_price_history(self, symbol: str, start_date: datetime, 
                         end_date: Optional[datetime] = None) -> List[PriceData]:
        """Get historical price data from Yahoo Finance."""
        if end_date is None:
            end_date = datetime.now()
        
        # Check cache first
        cache_key = f"yf_price_history:{symbol.upper()}:{start_date.date()}:{end_date.date()}"
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Using cached price history for {symbol}")
            return cached_data
        
        self._enforce_rate_limit()
        
        try:
            def _fetch_history():
                ticker = yf.Ticker(symbol.upper())
                
                # Fetch with specific parameters to avoid issues
                hist_data = ticker.history(
                    start=start_date.strftime('%Y-%m-%d'),
                    end=end_date.strftime('%Y-%m-%d'),
                    auto_adjust=False,
                    prepost=False,
                    actions=False,
                    progress=False
                )
                
                return hist_data
            
            hist_data = self._make_api_call(_fetch_history)
            
            if hist_data is None or hist_data.empty:
                # Try alternative period-based approach
                logger.warning(f"No data with date range for {symbol}, trying period approach")
                
                # Calculate period
                days_diff = (end_date - start_date).days
                if days_diff <= 7:
                    period = "5d"
                elif days_diff <= 30:
                    period = "1mo"
                elif days_diff <= 90:
                    period = "3mo"
                elif days_diff <= 180:
                    period = "6mo"
                elif days_diff <= 365:
                    period = "1y"
                else:
                    period = "max"
                
                def _fetch_by_period():
                    ticker = yf.Ticker(symbol.upper())
                    return ticker.history(period=period, auto_adjust=False)
                
                hist_data = self._make_api_call(_fetch_by_period)
                
                if hist_data is None or hist_data.empty:
                    raise DataProviderError(f"No historical data found for {symbol}")
            
            price_data = []
            for date, row in hist_data.iterrows():
                try:
                    # Convert pandas Timestamp to datetime if needed
                    if hasattr(date, 'to_pydatetime'):
                        date_obj = date.to_pydatetime()
                    else:
                        date_obj = date
                    
                    # Skip if outside our requested range
                    if date_obj.date() < start_date.date() or date_obj.date() > end_date.date():
                        continue
                    
                    data = PriceData(
                        symbol=symbol.upper(),
                        date=date_obj,
                        open_price=self._safe_decimal(row.get('Open')),
                        high_price=self._safe_decimal(row.get('High')),
                        low_price=self._safe_decimal(row.get('Low')),
                        close_price=self._safe_decimal(row.get('Close')),
                        adjusted_close=self._safe_decimal(
                            row.get('Adj Close', row.get('Close'))
                        ),
                        volume=int(row.get('Volume', 0)) if pd.notna(row.get('Volume')) else 0
                    )
                    
                    # Validate each price data point
                    validated_data = self._validate_price_data(data)
                    price_data.append(validated_data)
                    
                except (ValidationError, ValueError) as e:
                    logger.warning(f"Skipping invalid data for {symbol} on {date}: {e}")
                    continue
            
            if not price_data:
                raise DataProviderError(f"No valid price data found for {symbol}")
            
            # Sort by date
            price_data = sorted(price_data, key=lambda x: x.date)
            
            # Cache for 1 hour
            cache.set(cache_key, price_data, 3600)
            
            return price_data
            
        except RateLimitError:
            raise  # Re-raise rate limit errors
        except Exception as e:
            logger.error(f"Failed to get price history for {symbol}: {e}")
            raise DataProviderError(f"Failed to get price history for {symbol}: {str(e)}")
    
    @rate_limit_handler
    def get_current_price(self, symbol: str) -> Decimal:
        """Get current price from Yahoo Finance."""
        # Try to get from stock info first (uses cache)
        try:
            stock_info = self.get_stock_info(symbol)
            if stock_info.current_price:
                return stock_info.current_price
        except Exception:
            pass
        
        self._enforce_rate_limit()
        
        try:
            def _fetch_current():
                ticker = yf.Ticker(symbol.upper())
                # Get most recent price
                hist = ticker.history(period="1d", interval="1m")
                
                if not hist.empty:
                    return float(hist['Close'].iloc[-1])
                
                # Fallback to info
                info = ticker.info
                for field in ['regularMarketPrice', 'currentPrice', 'price', 'previousClose']:
                    if field in info and info[field]:
                        return float(info[field])
                
                raise DataProviderError(f"No current price available for {symbol}")
            
            price = self._make_api_call(_fetch_current)
            return self._safe_decimal(price)
            
        except RateLimitError:
            raise  # Re-raise rate limit errors
        except Exception as e:
            logger.error(f"Failed to get current price for {symbol}: {e}")
            raise DataProviderError(f"Failed to get current price for {symbol}: {str(e)}")
    
    def search_stocks(self, query: str) -> List[Dict[str, str]]:
        """Search for stocks using Yahoo Finance."""
        # Note: yfinance doesn't have a direct search API
        # This is a basic implementation
        results = []
        
        # Clean the query
        query = query.upper().strip()
        
        # Try direct symbol lookup
        try:
            stock_info = self.get_stock_info(query)
            results.append({
                'symbol': stock_info.symbol,
                'name': stock_info.name
            })
        except DataProviderError:
            pass
        
        # For more comprehensive search, you'd need to use a different API
        # or maintain a local database of symbols
        
        return results
    
    def validate_symbol(self, symbol: str) -> bool:
        """Validate symbol by attempting to fetch basic info."""
        try:
            stock_info = self.get_stock_info(symbol)
            return stock_info is not None and stock_info.symbol
        except (DataProviderError, RateLimitError):
            return False
    
    def _safe_decimal(self, value: Any) -> Optional[Decimal]:
        """Safely convert value to Decimal."""
        if value is None or pd.isna(value):
            return None
        
        try:
            # Handle string values
            if isinstance(value, str):
                # Remove currency symbols and commas
                cleaned = value.replace('$', '').replace(',', '').strip()
                if not cleaned or cleaned.upper() == 'N/A':
                    return None
                return Decimal(cleaned)
            else:
                return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            logger.warning(f"Could not convert value to Decimal: {value}")
            return None
    
    def get_multiple_stocks_info(self, symbols: List[str]) -> Dict[str, StockInfo]:
        """
        Get information for multiple stocks efficiently.
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            Dictionary mapping symbols to StockInfo objects
        """
        results = {}
        
        for symbol in symbols:
            try:
                results[symbol] = self.get_stock_info(symbol)
                # Add small delay between requests
                if symbol != symbols[-1]:  # Not the last symbol
                    time.sleep(0.5)
            except (DataProviderError, RateLimitError) as e:
                logger.warning(f"Failed to get info for {symbol}: {e}")
                continue
        
        return results
    
    def get_sector_stocks(self, sector_etf: str, limit: int = 50) -> List[str]:
        """
        Get a list of stocks from a sector ETF.
        Note: This is a simplified implementation.
        """
        # This would require additional data sources or APIs
        # For now, return empty list
        return []
    
    def _make_api_call(self, func, *args, **kwargs):
        """Override parent method to handle Yahoo Finance specific errors."""
        try:
            # Use parent's rate limiting
            return super()._make_api_call(func, *args, **kwargs)
        except Exception as e:
            error_str = str(e)
            
            # Check for specific Yahoo Finance errors
            if any(x in error_str for x in [
                'No timezone found',
                'symbol may be delisted',
                'No data found',
                'Expecting value'
            ]):
                raise DataProviderError(f"Invalid symbol or no data available: {error_str}")
            
            # Re-raise other errors
            raise