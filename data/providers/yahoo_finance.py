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
from django.conf import settings

from .base import (
    BaseDataProvider, StockInfo, PriceData, 
    DataProviderError, ValidationError
)

logger = logging.getLogger(__name__)


class YahooFinanceProvider(BaseDataProvider):
    """
    Yahoo Finance implementation of BaseDataProvider.
    
    Provides stock data using the yfinance library with rate limiting
    and comprehensive error handling.
    """
    
    def __init__(self):
        super().__init__(rate_limit_calls_per_minute=30)  # Conservative rate limit
        self.timeout = getattr(settings, 'YAHOO_FINANCE_TIMEOUT', 30)
    
    def get_stock_info(self, symbol: str) -> StockInfo:
        """Get basic stock information from Yahoo Finance."""
        try:
            def _fetch_info():
                ticker = yf.Ticker(symbol.upper())
                return ticker.info
            
            info = self._make_api_call(_fetch_info)
            
            if not info or 'symbol' not in info:
                raise DataProviderError(f"No data found for symbol: {symbol}")
            
            return StockInfo(
                symbol=info.get('symbol', symbol.upper()),
                name=info.get('longName', info.get('shortName', '')),
                sector=info.get('sector'),
                exchange=info.get('exchange'),
                currency=info.get('currency', 'USD'),
                market_cap=info.get('marketCap'),
                current_price=self._safe_decimal(info.get('regularMarketPrice')),
                target_price=self._safe_decimal(info.get('targetMeanPrice')),
                last_updated=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get stock info for {symbol}: {e}")
            raise DataProviderError(f"Failed to get stock info for {symbol}: {e}")
    
    def get_price_history(self, symbol: str, start_date: datetime, 
                         end_date: Optional[datetime] = None) -> List[PriceData]:
        """Get historical price data from Yahoo Finance."""
        if end_date is None:
            end_date = datetime.now()
        
        try:
            def _fetch_history():
                ticker = yf.Ticker(symbol.upper())
                # Removed 'threads' parameter for compatibility
                return ticker.history(
                    start=start_date.date(),
                    end=end_date.date(),
                    auto_adjust=False,
                    prepost=False
                )
            
            hist_data = self._make_api_call(_fetch_history)
            
            if hist_data.empty:
                raise DataProviderError(f"No historical data found for {symbol}")
            
            price_data = []
            for date, row in hist_data.iterrows():
                try:
                    data = PriceData(
                        symbol=symbol.upper(),
                        date=date.to_pydatetime() if hasattr(date, 'to_pydatetime') else date,
                        open_price=self._safe_decimal(row['Open']),
                        high_price=self._safe_decimal(row['High']),
                        low_price=self._safe_decimal(row['Low']),
                        close_price=self._safe_decimal(row['Close']),
                        adjusted_close=self._safe_decimal(row['Adj Close']),
                        volume=int(row['Volume']) if pd.notna(row['Volume']) else 0
                    )
                    
                    # Validate each price data point
                    validated_data = self._validate_price_data(data)
                    price_data.append(validated_data)
                    
                except (ValidationError, ValueError) as e:
                    self.logger.warning(f"Skipping invalid data for {symbol} on {date}: {e}")
                    continue
            
            if not price_data:
                raise DataProviderError(f"No valid price data found for {symbol}")
            
            return sorted(price_data, key=lambda x: x.date)
            
        except Exception as e:
            self.logger.error(f"Failed to get price history for {symbol}: {e}")
            raise DataProviderError(f"Failed to get price history for {symbol}: {e}")
    
    def get_current_price(self, symbol: str) -> Decimal:
        """Get current price from Yahoo Finance."""
        try:
            def _fetch_current():
                ticker = yf.Ticker(symbol.upper())
                return ticker.info
            
            info = self._make_api_call(_fetch_current)
            
            # Try different price fields
            price_fields = ['regularMarketPrice', 'currentPrice', 'price', 'previousClose']
            for field in price_fields:
                price = info.get(field)
                if price is not None:
                    return self._safe_decimal(price)
            
            raise DataProviderError(f"No current price available for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Failed to get current price for {symbol}: {e}")
            raise DataProviderError(f"Failed to get current price for {symbol}: {e}")
    
    def search_stocks(self, query: str) -> List[Dict[str, str]]:
        """Search for stocks using Yahoo Finance."""
        # Yahoo Finance doesn't have a direct search API through yfinance
        # This is a simplified implementation
        # In a production environment, you might use a different service or API
        
        results = []
        
        # Try the query as a direct symbol lookup
        try:
            stock_info = self.get_stock_info(query)
            results.append({
                'symbol': stock_info.symbol,
                'name': stock_info.name
            })
        except DataProviderError:
            pass
        
        return results
    
    def validate_symbol(self, symbol: str) -> bool:
        """Validate symbol by attempting to fetch basic info."""
        try:
            self.get_stock_info(symbol)
            return True
        except DataProviderError:
            return False
    
    def _safe_decimal(self, value: Any) -> Optional[Decimal]:
        """Safely convert value to Decimal."""
        if value is None or pd.isna(value):
            return None
        
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
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
            except DataProviderError as e:
                self.logger.warning(f"Failed to get info for {symbol}: {e}")
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