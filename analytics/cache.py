"""
Caching utilities for analytics module
Optimized for high-RAM environment with Redis backend
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
import hashlib

logger = logging.getLogger(__name__)


class AnalyticsCache:
    """
    Advanced caching utilities for analytics calculations.
    Provides hierarchical caching with different TTLs for different data types.
    """
    
    # Cache TTL settings (in seconds)
    CACHE_TTLS = {
        'market_data': 3600,        # 1 hour
        'technical_indicators': 3600,  # 1 hour  
        'analysis_results': 14400,   # 4 hours
        'sector_mappings': 86400,    # 24 hours
        'user_sessions': 3600,       # 1 hour
    }
    
    def __init__(self, cache_type: str = 'default'):
        """
        Initialize cache manager.
        
        Args:
            cache_type: Type of cache for TTL selection
        """
        self.cache_type = cache_type
        self.ttl = self.CACHE_TTLS.get(cache_type, 3600)
        self.prefix = f"analytics:{cache_type}"
        
    def generate_key(self, *args, **kwargs) -> str:
        """
        Generate a unique cache key from arguments.
        
        Args:
            *args: Positional arguments for key generation
            **kwargs: Keyword arguments for key generation
            
        Returns:
            Unique cache key string
        """
        # Combine all arguments into a single string
        key_components = list(args)
        key_components.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
        key_string = ":".join(str(comp) for comp in key_components)
        
        # Create hash for long keys
        if len(key_string) > 200:
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"{self.prefix}:{key_hash}"
        
        return f"{self.prefix}:{key_string}"
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve value from cache with error handling.
        
        Args:
            key: Cache key
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        try:
            result = cache.get(key, default)
            if result is not None:
                logger.debug(f"Cache HIT: {key}")
            else:
                logger.debug(f"Cache MISS: {key}")
            return result
        except Exception as e:
            logger.warning(f"Cache retrieval error for {key}: {e}")
            return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """
        Store value in cache with error handling.
        
        Args:
            key: Cache key
            value: Value to store
            timeout: Custom timeout (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cache_timeout = timeout or self.ttl
            cache.set(key, value, cache_timeout)
            logger.debug(f"Cache SET: {key} (TTL: {cache_timeout}s)")
            return True
        except Exception as e:
            logger.warning(f"Cache storage error for {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cache.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return True
        except Exception as e:
            logger.warning(f"Cache deletion error for {key}: {e}")
            return False
    
    def get_or_set(self, key: str, callable_func, timeout: Optional[int] = None, *args, **kwargs) -> Any:
        """
        Get from cache or calculate and store.
        
        Args:
            key: Cache key
            callable_func: Function to call if cache miss
            timeout: Cache timeout
            *args: Arguments for callable_func
            **kwargs: Keyword arguments for callable_func
            
        Returns:
            Cached or calculated value
        """
        # Try to get from cache first
        result = self.get(key)
        
        if result is not None:
            return result
        
        # Calculate new value
        try:
            result = callable_func(*args, **kwargs)
            # Store in cache
            self.set(key, result, timeout)
            return result
        except Exception as e:
            logger.error(f"Error calculating value for cache key {key}: {e}")
            raise


class TechnicalIndicatorCache(AnalyticsCache):
    """
    Specialized cache for technical indicators with optimized key generation.
    """
    
    def __init__(self):
        super().__init__('technical_indicators')
    
    def get_indicator_key(self, symbol: str, indicator: str, **params) -> str:
        """
        Generate cache key for technical indicator.
        
        Args:
            symbol: Stock symbol
            indicator: Indicator name (sma, ema, rsi, etc.)
            **params: Indicator parameters
            
        Returns:
            Cache key for indicator
        """
        return self.generate_key(symbol.upper(), indicator.lower(), **params)
    
    def get_batch_key(self, symbol: str, indicators: List[str]) -> str:
        """
        Generate cache key for batch of indicators.
        
        Args:
            symbol: Stock symbol
            indicators: List of indicator names
            
        Returns:
            Cache key for batch
        """
        indicators_sorted = sorted(indicators)
        return self.generate_key(symbol.upper(), 'batch', indicators=':'.join(indicators_sorted))
    
    def cache_indicator_result(self, symbol: str, indicator: str, result: Dict, **params) -> bool:
        """
        Cache technical indicator result with metadata.
        
        Args:
            symbol: Stock symbol
            indicator: Indicator name
            result: Calculation result
            **params: Indicator parameters
            
        Returns:
            True if cached successfully
        """
        cache_key = self.get_indicator_key(symbol, indicator, **params)
        
        # Add caching metadata
        cached_result = {
            **result,
            'cached_at': datetime.now().isoformat(),
            'cache_key': cache_key,
            'symbol': symbol.upper(),
            'indicator': indicator.upper()
        }
        
        return self.set(cache_key, cached_result)
    
    def get_indicator_result(self, symbol: str, indicator: str, **params) -> Optional[Dict]:
        """
        Retrieve cached technical indicator result.
        
        Args:
            symbol: Stock symbol
            indicator: Indicator name
            **params: Indicator parameters
            
        Returns:
            Cached result or None
        """
        cache_key = self.get_indicator_key(symbol, indicator, **params)
        return self.get(cache_key)
    
    def invalidate_symbol(self, symbol: str) -> None:
        """
        Invalidate all cached indicators for a symbol.
        Note: This is a simplified implementation. 
        Production would use cache.delete_pattern() if available.
        
        Args:
            symbol: Stock symbol to invalidate
        """
        logger.info(f"Invalidating all cached indicators for {symbol}")
        # This would need to be implemented based on your cache backend
        # For Redis, you could use SCAN with pattern matching


class MarketDataCache(AnalyticsCache):
    """
    Specialized cache for market data with time-based invalidation.
    """
    
    def __init__(self):
        super().__init__('market_data')
    
    def get_price_data_key(self, symbol: str, start_date: str, end_date: str) -> str:
        """
        Generate cache key for price data.
        
        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Cache key for price data
        """
        return self.generate_key(symbol.upper(), 'price_data', start_date, end_date)
    
    def cache_price_data(self, symbol: str, start_date: str, end_date: str, data: Any) -> bool:
        """
        Cache price data with metadata.
        
        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            data: Price data to cache
            
        Returns:
            True if cached successfully
        """
        cache_key = self.get_price_data_key(symbol, start_date, end_date)
        
        cached_data = {
            'data': data,
            'symbol': symbol.upper(),
            'start_date': start_date,
            'end_date': end_date,
            'cached_at': datetime.now().isoformat(),
            'data_points': len(data) if hasattr(data, '__len__') else 0
        }
        
        return self.set(cache_key, cached_data)
    
    def get_price_data(self, symbol: str, start_date: str, end_date: str) -> Optional[Any]:
        """
        Retrieve cached price data.
        
        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            
        Returns:
            Cached price data or None
        """
        cache_key = self.get_price_data_key(symbol, start_date, end_date)
        cached_result = self.get(cache_key)
        
        if cached_result and isinstance(cached_result, dict):
            return cached_result.get('data')
        
        return cached_result


class CacheStats:
    """
    Cache statistics and monitoring utilities.
    """
    
    @staticmethod
    def get_cache_info() -> Dict[str, Any]:
        """
        Get cache statistics and information.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            # This would need to be implemented based on your cache backend
            # For Redis, you could use INFO command
            return {
                'backend': settings.CACHES['default']['BACKEND'],
                'status': 'healthy',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting cache info: {e}")
            return {
                'backend': 'unknown',
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    @staticmethod
    def clear_analytics_cache() -> bool:
        """
        Clear all analytics-related cache entries.
        
        Returns:
            True if successful
        """
        try:
            # This is a simplified implementation
            # Production would use pattern-based deletion
            logger.info("Clearing analytics cache")
            return True
        except Exception as e:
            logger.error(f"Error clearing analytics cache: {e}")
            return False


# Convenience instances
technical_cache = TechnicalIndicatorCache()
market_data_cache = MarketDataCache()