"""
Cache utilities and decorators for MapleTrade.

This module provides sophisticated caching mechanisms for different types
of data with appropriate TTL values and cache warming strategies.
"""

import functools
import hashlib
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from datetime import datetime, timedelta

from django.core.cache import caches, cache
from django.conf import settings
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Central cache manager for different cache types in MapleTrade.
    """
    
    # Cache aliases
    MARKET_DATA = 'market_data'
    ANALYSIS_RESULTS = 'analysis_results'
    USER_SESSIONS = 'user_sessions'
    DEFAULT = 'default'
    
    # Cache TTL values (in seconds)
    TTL_MARKET_DATA = 3600      # 1 hour
    TTL_ANALYSIS = 14400        # 4 hours
    TTL_USER_SESSION = 86400    # 24 hours
    TTL_SHORT = 300             # 5 minutes
    TTL_LONG = 86400           # 24 hours
    
    @classmethod
    def get_cache(cls, cache_type: str):
        """Get specific cache instance."""
        return caches[cache_type]
    
    @classmethod
    def generate_cache_key(cls, prefix: str, *args, **kwargs) -> str:
        """
        Generate a consistent cache key from arguments.
        
        Args:
            prefix: Key prefix (e.g., 'stock_price', 'analysis_result')
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Generated cache key string
        """
        # Create a string representation of all arguments
        key_parts = [str(arg) for arg in args]
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
        key_string = ":".join(key_parts)
        
        # Hash if too long
        if len(key_string) > 200:
            key_string = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"{prefix}:{key_string}"
    
    @classmethod
    def set_market_data(cls, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """Set market data with appropriate TTL."""
        timeout = timeout or cls.TTL_MARKET_DATA
        return cls.get_cache(cls.MARKET_DATA).set(key, value, timeout)
    
    @classmethod
    def get_market_data(cls, key: str, default=None) -> Any:
        """Get market data from cache."""
        return cls.get_cache(cls.MARKET_DATA).get(key, default)
    
    @classmethod
    def set_analysis_result(cls, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """Set analysis result with appropriate TTL."""
        timeout = timeout or cls.TTL_ANALYSIS
        return cls.get_cache(cls.ANALYSIS_RESULTS).set(key, value, timeout)
    
    @classmethod
    def get_analysis_result(cls, key: str, default=None) -> Any:
        """Get analysis result from cache."""
        return cls.get_cache(cls.ANALYSIS_RESULTS).get(key, default)
    
    @classmethod
    def set_user_data(cls, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """Set user-specific data with appropriate TTL."""
        timeout = timeout or cls.TTL_USER_SESSION
        return cls.get_cache(cls.USER_SESSIONS).set(key, value, timeout)
    
    @classmethod
    def get_user_data(cls, key: str, default=None) -> Any:
        """Get user-specific data from cache."""
        return cls.get_cache(cls.USER_SESSIONS).get(key, default)
    
    @classmethod
    def invalidate_pattern(cls, cache_type: str, pattern: str) -> int:
        """
        Invalidate cache keys matching a pattern.
        
        Args:
            cache_type: Cache type to search in
            pattern: Pattern to match (supports wildcards)
            
        Returns:
            Number of keys deleted
        """
        cache_instance = cls.get_cache(cache_type)
        try:
            if hasattr(cache_instance, 'delete_pattern'):
                return cache_instance.delete_pattern(pattern)
            else:
                # Fallback for caches without pattern deletion
                logger.warning(f"Cache {cache_type} doesn't support pattern deletion")
                return 0
        except Exception as e:
            logger.error(f"Failed to invalidate cache pattern {pattern}: {e}")
            return 0
    
    @classmethod
    def clear_cache(cls, cache_type: str) -> bool:
        """Clear entire cache of specified type."""
        try:
            cls.get_cache(cache_type).clear()
            logger.info(f"Cleared cache: {cache_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache {cache_type}: {e}")
            return False
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all cache types."""
        stats = {}
        cache_types = [cls.MARKET_DATA, cls.ANALYSIS_RESULTS, cls.USER_SESSIONS, cls.DEFAULT]
        
        for cache_type in cache_types:
            try:
                cache_instance = cls.get_cache(cache_type)
                # Get basic stats (implementation varies by cache backend)
                stats[cache_type] = {
                    'backend': str(cache_instance.__class__.__name__),
                    'location': getattr(cache_instance, '_server', 'Unknown'),
                }
            except Exception as e:
                stats[cache_type] = {'error': str(e)}
        
        return stats


