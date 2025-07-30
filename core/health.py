"""
Health check endpoints and utilities for MapleTrade.

This module provides comprehensive health checks for all system components
including database, cache, external APIs, and overall system status.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple

from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from .exceptions import ServiceUnavailableError, DatabaseError
from data.providers import YahooFinanceProvider, DataProviderError

logger = logging.getLogger('mapletrade.health')


class HealthChecker:
    """
    Comprehensive health checking for all system components.
    """
    
    def __init__(self):
        self.checks = {
            'database': self._check_database,
            'cache': self._check_cache,
            'yahoo_finance': self._check_yahoo_finance,
            'disk_space': self._check_disk_space,
            'memory': self._check_memory,
        }
    
    def run_all_checks(self) -> Dict[str, Any]:
        """
        Run all health checks and return comprehensive status.
        
        Returns:
            Dictionary with overall status and individual check results
        """
        start_time = time.time()
        results = {
            'timestamp': timezone.now().isoformat(),
            'overall_status': 'healthy',
            'checks': {},
            'metadata': {
                'version': getattr(settings, 'VERSION', '1.0.0'),
                'environment': getattr(settings, 'DJANGO_ENV', 'development'),
                'debug_mode': settings.DEBUG,
            }
        }
        
        # Run individual checks
        for check_name, check_function in self.checks.items():
            try:
                check_result = check_function()
                results['checks'][check_name] = check_result
                
                # Update overall status if any check fails
                if check_result['status'] != 'healthy':
                    if check_result['status'] == 'critical':
                        results['overall_status'] = 'critical'
                    elif results['overall_status'] == 'healthy':
                        results['overall_status'] = 'degraded'
                        
            except Exception as e:
                logger.error(f"Health check {check_name} failed: {e}")
                results['checks'][check_name] = {
                    'status': 'critical',
                    'message': f"Check failed: {str(e)}",
                    'timestamp': timezone.now().isoformat()
                }
                results['overall_status'] = 'critical'
        
        # Add timing information
        results['response_time_ms'] = round((time.time() - start_time) * 1000, 2)
        
        return results
    
    def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            start_time = time.time()
            
            # Test basic connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
                if result[0] != 1:
                    raise DatabaseError("Database query returned unexpected result")
            
            # Test transaction capability
            from django.db import transaction
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM django_migrations")
                    migration_count = cursor.fetchone()[0]
            
            response_time = round((time.time() - start_time) * 1000, 2)
            
            return {
                'status': 'healthy',
                'message': 'Database is accessible and responsive',
                'response_time_ms': response_time,
                'metadata': {
                    'migration_count': migration_count,
                    'database_name': settings.DATABASES['default']['NAME'],
                    'database_engine': settings.DATABASES['default']['ENGINE']
                },
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'critical',
                'message': f"Database unavailable: {str(e)}",
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_cache(self) -> Dict[str, Any]:
        """Check cache (Redis) connectivity and performance."""
        try:
            start_time = time.time()
            
            # Test cache write/read
            test_key = f"health_check_{int(time.time())}"
            test_value = "health_check_value"
            
            cache.set(test_key, test_value, timeout=60)
            retrieved_value = cache.get(test_key)
            
            if retrieved_value != test_value:
                raise Exception("Cache write/read test failed")
            
            # Clean up test key
            cache.delete(test_key)
            
            response_time = round((time.time() - start_time) * 1000, 2)
            
            # Get cache info if available
            cache_info = {}
            try:
                from django_redis import get_redis_connection
                redis_conn = get_redis_connection("default")
                cache_info = redis_conn.info()
            except Exception:
                pass  # Cache info not critical
            
            return {
                'status': 'healthy',
                'message': 'Cache is accessible and responsive',
                'response_time_ms': response_time,
                'metadata': {
                    'cache_backend': settings.CACHES['default']['BACKEND'],
                    'redis_version': cache_info.get('redis_version', 'unknown'),
                    'connected_clients': cache_info.get('connected_clients', 'unknown')
                },
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return {
                'status': 'degraded',
                'message': f"Cache unavailable: {str(e)}",
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_yahoo_finance(self) -> Dict[str, Any]:
        """Check Yahoo Finance API connectivity."""
        try:
            start_time = time.time()
            
            provider = YahooFinanceProvider()
            
            # Test with a reliable symbol
            test_symbol = "AAPL"
            stock_info = provider.get_stock_info(test_symbol)
            
            if not stock_info or not stock_info.symbol:
                raise DataProviderError("Yahoo Finance returned invalid data")
            
            response_time = round((time.time() - start_time) * 1000, 2)
            
            return {
                'status': 'healthy',
                'message': 'Yahoo Finance API is accessible',
                'response_time_ms': response_time,
                'metadata': {
                    'test_symbol': test_symbol,
                    'provider': 'YahooFinanceProvider'
                },
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.warning(f"Yahoo Finance health check failed: {e}")
            return {
                'status': 'degraded',
                'message': f"Yahoo Finance API issues: {str(e)}",
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space."""
        try:
            import shutil
            
            # Check disk space for the current directory
            total, used, free = shutil.disk_usage('.')
            
            # Convert to GB
            total_gb = total / (1024**3)
            used_gb = used / (1024**3)
            free_gb = free / (1024**3)
            usage_percent = (used / total) * 100
            
            # Determine status based on free space
            if free_gb < 1.0:  # Less than 1GB free
                status_level = 'critical'
                message = f"Low disk space: {free_gb:.1f}GB free"
            elif free_gb < 5.0:  # Less than 5GB free
                status_level = 'degraded'
                message = f"Limited disk space: {free_gb:.1f}GB free"
            else:
                status_level = 'healthy'
                message = f"Sufficient disk space: {free_gb:.1f}GB free"
            
            return {
                'status': status_level,
                'message': message,
                'metadata': {
                    'total_gb': round(total_gb, 1),
                    'used_gb': round(used_gb, 1),
                    'free_gb': round(free_gb, 1),
                    'usage_percent': round(usage_percent, 1)
                },
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'degraded',
                'message': f"Could not check disk space: {str(e)}",
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_memory(self) -> Dict[str, Any]:
        """Check memory usage."""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            
            # Convert to GB
            total_gb = memory.total / (1024**3)
            available_gb = memory.available / (1024**3)
            used_gb = memory.used / (1024**3)
            usage_percent = memory.percent
            
            # Determine status based on memory usage
            if usage_percent > 90:
                status_level = 'critical'
                message = f"High memory usage: {usage_percent:.1f}%"
            elif usage_percent > 80:
                status_level = 'degraded'
                message = f"Elevated memory usage: {usage_percent:.1f}%"
            else:
                status_level = 'healthy'
                message = f"Normal memory usage: {usage_percent:.1f}%"
            
            return {
                'status': status_level,
                'message': message,
                'metadata': {
                    'total_gb': round(total_gb, 1),
                    'used_gb': round(used_gb, 1),
                    'available_gb': round(available_gb, 1),
                    'usage_percent': round(usage_percent, 1)
                },
                'timestamp': timezone.now().isoformat()
            }
            
        except ImportError:
            return {
                'status': 'healthy',
                'message': 'Memory monitoring not available (psutil not installed)',
                'timestamp': timezone.now().isoformat()
            }
        except Exception as e:
            return {
                'status': 'degraded',
                'message': f"Could not check memory: {str(e)}",
                'timestamp': timezone.now().isoformat()
            }


# Health Check Views
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Comprehensive health check endpoint.
    
    Returns detailed status of all system components.
    """
    checker = HealthChecker()
    health_data = checker.run_all_checks()
    
    # Determine HTTP status code based on overall health
    if health_data['overall_status'] == 'healthy':
        status_code = status.HTTP_200_OK
    elif health_data['overall_status'] == 'degraded':
        status_code = status.HTTP_200_OK  # Still functional
    else:  # critical
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return JsonResponse(health_data, status=status_code)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check_simple(request):
    """
    Simple health check endpoint for load balancers.
    
    Returns minimal response for quick health verification.
    """
    try:
        # Quick database check
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
        if result[0] == 1:
            return JsonResponse({
                'status': 'healthy',
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
        else:
            raise Exception("Database check failed")
            
    except Exception as e:
        logger.error(f"Simple health check failed: {e}")
        return JsonResponse({
            'status': 'unhealthy',
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([AllowAny])
def readiness_check(request):
    """
    Readiness check for Kubernetes deployments.
    
    Verifies that the application is ready to serve requests.
    """
    checker = HealthChecker()
    
    # Check critical components only
    critical_checks = ['database', 'cache']
    ready = True
    
    for check_name in critical_checks:
        try:
            check_function = checker.checks[check_name]
            result = check_function()
            if result['status'] == 'critical':
                ready = False
                break
        except Exception:
            ready = False
            break
    
    if ready:
        return JsonResponse({
            'status': 'ready',
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)
    else:
        return JsonResponse({
            'status': 'not_ready',
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([AllowAny])
def liveness_check(request):
    """
    Liveness check for Kubernetes deployments.
    
    Verifies that the application is alive and not in a deadlock state.
    """
    # Simple check that the application is responsive
    return JsonResponse({
        'status': 'alive',
        'timestamp': timezone.now().isoformat()
    }, status=status.HTTP_200_OK)