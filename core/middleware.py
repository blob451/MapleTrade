"""
Error handling middleware for MapleTrade application.

This middleware provides comprehensive error handling, logging,
and standardized error responses for the entire application.
"""

import logging
import traceback
from django.http import JsonResponse
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response

from .exceptions import (
    MapleTradeBaseException, DataProviderError, AnalysisError,
    ValidationError as CustomValidationError, RateLimitError
)

logger = logging.getLogger('mapletrade.middleware')


class ErrorHandlingMiddleware(MiddlewareMixin):
    """
    Comprehensive error handling middleware for MapleTrade.
    
    This middleware catches unhandled exceptions and provides
    consistent error responses and logging.
    """
    
    def process_exception(self, request, exception):
        """
        Process any unhandled exception and return appropriate response.
        
        Args:
            request: Django request object
            exception: The exception that was raised
            
        Returns:
            JsonResponse with error details or None to continue normal processing
        """
        # Log the exception with full traceback
        self._log_exception(request, exception)
        
        # Handle different types of exceptions
        if isinstance(exception, MapleTradeBaseException):
            return self._handle_mapletrade_exception(request, exception)
        elif isinstance(exception, ValidationError):
            return self._handle_validation_error(request, exception)
        elif settings.DEBUG:
            # In debug mode, let Django handle the exception normally
            return None
        else:
            # In production, return a generic error response
            return self._handle_generic_error(request, exception)
    
    def _log_exception(self, request, exception):
        """Log exception details with request context."""
        extra_context = {
            'request_path': request.path,
            'request_method': request.method,
            'user': getattr(request, 'user', 'Anonymous'),
            'remote_addr': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown'),
        }
        
        if isinstance(exception, MapleTradeBaseException):
            # Log MapleTrade exceptions at appropriate level
            if exception.severity == 'critical':
                logger.critical(
                    f"Critical error: {exception}",
                    extra=extra_context,
                    exc_info=True
                )
            elif exception.severity == 'high':
                logger.error(
                    f"High severity error: {exception}",
                    extra=extra_context,
                    exc_info=True
                )
            else:
                logger.warning(
                    f"MapleTrade error: {exception}",
                    extra=extra_context
                )
        else:
            # Log unexpected exceptions as errors
            logger.error(
                f"Unhandled exception: {type(exception).__name__}: {exception}",
                extra=extra_context,
                exc_info=True
            )
    
    def _handle_mapletrade_exception(self, request, exception):
        """Handle MapleTrade-specific exceptions."""
        error_response = {
            'error': True,
            'error_type': type(exception).__name__,
            'message': str(exception),
            'code': getattr(exception, 'error_code', 'MAPLETRADE_ERROR'),
            'timestamp': self._get_timestamp(),
        }
        
        # Add additional context for specific exception types
        if isinstance(exception, DataProviderError):
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            error_response['retry_after'] = getattr(exception, 'retry_after', 60)
        elif isinstance(exception, RateLimitError):
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
            error_response['retry_after'] = getattr(exception, 'retry_after', 60)
        elif isinstance(exception, AnalysisError):
            status_code = status.HTTP_400_BAD_REQUEST
        elif isinstance(exception, CustomValidationError):
            status_code = status.HTTP_400_BAD_REQUEST
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        
        return JsonResponse(error_response, status=status_code)
    
    def _handle_validation_error(self, request, exception):
        """Handle Django validation errors."""
        error_response = {
            'error': True,
            'error_type': 'ValidationError',
            'message': 'Validation failed',
            'details': str(exception),
            'timestamp': self._get_timestamp(),
        }
        
        return JsonResponse(error_response, status=status.HTTP_400_BAD_REQUEST)
    
    def _handle_generic_error(self, request, exception):
        """Handle unexpected exceptions in production."""
        error_response = {
            'error': True,
            'error_type': 'InternalServerError',
            'message': 'An unexpected error occurred. Please try again later.',
            'timestamp': self._get_timestamp(),
        }
        
        if settings.DEBUG:
            error_response['debug_info'] = {
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'traceback': traceback.format_exc()
            }
        
        return JsonResponse(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _get_timestamp(self):
        """Get current timestamp in ISO format."""
        from django.utils import timezone
        return timezone.now().isoformat()


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log all incoming requests for monitoring and debugging.
    """
    
    def process_request(self, request):
        """Log incoming request details."""
        if not self._should_log_request(request):
            return None
        
        logger.info(
            f"Request: {request.method} {request.path}",
            extra={
                'request_method': request.method,
                'request_path': request.path,
                'user': getattr(request, 'user', 'Anonymous'),
                'remote_addr': self._get_client_ip(request),
                'query_params': dict(request.GET),
            }
        )
        
        return None
    
    def process_response(self, request, response):
        """Log response details."""
        if not self._should_log_request(request):
            return response
        
        logger.info(
            f"Response: {request.method} {request.path} -> {response.status_code}",
            extra={
                'request_method': request.method,
                'request_path': request.path,
                'response_status': response.status_code,
                'user': getattr(request, 'user', 'Anonymous'),
            }
        )
        
        return response
    
    def _should_log_request(self, request):
        """Determine if request should be logged."""
        # Skip logging for static files and admin media
        skip_paths = ['/static/', '/media/', '/favicon.ico']
        return not any(request.path.startswith(path) for path in skip_paths)
    
    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip