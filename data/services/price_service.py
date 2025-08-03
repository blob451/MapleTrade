"""
Price service for managing historical price data.

This service handles fetching, storing, and analyzing price data.
"""

import logging
from typing import List, Dict, Optional, Tuple, Any  
from datetime import datetime, date, timedelta
from decimal import Decimal

from django.db import transaction, models
from django.utils import timezone
from django.core.cache import cache

from data.models import Stock, PriceData
from data.providers.yahoo_finance import YahooFinanceProvider, PriceHistory
from core.constants import TimeConstants, CacheKeys

logger = logging.getLogger(__name__)


class PriceService:
    """
    Service for managing historical price data.
    
    Provides methods for:
    - Fetching price history
    - Storing price data
    - Calculating price metrics
    - Managing price cache
    """
    
    def __init__(self):
        self.provider = YahooFinanceProvider()
        self.cache_timeout = TimeConstants.CACHE_MARKET_DATA
    
    def get_price_history(
        self, 
        stock: Stock, 
        start_date: date, 
        end_date: date,
        use_cache: bool = True
    ) -> List[PriceData]:
        """
        Get price history for a stock.
        
        Args:
            stock: Stock instance
            start_date: Start date for history
            end_date: End date for history
            use_cache: Whether to use cache
            
        Returns:
            List of PriceData objects
        """
        # Check cache
        if use_cache:
            cache_key = CacheKeys.get_price_data_key(
                stock.symbol, 
                start_date.isoformat(), 
                end_date.isoformat()
            )
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.debug(f"Returning cached price data for {stock.symbol}")
                return cached_data
        
        # Check database
        existing_data = list(
            PriceData.objects.filter(
                stock=stock,
                date__gte=start_date,
                date__lte=end_date
            ).order_by('date')
        )
        
        # Determine if we need to fetch more data
        if existing_data:
            first_date = existing_data[0].date
            last_date = existing_data[-1].date
            
            # Check if we have complete data
            expected_days = (end_date - start_date).days
            actual_days = len(existing_data)
            
            # Rough check (markets aren't open every day)
            if actual_days >= expected_days * 0.7:  # 70% of days (weekends/holidays)
                if first_date <= start_date and last_date >= end_date:
                    logger.debug(f"Using existing price data for {stock.symbol}")
                    if use_cache:
                        cache.set(cache_key, existing_data, self.cache_timeout)
                    return existing_data
        
        # Fetch missing data
        logger.info(f"Fetching price data for {stock.symbol} from {start_date} to {end_date}")
        return self.fetch_and_store_prices(stock, start_date, end_date)
    
    def fetch_and_store_prices(
        self, 
        stock: Stock, 
        start_date: date, 
        end_date: date
    ) -> List[PriceData]:
        """
        Fetch price data from provider and store in database.
        
        Args:
            stock: Stock instance
            start_date: Start date
            end_date: End date
            
        Returns:
            List of PriceData objects
        """
        try:
            # Fetch from provider
            price_history = self.provider.get_price_history(
                stock.symbol,
                datetime.combine(start_date, datetime.min.time()),
                datetime.combine(end_date, datetime.max.time())
            )
            
            if not price_history:
                logger.warning(f"No price data returned for {stock.symbol}")
                return []
            
            # Store in database
            price_objects = []
            
            with transaction.atomic():
                for price_item in price_history:
                    price_data, created = PriceData.objects.update_or_create(
                        stock=stock,
                        date=price_item.date.date(),
                        defaults={
                            'open_price': Decimal(str(price_item.open)),
                            'high_price': Decimal(str(price_item.high)),
                            'low_price': Decimal(str(price_item.low)),
                            'close_price': Decimal(str(price_item.close)),
                            'adjusted_close': Decimal(str(price_item.adjusted_close)) if price_item.adjusted_close else None,
                            'volume': price_item.volume
                        }
                    )
                    price_objects.append(price_data)
            
            logger.info(f"Stored {len(price_objects)} price records for {stock.symbol}")
            
            # Update stock's current price with latest data
            if price_objects:
                latest_price = max(price_objects, key=lambda x: x.date)
                stock.current_price = latest_price.close_price
                stock.save()
            
            # Cache the result
            cache_key = CacheKeys.get_price_data_key(
                stock.symbol,
                start_date.isoformat(),
                end_date.isoformat()
            )
            cache.set(cache_key, price_objects, self.cache_timeout)
            
            return price_objects
            
        except Exception as e:
            logger.error(f"Failed to fetch prices for {stock.symbol}: {e}")
            raise
    
    def get_latest_price(self, stock: Stock) -> Optional[PriceData]:
        """
        Get the most recent price for a stock.
        
        Args:
            stock: Stock instance
            
        Returns:
            Latest PriceData or None
        """
        return PriceData.objects.filter(
            stock=stock
        ).order_by('-date').first()
    
    def get_price_range(
        self, 
        stock: Stock, 
        days: int = 30
    ) -> Dict[str, Optional[Decimal]]:
        """
        Get price range statistics for a period.
        
        Args:
            stock: Stock instance
            days: Number of days to look back
            
        Returns:
            Dictionary with high, low, average prices
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        stats = PriceData.objects.filter(
            stock=stock,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(
            high=models.Max('high_price'),
            low=models.Min('low_price'),
            avg=models.Avg('close_price'),
            first=models.Min('date'),
            last=models.Max('date')
        )
        
        return stats
    
    def calculate_returns(
        self, 
        price_data: List[PriceData]
    ) -> List[Tuple[date, float]]:
        """
        Calculate daily returns from price data.
        
        Args:
            price_data: List of PriceData objects (sorted by date)
            
        Returns:
            List of (date, return) tuples
        """
        if len(price_data) < 2:
            return []
        
        returns = []
        for i in range(1, len(price_data)):
            prev_price = float(price_data[i-1].close_price)
            curr_price = float(price_data[i].close_price)
            
            if prev_price > 0:
                daily_return = (curr_price - prev_price) / prev_price
                returns.append((price_data[i].date, daily_return))
        
        return returns
    
    def calculate_volatility(
        self, 
        stock: Stock, 
        days: int = 30
    ) -> Optional[float]:
        """
        Calculate annualized volatility for a stock.
        
        Args:
            stock: Stock instance
            days: Number of days to calculate over
            
        Returns:
            Annualized volatility or None
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        price_data = list(
            PriceData.objects.filter(
                stock=stock,
                date__gte=start_date,
                date__lte=end_date
            ).order_by('date')
        )
        
        if len(price_data) < 2:
            return None
        
        returns = self.calculate_returns(price_data)
        if not returns:
            return None
        
        # Calculate standard deviation of returns
        return_values = [r[1] for r in returns]
        mean_return = sum(return_values) / len(return_values)
        
        variance = sum((r - mean_return) ** 2 for r in return_values) / len(return_values)
        daily_volatility = variance ** 0.5
        
        # Annualize (252 trading days)
        annual_volatility = daily_volatility * (252 ** 0.5)
        
        return annual_volatility
    
    def bulk_fetch_prices(
        self, 
        stocks: List[Stock], 
        start_date: date, 
        end_date: date
    ) -> Dict[str, Any]:
        """
        Fetch prices for multiple stocks.
        
        Args:
            stocks: List of Stock instances
            start_date: Start date
            end_date: End date
            
        Returns:
            Dictionary with results
        """
        results = {
            'success': [],
            'failed': [],
            'total': len(stocks)
        }
        
        for stock in stocks:
            try:
                prices = self.fetch_and_store_prices(stock, start_date, end_date)
                results['success'].append({
                    'symbol': stock.symbol,
                    'count': len(prices)
                })
            except Exception as e:
                logger.error(f"Failed to fetch prices for {stock.symbol}: {e}")
                results['failed'].append({
                    'symbol': stock.symbol,
                    'error': str(e)
                })
        
        return results
    
    def cleanup_old_prices(self, days_to_keep: int = 365) -> int:
        """
        Remove price data older than specified days.
        
        Args:
            days_to_keep: Number of days of data to keep
            
        Returns:
            Number of records deleted
        """
        cutoff_date = timezone.now().date() - timedelta(days=days_to_keep)
        
        deleted_count, _ = PriceData.objects.filter(
            date__lt=cutoff_date
        ).delete()
        
        logger.info(f"Cleaned up {deleted_count} old price records")
        return deleted_count


# Convenience function
_default_service = None

def get_price_service() -> PriceService:
    """Get singleton instance of PriceService."""
    global _default_service
    if _default_service is None:
        _default_service = PriceService()
    return _default_service