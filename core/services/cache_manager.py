"""
Centralized cache management service.

Provides consistent caching strategies across all services.
"""

import logging
import hashlib
import json
from typing import Any, Optional, List, Dict 
from datetime import timedelta

from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Centralized cache management with consistent key generation
    and invalidation strategies.
    """
    
    # Default cache timeouts (in seconds)
    TIMEOUTS = {
        'stock_info': 300,  # 5 minutes
        'price_data': 3600,  # 1 hour
        'analysis': 14400,  # 4 hours
        'portfolio': 300,  # 5 minutes
        'market_data': 300,  # 5 minutes
        'sector_data': 900,  # 15 minutes
        'user_data': 600,  # 10 minutes
    }
    
    def __init__(self, prefix: str = 'mapletrade'):
        """
        Initialize cache manager.
        
        Args:
            prefix: Global cache key prefix
        """
        self.prefix = prefix
        self.enabled = getattr(settings, 'CACHE_ENABLED', True)
    
    def _make_key(self, key: str) -> str:
        """Generate cache key with prefix."""
        return f"{self.prefix}:{key}"
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        if not self.enabled:
            return default
        
        full_key = self._make_key(key)
        
        try:
            value = cache.get(full_key, default)
            if value != default:
                logger.debug(f"Cache hit: {key}")
            return value
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None, 
            category: Optional[str] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            timeout: Timeout in seconds (None = use category default)
            category: Category for default timeout
            
        Returns:
            Success status
        """
        if not self.enabled:
            return True
        
        full_key = self._make_key(key)
        
        # Determine timeout
        if timeout is None and category:
            timeout = self.TIMEOUTS.get(category, 3600)
        elif timeout is None:
            timeout = 3600  # Default 1 hour
        
        try:
            cache.set(full_key, value, timeout)
            logger.debug(f"Cache set: {key} (timeout: {timeout}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Success status
        """
        if not self.enabled:
            return True
        
        full_key = self._make_key(key)
        
        try:
            cache.delete(full_key)
            logger.debug(f"Cache delete: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.
        
        Args:
            pattern: Pattern to match (supports * wildcard)
            
        Returns:
            Number of keys deleted
        """
        if not self.enabled:
            return 0
        
        try:
            # This is backend-specific
            # For Redis backend with django-redis
            if hasattr(cache, 'delete_pattern'):
                full_pattern = self._make_key(pattern)
                deleted = cache.delete_pattern(full_pattern)
                logger.debug(f"Cache delete pattern: {pattern} ({deleted} keys)")
                return deleted
            else:
                logger.warning("Cache backend doesn't support delete_pattern")
                return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            return 0
    
    def clear_all(self) -> bool:
        """
        Clear entire cache.
        
        Returns:
            Success status
        """
        if not self.enabled:
            return True
        
        try:
            cache.clear()
            logger.info("Cache cleared")
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
    
    def get_or_set(self, key: str, callable: Any, timeout: Optional[int] = None,
                   category: Optional[str] = None) -> Any:
        """
        Get from cache or compute and set.
        
        Args:
            key: Cache key
            callable: Function to call if not cached
            timeout: Cache timeout
            category: Category for default timeout
            
        Returns:
            Cached or computed value
        """
        value = self.get(key)
        
        if value is None:
            value = callable()
            if value is not None:
                self.set(key, value, timeout, category)
        
        return value
    
    def invalidate_stock(self, symbol: str) -> None:
        """Invalidate all cache entries for a stock."""
        patterns = [
            f"stock_info_{symbol}",
            f"price_data_{symbol}_*",
            f"analysis_{symbol}_*",
            f"technical_{symbol}_*",
        ]
        
        for pattern in patterns:
            self.delete_pattern(pattern)
        
        logger.info(f"Invalidated cache for stock: {symbol}")
    
    def invalidate_portfolio(self, portfolio_id: int) -> None:
        """Invalidate all cache entries for a portfolio."""
        patterns = [
            f"portfolio_{portfolio_id}_*",
            f"portfolio_summary_{portfolio_id}",
            f"portfolio_analysis_{portfolio_id}_*",
        ]
        
        for pattern in patterns:
            self.delete_pattern(pattern)
        
        logger.info(f"Invalidated cache for portfolio: {portfolio_id}")
    
    def invalidate_user(self, user_id: int) -> None:
        """Invalidate all cache entries for a user."""
        patterns = [
            f"user_{user_id}_*",
            f"user_portfolios_{user_id}",
            f"user_analysis_{user_id}_*",
        ]
        
        for pattern in patterns:
            self.delete_pattern(pattern)
        
        logger.info(f"Invalidated cache for user: {user_id}")
    
    def generate_cache_key(self, *args, **kwargs) -> str:
        """
        Generate a consistent cache key from arguments.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Generated cache key
        """
        # Create a string representation
        key_parts = [str(arg) for arg in args]
        
        # Add sorted kwargs
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        
        # Create hash for long keys
        key_string = ":".join(key_parts)
        
        if len(key_string) > 200:
            # Use hash for long keys
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"hash_{key_hash}"
        
        return key_string
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Cache statistics if available
        """
        stats = {
            'enabled': self.enabled,
            'backend': settings.CACHES['default']['BACKEND']
        }
        
        # Try to get backend-specific stats
        try:
            if hasattr(cache, 'get_stats'):
                stats.update(cache.get_stats())
            elif hasattr(cache, '_cache') and hasattr(cache._cache, 'get_stats'):
                stats.update(cache._cache.get_stats())
        except Exception as e:
            logger.warning(f"Could not get cache stats: {e}")
        
        return stats