def cache_market_data(timeout: Optional[int] = None, key_prefix: str = 'market'):
    """
    Decorator for caching market data with 1-hour TTL.
    
    Args:
        timeout: Custom timeout in seconds (defaults to 1 hour)
        key_prefix: Prefix for cache key generation
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = CacheManager.generate_cache_key(
                key_prefix, 
                func.__name__, 
                *args, 
                **kwargs
            )
            
            # Try to get from cache
            cached_result = CacheManager.get_market_data(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache HIT for market data: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            logger.debug(f"Cache MISS for market data: {cache_key}")
            result = func(*args, **kwargs)
            
            if result is not None:
                CacheManager.set_market_data(cache_key, result, timeout)
                logger.debug(f"Cached market data: {cache_key}")
            
            return result
        return wrapper
    return decorator


def cache_analysis_result(timeout: Optional[int] = None, key_prefix: str = 'analysis'):
    """
    Decorator for caching analysis results with 4-hour TTL.
    
    Args:
        timeout: Custom timeout in seconds (defaults to 4 hours)
        key_prefix: Prefix for cache key generation
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = CacheManager.generate_cache_key(
                key_prefix,
                func.__name__,
                *args,
                **kwargs
            )
            
            # Try to get from cache
            cached_result = CacheManager.get_analysis_result(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache HIT for analysis: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            logger.debug(f"Cache MISS for analysis: {cache_key}")
            result = func(*args, **kwargs)
            
            if result is not None:
                CacheManager.set_analysis_result(cache_key, result, timeout)
                logger.debug(f"Cached analysis result: {cache_key}")
            
            return result
        return wrapper
    return decorator


def cache_user_data(timeout: Optional[int] = None, key_prefix: str = 'user'):
    """
    Decorator for caching user-specific data with 24-hour TTL.
    
    Args:
        timeout: Custom timeout in seconds (defaults to 24 hours)
        key_prefix: Prefix for cache key generation
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = CacheManager.generate_cache_key(
                key_prefix,
                func.__name__,
                *args,
                **kwargs
            )
            
            # Try to get from cache
            cached_result = CacheManager.get_user_data(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache HIT for user data: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            logger.debug(f"Cache MISS for user data: {cache_key}")
            result = func(*args, **kwargs)
            
            if result is not None:
                CacheManager.set_user_data(cache_key, result, timeout)
                logger.debug(f"Cached user data: {cache_key}")
            
            return result
        return wrapper
    return decorator


def invalidate_cache_on_update(*cache_patterns: str):
    """
    Decorator to invalidate cache patterns when a function is called.
    Useful for cache invalidation on data updates.
    
    Args:
        *cache_patterns: Cache key patterns to invalidate
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Invalidate specified cache patterns
            for pattern in cache_patterns:
                try:
                    CacheManager.invalidate_pattern(CacheManager.MARKET_DATA, pattern)
                    CacheManager.invalidate_pattern(CacheManager.ANALYSIS_RESULTS, pattern)
                    logger.info(f"Invalidated cache pattern: {pattern}")
                except Exception as e:
                    logger.error(f"Failed to invalidate cache pattern {pattern}: {e}")
            
            return result
        return wrapper
    return decorator


class CacheWarmer:
    """
    Cache warming utility for pre-loading frequently accessed data.
    """
    
    @staticmethod
    def warm_popular_stocks(stock_symbols: List[str]) -> Dict[str, bool]:
        """
        Pre-warm cache for popular stocks.
        
        Args:
            stock_symbols: List of stock symbols to warm
            
        Returns:
            Dictionary of warming results
        """
        from data.providers import YahooFinanceProvider
        from data.validators import DataValidator
        
        provider = YahooFinanceProvider()
        validator = DataValidator()
        results = {}
        
        for symbol in stock_symbols:
            try:
                # Warm stock info
                stock_info = provider.get_stock_info(symbol)
                validated_info = validator.validate_stock_info(stock_info)
                
                cache_key = CacheManager.generate_cache_key('stock_info', symbol)
                CacheManager.set_market_data(cache_key, validated_info)
                
                # Warm recent price data
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)
                price_data = provider.get_price_history(symbol, start_date, end_date)
                
                cache_key = CacheManager.generate_cache_key('price_history', symbol, '30d')
                CacheManager.set_market_data(cache_key, price_data)
                
                results[symbol] = True
                logger.info(f"Cache warmed for {symbol}")
                
            except Exception as e:
                results[symbol] = False
                logger.error(f"Failed to warm cache for {symbol}: {e}")
        
        return results
    
    @staticmethod
    def warm_sector_etfs() -> Dict[str, bool]:
        """Warm cache for sector ETF data."""
        from core.models import Sector
        
        results = {}
        sectors = Sector.objects.all()
        
        for sector in sectors:
            try:
                # Use the warm_popular_stocks method for ETFs
                etf_results = CacheWarmer.warm_popular_stocks([sector.etf_symbol])
                results[sector.etf_symbol] = etf_results.get(sector.etf_symbol, False)
            except Exception as e:
                results[sector.etf_symbol] = False
                logger.error(f"Failed to warm ETF cache for {sector.name}: {e}")
        
        return results
    
    @staticmethod
    def get_popular_stocks() -> List[str]:
        """Get list of popular stocks to warm cache for."""
        # This could be based on user activity, market cap, etc.
        # For now, return a static list of major stocks
        return [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA',
            'NVDA', 'META', 'NFLX', 'ORCL', 'CRM',
            'JPM', 'BAC', 'WFC', 'V', 'MA',
            'JNJ', 'UNH', 'PFE', 'ABBV', 'MRK',
            'XOM', 'CVX', 'COP', 'SLB', 'EOG'
        ]


# Utility functions for specific cache operations
def get_cached_stock_price(symbol: str) -> Optional[Dict]:
    """Get cached stock price data."""
    cache_key = CacheManager.generate_cache_key('stock_price', symbol)
    return CacheManager.get_market_data(cache_key)


def cache_stock_price(symbol: str, price_data: Dict) -> bool:
    """Cache stock price data."""
    cache_key = CacheManager.generate_cache_key('stock_price', symbol)
    return CacheManager.set_market_data(cache_key, price_data)


def get_cached_analysis(symbol: str, period: int, user_id: Optional[int] = None) -> Optional[Dict]:
    """Get cached analysis result."""
    cache_key = CacheManager.generate_cache_key('analysis', symbol, period, user_id or 'anonymous')
    return CacheManager.get_analysis_result(cache_key)


def cache_analysis(symbol: str, period: int, analysis_data: Dict, user_id: Optional[int] = None) -> bool:
    """Cache analysis result."""
    cache_key = CacheManager.generate_cache_key('analysis', symbol, period, user_id or 'anonymous')
    return CacheManager.set_analysis_result(cache_key, analysis_data)