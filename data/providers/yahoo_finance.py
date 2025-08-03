"""
Yahoo Finance data provider implementation.

This module provides real-time and historical market data using yfinance library.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from decimal import Decimal

import yfinance as yf
from django.core.cache import cache
from django.utils import timezone

from .base import BaseDataProvider, StockInfo

logger = logging.getLogger(__name__)


@dataclass
class PriceHistory:
    """Data class for price history entries."""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    adjusted_close: Optional[float] = None


class YahooFinanceProvider(BaseDataProvider):
    """
    Yahoo Finance data provider using yfinance library.
    
    This provider fetches real-time stock data, historical prices,
    and fundamental data from Yahoo Finance.
    """
    
    def __init__(self):
        super().__init__()
        self.cache_timeout = 300  # 5 minutes for real-time data
        
    def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """
        Get current stock information from Yahoo Finance.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            StockInfo object or None if not found
        """
        try:
            # Check cache first
            cache_key = f"yf_info_{symbol}"
            cached_info = cache.get(cache_key)
            if cached_info:
                logger.debug(f"Returning cached info for {symbol}")
                return cached_info
            
            # Fetch from Yahoo Finance
            logger.info(f"Fetching info for {symbol} from Yahoo Finance")
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if not info or 'symbol' not in info:
                logger.warning(f"No data found for symbol: {symbol}")
                return None
            
            # Parse the data
            stock_info = StockInfo(
                symbol=info.get('symbol', symbol).upper(),
                name=info.get('longName') or info.get('shortName', 'Unknown'),
                exchange=info.get('exchange', ''),
                currency=info.get('currency', 'USD'),
                current_price=self._safe_decimal(info.get('currentPrice') or info.get('regularMarketPrice')),
                previous_close=self._safe_decimal(info.get('previousClose')),
                market_cap=info.get('marketCap'),
                volume=info.get('volume') or info.get('regularMarketVolume'),
                
                # Fundamental data
                pe_ratio=self._safe_float(info.get('trailingPE')),
                eps=self._safe_decimal(info.get('trailingEps')),
                dividend_yield=self._safe_float(info.get('dividendYield')),
                
                # Analyst data
                target_price=self._safe_decimal(info.get('targetMeanPrice')),
                recommendation=info.get('recommendationKey', ''),
                
                # Company info
                sector=info.get('sector', ''),
                industry=info.get('industry', ''),
                website=info.get('website', ''),
                description=info.get('longBusinessSummary', '')[:500] if info.get('longBusinessSummary') else '',
                
                # Additional metrics
                fifty_two_week_high=self._safe_decimal(info.get('fiftyTwoWeekHigh')),
                fifty_two_week_low=self._safe_decimal(info.get('fiftyTwoWeekLow')),
                two_hundred_day_avg=self._safe_decimal(info.get('twoHundredDayAverage')),
                fifty_day_avg=self._safe_decimal(info.get('fiftyDayAverage')),
                
                last_updated=timezone.now()
            )
            
            # Cache the result
            cache.set(cache_key, stock_info, self.cache_timeout)
            
            return stock_info
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def get_price_history(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime,
        interval: str = '1d'
    ) -> List[PriceHistory]:
        """
        Get historical price data from Yahoo Finance.
        
        Args:
            symbol: Stock ticker symbol
            start_date: Start date for history
            end_date: End date for history
            interval: Data interval (1d, 1wk, 1mo)
            
        Returns:
            List of PriceHistory objects
        """
        try:
            # Check cache
            cache_key = f"yf_history_{symbol}_{start_date.date()}_{end_date.date()}_{interval}"
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.debug(f"Returning cached history for {symbol}")
                return cached_data
            
            logger.info(f"Fetching history for {symbol} from {start_date} to {end_date}")
            
            # Fetch from Yahoo Finance
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=start_date,
                end=end_date,
                interval=interval,
                auto_adjust=False,
                prepost=False
            )
            
            if df.empty:
                logger.warning(f"No historical data found for {symbol}")
                return []
            
            # Convert to PriceHistory objects
            price_history = []
            for date, row in df.iterrows():
                price_history.append(PriceHistory(
                    date=date.to_pydatetime(),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume']),
                    adjusted_close=float(row['Adj Close']) if 'Adj Close' in row else None
                ))
            
            # Cache for 1 hour
            cache.set(cache_key, price_history, 3600)
            
            return price_history
            
        except Exception as e:
            logger.error(f"Error fetching history for {symbol}: {e}")
            return []
    
    def get_real_time_price(self, symbol: str) -> Optional[Decimal]:
        """
        Get real-time price for a stock.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Current price or None
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Try to get the most current price
            fast_info = ticker.fast_info
            if hasattr(fast_info, 'last_price') and fast_info.last_price:
                return Decimal(str(fast_info.last_price))
            
            # Fallback to regular info
            info = ticker.info
            price = info.get('currentPrice') or info.get('regularMarketPrice')
            
            if price:
                return Decimal(str(price))
                
            return None
            
        except Exception as e:
            logger.error(f"Error fetching real-time price for {symbol}: {e}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[Decimal]:
        """
        Get current price for a stock (required by base class).
        
        This is an alias for get_real_time_price to satisfy the abstract method.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Current price or None
        """
        return self.get_real_time_price(symbol)

    def search_symbols(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Search for stock symbols matching a query.
        
        Args:
            query: Search query
            limit: Maximum results to return
            
        Returns:
            List of dictionaries with symbol and name
        """
        try:
            # Note: yfinance doesn't have a direct search API
            # This is a simple implementation that checks if a symbol exists
            # In production, you might want to use a different API for search
            
            ticker = yf.Ticker(query.upper())
            info = ticker.info
            
            if info and 'symbol' in info:
                return [{
                    'symbol': info.get('symbol', query.upper()),
                    'name': info.get('longName') or info.get('shortName', 'Unknown'),
                    'exchange': info.get('exchange', ''),
                    'type': info.get('quoteType', 'EQUITY')
                }]
            
            return []
            
        except Exception as e:
            logger.error(f"Error searching for {query}: {e}")
            return []
    
    def get_market_status(self) -> Dict[str, Any]:
        """
        Get current market status.
        
        Returns:
            Dictionary with market status information
        """
        try:
            # Check major indices
            indices = {
                '^GSPC': 'S&P 500',
                '^DJI': 'Dow Jones',
                '^IXIC': 'NASDAQ',
                '^VIX': 'VIX'
            }
            
            status = {
                'timestamp': timezone.now(),
                'indices': {}
            }
            
            for symbol, name in indices.items():
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                if info:
                    status['indices'][name] = {
                        'symbol': symbol,
                        'price': info.get('regularMarketPrice'),
                        'change': info.get('regularMarketChange'),
                        'change_percent': info.get('regularMarketChangePercent'),
                        'previous_close': info.get('previousClose')
                    }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting market status: {e}")
            return {'error': str(e)}
    
    def _safe_decimal(self, value: Any) -> Optional[Decimal]:
        """Convert value to Decimal safely."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except:
            return None
    
    def _safe_float(self, value: Any) -> Optional[float]:
        """Convert value to float safely."""
        if value is None:
            return None
        try:
            return float(value)
        except:
            return None
    
    def validate_connection(self) -> bool:
        """
        Validate that Yahoo Finance connection is working.
        
        Returns:
            True if connection is valid
        """
        try:
            # Test with a known symbol
            ticker = yf.Ticker('SPY')
            info = ticker.info
            return bool(info and 'symbol' in info)
        except Exception as e:
            logger.error(f"Yahoo Finance connection validation failed: {e}")
            return False