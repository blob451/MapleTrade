"""
Mock data provider for testing when Yahoo Finance is rate limited.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import random
import logging
from django.utils import timezone  # Add this import

from .base import BaseDataProvider, StockInfo, PriceData, DataProviderError

logger = logging.getLogger(__name__)


class MockDataProvider(BaseDataProvider):
    """
    Mock data provider that generates realistic-looking data for testing.
    """
    
    def __init__(self):
        super().__init__(rate_limit_calls_per_minute=1000)  # No real rate limit
        
        # Mock company data
        self.mock_stocks = {
            'AAPL': {
                'name': 'Apple Inc.',
                'sector': 'Technology',
                'base_price': 180.0,
                'volatility': 0.35,
                'target_price': 195.0
            },
            'MSFT': {
                'name': 'Microsoft Corporation',
                'sector': 'Technology',
                'base_price': 420.0,
                'volatility': 0.28,
                'target_price': 450.0
            },
            'GOOGL': {
                'name': 'Alphabet Inc.',
                'sector': 'Communication Services',
                'base_price': 170.0,
                'volatility': 0.32,
                'target_price': 185.0
            },
            'AMZN': {
                'name': 'Amazon.com Inc.',
                'sector': 'Consumer Discretionary',
                'base_price': 185.0,
                'volatility': 0.38,
                'target_price': 200.0
            },
            'TSLA': {
                'name': 'Tesla Inc.',
                'sector': 'Consumer Discretionary',
                'base_price': 250.0,
                'volatility': 0.55,
                'target_price': 275.0
            },
            'SPY': {
                'name': 'SPDR S&P 500 ETF',
                'sector': 'ETF',
                'base_price': 550.0,
                'volatility': 0.18,
                'target_price': 560.0
            },
            'XLK': {
                'name': 'Technology Select Sector SPDR',
                'sector': 'ETF',
                'base_price': 195.0,
                'volatility': 0.22,
                'target_price': 200.0
            }
        }
    
    def get_stock_info(self, symbol: str) -> StockInfo:
        """Get mock stock information."""
        symbol = symbol.upper()
        
        if symbol not in self.mock_stocks:
            raise DataProviderError(f"Symbol {symbol} not found in mock data")
        
        mock_data = self.mock_stocks[symbol]
        
        # Add some random variation to current price
        variation = random.uniform(-0.02, 0.02)  # +/- 2%
        current_price = mock_data['base_price'] * (1 + variation)
        
        return StockInfo(
            symbol=symbol,
            name=mock_data['name'],
            sector=mock_data['sector'] if mock_data['sector'] != 'ETF' else None,
            exchange='NASDAQ',
            currency='USD',
            market_cap=random.randint(100_000_000_000, 3_000_000_000_000),
            current_price=Decimal(str(current_price)),
            target_price=Decimal(str(mock_data['target_price'])),
            last_updated=timezone.now()  # Changed from datetime.now()
        )
    
    def get_price_history(self, symbol: str, start_date: datetime, 
                         end_date: Optional[datetime] = None) -> List[PriceData]:
        """Generate mock price history."""
        if end_date is None:
            end_date = timezone.now()
        
        # Ensure dates are timezone-aware
        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)
        
        symbol = symbol.upper()
        if symbol not in self.mock_stocks:
            raise DataProviderError(f"Symbol {symbol} not found in mock data")
        
        mock_data = self.mock_stocks[symbol]
        base_price = mock_data['base_price']
        volatility = mock_data['volatility']
        
        # Generate daily prices
        current_date = start_date
        prices = []
        current_price = base_price
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                # Random walk with drift
                daily_return = random.gauss(0.0003, volatility / 16)  # Daily volatility
                current_price *= (1 + daily_return)
                
                # Generate OHLC data
                daily_vol = volatility / 32
                open_price = current_price * (1 + random.gauss(0, daily_vol))
                high_price = max(open_price, current_price) * (1 + abs(random.gauss(0, daily_vol)))
                low_price = min(open_price, current_price) * (1 - abs(random.gauss(0, daily_vol)))
                close_price = current_price
                
                prices.append(PriceData(
                    symbol=symbol,
                    date=current_date,
                    open_price=Decimal(str(open_price)),
                    high_price=Decimal(str(high_price)),
                    low_price=Decimal(str(low_price)),
                    close_price=Decimal(str(close_price)),
                    adjusted_close=Decimal(str(close_price)),
                    volume=random.randint(10_000_000, 100_000_000)
                ))
            
            current_date += timedelta(days=1)
        
        return prices
    
    def get_current_price(self, symbol: str) -> Decimal:
        """Get mock current price."""
        info = self.get_stock_info(symbol)
        return info.current_price
    
    def search_stocks(self, query: str) -> List[Dict[str, str]]:
        """Search mock stocks."""
        query = query.upper()
        results = []
        
        for symbol, data in self.mock_stocks.items():
            if query in symbol or query in data['name'].upper():
                results.append({
                    'symbol': symbol,
                    'name': data['name']
                })
        
        return results
    
    def validate_symbol(self, symbol: str) -> bool:
        """Check if symbol exists in mock data."""
        return symbol.upper() in self.mock_stocks