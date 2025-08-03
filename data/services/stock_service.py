"""
Stock service for managing stock data operations.

This service handles all stock-related database operations and
coordinates with external data providers.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.db import models  
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q, Count, Avg, Max

from data.models import Stock, Sector
from data.providers.yahoo_finance import YahooFinanceProvider
from core.constants import TimeConstants, CacheKeys

logger = logging.getLogger(__name__)


class StockService:
    """
    Service class for stock data operations.
    
    This service provides methods for:
    - Creating and updating stocks
    - Fetching stock information
    - Managing stock cache
    - Bulk operations
    """
    
    def __init__(self):
        self.provider = YahooFinanceProvider()
        self.cache_timeout = TimeConstants.CACHE_MARKET_DATA
    
    def get_or_create_stock(self, symbol: str, update_if_stale: bool = True) -> Stock:
        """
        Get existing stock or create new one with fresh data.
        
        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')
            update_if_stale: Whether to update if data is stale
            
        Returns:
            Stock instance
            
        Raises:
            ValueError: If symbol is invalid
            Exception: If provider fails
        """
        if not symbol:
            raise ValueError("Symbol cannot be empty")
            
        symbol = symbol.upper().strip()
        
        try:
            # Check cache first
            cache_key = CacheKeys.get_stock_info_key(symbol)
            cached_stock_id = cache.get(cache_key)
            
            if cached_stock_id:
                try:
                    stock = Stock.objects.get(id=cached_stock_id)
                    if not update_if_stale or not stock.needs_update:
                        logger.debug(f"Returning cached stock: {symbol}")
                        return stock
                except Stock.DoesNotExist:
                    cache.delete(cache_key)
            
            # Try to get from database
            stock = Stock.objects.filter(symbol=symbol).first()
            
            if stock:
                if update_if_stale and stock.needs_update:
                    logger.info(f"Updating stale stock data: {symbol}")
                    stock = self.update_stock_data(stock)
            else:
                logger.info(f"Creating new stock: {symbol}")
                stock = self.create_stock(symbol)
            
            # Cache the stock ID
            cache.set(cache_key, stock.id, self.cache_timeout)
            
            return stock
            
        except Exception as e:
            logger.error(f"Error getting/creating stock {symbol}: {e}")
            raise
    
    def create_stock(self, symbol: str) -> Stock:
        """
        Create a new stock with data from provider.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Created Stock instance
        """
        try:
            # Fetch data from provider
            stock_info = self.provider.get_stock_info(symbol)
            
            if not stock_info:
                raise ValueError(f"No data found for symbol: {symbol}")
            
            # Map sector
            sector = None
            if stock_info.sector:
                sector = self._get_or_create_sector(stock_info.sector)
            
            # Create stock
            with transaction.atomic():
                stock = Stock.objects.create(
                    symbol=stock_info.symbol,
                    name=stock_info.name or f"Unknown ({symbol})",
                    sector=sector,
                    exchange=stock_info.exchange or '',
                    currency=stock_info.currency or 'USD',
                    market_cap=stock_info.market_cap,
                    current_price=stock_info.current_price,
                    target_price=stock_info.target_price,
                    last_updated=timezone.now(),
                    is_active=True
                )
                
            logger.info(f"Created stock: {stock}")
            return stock
            
        except Exception as e:
            logger.error(f"Failed to create stock {symbol}: {e}")
            raise
    
    def update_stock_data(self, stock: Stock) -> Stock:
        """
        Update stock with latest data from provider.
        
        Args:
            stock: Stock instance to update
            
        Returns:
            Updated Stock instance
        """
        try:
            # Fetch fresh data
            stock_info = self.provider.get_stock_info(stock.symbol)
            
            if not stock_info:
                logger.warning(f"No data found for stock update: {stock.symbol}")
                return stock
            
            # Update fields
            with transaction.atomic():
                if stock_info.name and stock_info.name != "Unknown":
                    stock.name = stock_info.name
                
                if stock_info.sector and not stock.sector:
                    stock.sector = self._get_or_create_sector(stock_info.sector)
                
                if stock_info.exchange:
                    stock.exchange = stock_info.exchange
                
                if stock_info.currency:
                    stock.currency = stock_info.currency
                
                if stock_info.market_cap is not None:
                    stock.market_cap = stock_info.market_cap
                
                if stock_info.current_price is not None:
                    stock.current_price = stock_info.current_price
                
                if stock_info.target_price is not None:
                    stock.target_price = stock_info.target_price
                
                stock.last_updated = timezone.now()
                stock.save()
            
            # Clear cache
            cache_key = CacheKeys.get_stock_info_key(stock.symbol)
            cache.delete(cache_key)
            
            logger.info(f"Updated stock: {stock.symbol}")
            return stock
            
        except Exception as e:
            logger.error(f"Failed to update stock {stock.symbol}: {e}")
            raise
    
    def bulk_update_stocks(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Update multiple stocks in batch.
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            Dictionary with results
        """
        results = {
            'updated': [],
            'created': [],
            'failed': [],
            'total': len(symbols)
        }
        
        for symbol in symbols:
            try:
                stock = self.get_or_create_stock(symbol, update_if_stale=True)
                if stock.created_at == stock.updated_at:
                    results['created'].append(symbol)
                else:
                    results['updated'].append(symbol)
            except Exception as e:
                logger.error(f"Failed to process {symbol}: {e}")
                results['failed'].append({
                    'symbol': symbol,
                    'error': str(e)
                })
        
        return results
    
    def search_stocks(self, query: str, limit: int = 10) -> List[Stock]:
        """
        Search stocks by symbol or name.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching stocks
        """
        if not query:
            return []
        
        query = query.strip()
        
        # Search by symbol (exact and prefix) or name (contains)
        stocks = Stock.objects.filter(
            Q(symbol__iexact=query) |
            Q(symbol__istartswith=query) |
            Q(name__icontains=query)
        ).filter(is_active=True).order_by(
            # Exact symbol match first
            models.Case(
                models.When(symbol__iexact=query, then=0),
                default=1
            ),
            'symbol'
        )[:limit]
        
        return list(stocks)
    
    def get_stocks_by_sector(self, sector: Sector) -> List[Stock]:
        """
        Get all active stocks in a sector.
        
        Args:
            sector: Sector instance
            
        Returns:
            List of stocks in the sector
        """
        return list(
            Stock.objects.filter(
                sector=sector,
                is_active=True
            ).order_by('symbol')
        )
    
    def get_stocks_needing_update(self, hours: int = 24) -> List[Stock]:
        """
        Get stocks that haven't been updated recently.
        
        Args:
            hours: Hours since last update
            
        Returns:
            List of stocks needing update
        """
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        return list(
            Stock.objects.filter(
                Q(last_updated__lt=cutoff_time) | Q(last_updated__isnull=True),
                is_active=True
            ).order_by('last_updated', 'symbol')
        )
    
    def get_stock_statistics(self) -> Dict[str, Any]:
        """
        Get overall stock statistics.
        
        Returns:
            Dictionary with statistics
        """
        stats = Stock.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
            with_sector=Count('id', filter=Q(sector__isnull=False)),
            with_target=Count('id', filter=Q(target_price__isnull=False)),
            avg_market_cap=Avg('market_cap'),
            last_update=Max('last_updated')
        )
        
        # Add sector distribution
        sector_dist = Stock.objects.filter(
            is_active=True,
            sector__isnull=False
        ).values('sector__name').annotate(
            count=Count('id')
        ).order_by('-count')
        
        stats['sector_distribution'] = list(sector_dist)
        
        return stats
    
    def deactivate_stock(self, stock: Stock, reason: str = "") -> None:
        """
        Deactivate a stock (soft delete).
        
        Args:
            stock: Stock to deactivate
            reason: Optional reason for deactivation
        """
        stock.is_active = False
        stock.save()
        
        # Clear cache
        cache_key = CacheKeys.get_stock_info_key(stock.symbol)
        cache.delete(cache_key)
        
        logger.info(f"Deactivated stock: {stock.symbol}. Reason: {reason}")
    
    def _get_or_create_sector(self, sector_name: str) -> Optional[Sector]:
        """
        Get or create sector by name.
        
        Args:
            sector_name: Sector name from provider
            
        Returns:
            Sector instance or None
        """
        from .sector_service import SectorService
        
        sector_service = SectorService()
        return sector_service.get_or_create_by_name(sector_name)


# Convenience functions for direct import
_default_service = None

def get_stock_service() -> StockService:
    """Get singleton instance of StockService."""
    global _default_service
    if _default_service is None:
        _default_service = StockService()
    return _default_service