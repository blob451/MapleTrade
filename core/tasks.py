"""
Celery tasks for cache management and background operations.

These tasks handle automated cache warming, cleanup, and maintenance
to ensure optimal performance.
"""

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from .cache import CacheWarmer, CacheManager
from .models import Stock, Sector

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def warm_popular_stocks_task(self, symbols=None):
    """
    Celery task to warm cache for popular stocks.
    
    Args:
        symbols: List of stock symbols to warm (optional)
        
    Returns:
        Dictionary with warming results
    """
    try:
        if symbols is None:
            symbols = CacheWarmer.get_popular_stocks()
        
        logger.info(f"Starting cache warming for {len(symbols)} stocks")
        results = CacheWarmer.warm_popular_stocks(symbols)
        
        successful = sum(1 for success in results.values() if success)
        failed = len(results) - successful
        
        logger.info(f"Cache warming completed: {successful} successful, {failed} failed")
        
        return {
            'task': 'warm_popular_stocks',
            'symbols_count': len(symbols),
            'successful': successful,
            'failed': failed,
            'results': results,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Cache warming failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def warm_sector_etfs_task(self):
    """
    Celery task to warm cache for sector ETFs.
    
    Returns:
        Dictionary with warming results
    """
    try:
        logger.info("Starting sector ETF cache warming")
        results = CacheWarmer.warm_sector_etfs()
        
        successful = sum(1 for success in results.values() if success)
        failed = len(results) - successful
        
        logger.info(f"Sector ETF cache warming completed: {successful} successful, {failed} failed")
        
        return {
            'task': 'warm_sector_etfs',
            'etfs_count': len(results),
            'successful': successful,
            'failed': failed,
            'results': results,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Sector ETF cache warming failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=2)
def warm_user_portfolio_stocks_task(self):
    """
    Celery task to warm cache for stocks in user portfolios.
    
    Returns:
        Dictionary with warming results
    """
    try:
        # Get unique stocks from user portfolios
        user_stocks = Stock.objects.filter(
            portfoliostock__isnull=False
        ).distinct().values_list('symbol', flat=True)
        
        user_stock_symbols = list(user_stocks)
        
        if not user_stock_symbols:
            logger.info("No stocks found in user portfolios")
            return {
                'task': 'warm_user_portfolio_stocks',
                'symbols_count': 0,
                'successful': 0,
                'failed': 0,
                'message': 'No user portfolio stocks found',
                'timestamp': timezone.now().isoformat()
            }
        
        logger.info(f"Starting cache warming for {len(user_stock_symbols)} user portfolio stocks")
        results = CacheWarmer.warm_popular_stocks(user_stock_symbols)
        
        successful = sum(1 for success in results.values() if success)
        failed = len(results) - successful
        
        logger.info(f"User portfolio cache warming completed: {successful} successful, {failed} failed")
        
        return {
            'task': 'warm_user_portfolio_stocks',
            'symbols_count': len(user_stock_symbols),
            'successful': successful,
            'failed': failed,
            'results': results,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"User portfolio cache warming failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def comprehensive_cache_warming_task():
    """
    Comprehensive cache warming task that combines all warming strategies.
    
    This task is designed to be run periodically (e.g., every 30 minutes)
    to maintain optimal cache performance.
    
    Returns:
        Dictionary with comprehensive warming results
    """
    start_time = timezone.now()
    
    try:
        logger.info("Starting comprehensive cache warming")
        
        # Run all warming tasks
        popular_result = warm_popular_stocks_task.delay()
        sector_result = warm_sector_etfs_task.delay()
        user_result = warm_user_portfolio_stocks_task.delay()
        
        # Wait for all tasks to complete (with timeout)
        popular_data = popular_result.get(timeout=300)  # 5 minutes
        sector_data = sector_result.get(timeout=300)
        user_data = user_result.get(timeout=300)
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        # Aggregate results
        total_successful = (
            popular_data.get('successful', 0) + 
            sector_data.get('successful', 0) + 
            user_data.get('successful', 0)
        )
        total_failed = (
            popular_data.get('failed', 0) + 
            sector_data.get('failed', 0) + 
            user_data.get('failed', 0)
        )
        
        result = {
            'task': 'comprehensive_cache_warming',
            'duration_seconds': duration,
            'total_successful': total_successful,
            'total_failed': total_failed,
            'popular_stocks': popular_data,
            'sector_etfs': sector_data,
            'user_portfolio_stocks': user_data,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(f"Comprehensive cache warming completed in {duration:.2f}s: "
                   f"{total_successful} successful, {total_failed} failed")
        
        return result
        
    except Exception as exc:
        logger.error(f"Comprehensive cache warming failed: {exc}")
        return {
            'task': 'comprehensive_cache_warming',
            'error': str(exc),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def cache_cleanup_task():
    """
    Periodic cache cleanup task to remove stale entries and optimize performance.
    
    This task should be run daily to maintain cache health.
    
    Returns:
        Dictionary with cleanup results
    """
    try:
        logger.info("Starting cache cleanup")
        
        # Get cache statistics before cleanup
        stats_before = CacheManager.get_cache_stats()
        
        # Clear old analysis results (older than their TTL)
        # Note: Redis automatically handles TTL expiry, but we can do additional cleanup here
        
        # Log cleanup completion
        stats_after = CacheManager.get_cache_stats()
        
        result = {
            'task': 'cache_cleanup',
            'stats_before': stats_before,
            'stats_after': stats_after,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info("Cache cleanup completed")
        return result
        
    except Exception as exc:
        logger.error(f"Cache cleanup failed: {exc}")
        return {
            'task': 'cache_cleanup',
            'error': str(exc),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def cache_health_check_task():
    """
    Health check task for cache systems.
    
    Returns:
        Dictionary with health check results
    """
    try:
        logger.info("Starting cache health check")
        
        # Test each cache type
        health_results = {}
        cache_types = [
            CacheManager.MARKET_DATA,
            CacheManager.ANALYSIS_RESULTS,
            CacheManager.USER_SESSIONS,
            CacheManager.DEFAULT
        ]
        
        for cache_type in cache_types:
            try:
                # Test cache read/write
                test_key = f"health_check_{cache_type}_{timezone.now().timestamp()}"
                test_value = "health_check_value"
                
                cache_instance = CacheManager.get_cache(cache_type)
                cache_instance.set(test_key, test_value, 60)  # 1 minute TTL
                retrieved_value = cache_instance.get(test_key)
                
                health_results[cache_type] = {
                    'status': 'healthy' if retrieved_value == test_value else 'unhealthy',
                    'read_write_test': 'passed' if retrieved_value == test_value else 'failed',
                    'timestamp': timezone.now().isoformat()
                }
                
                # Clean up test key
                cache_instance.delete(test_key)
                
            except Exception as e:
                health_results[cache_type] = {
                    'status': 'unhealthy',
                    'error': str(e),
                    'timestamp': timezone.now().isoformat()
                }
        
        # Overall health status
        overall_healthy = all(
            result.get('status') == 'healthy' 
            for result in health_results.values()
        )
        
        result = {
            'task': 'cache_health_check',
            'overall_status': 'healthy' if overall_healthy else 'unhealthy',
            'cache_results': health_results,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(f"Cache health check completed: {result['overall_status']}")
        return result
        
    except Exception as exc:
        logger.error(f"Cache health check failed: {exc}")
        return {
            'task': 'cache_health_check',
            'overall_status': 'unhealthy',
            'error': str(exc),
            'timestamp': timezone.now().isoformat()
        }