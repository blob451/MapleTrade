"""
Custom exceptions for MapleTrade financial data operations.

This module defines a hierarchy of exceptions specific to financial
data processing, analysis, and API operations.
"""

from typing import Optional, Any, Dict


class MapleTradeBaseException(Exception):
    """
    Base exception for all MapleTrade-specific errors.
    
    All custom exceptions should inherit from this class to ensure
    consistent error handling and logging.
    """
    
    def __init__(self, message: str, error_code: str = None, 
                 severity: str = 'medium', details: Dict[str, Any] = None):
        """
        Initialize MapleTrade exception.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            severity: Error severity level ('low', 'medium', 'high', 'critical')
            details: Additional error context and details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.severity = severity
        self.details = details or {}
    
    def __str__(self):
        return f"[{self.error_code}] {self.message}"
    
    def to_dict(self):
        """Convert exception to dictionary for API responses."""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'severity': self.severity,
            'details': self.details
        }


# Data Provider Exceptions
class DataProviderError(MapleTradeBaseException):
    """Base exception for data provider errors."""
    
    def __init__(self, message: str, provider: str = None, 
                 retry_after: int = None, **kwargs):
        super().__init__(message, **kwargs)
        self.provider = provider
        self.retry_after = retry_after  # Seconds until retry is allowed


class DataSourceUnavailableError(DataProviderError):
    """Raised when external data source is unavailable."""
    
    def __init__(self, message: str, provider: str = None, **kwargs):
        super().__init__(
            message, 
            provider=provider,
            error_code='DATA_SOURCE_UNAVAILABLE',
            severity='high',
            **kwargs
        )


class RateLimitError(DataProviderError):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: int = 60, **kwargs):
        super().__init__(
            message,
            error_code='RATE_LIMIT_EXCEEDED',
            severity='medium',
            retry_after=retry_after,
            **kwargs
        )


class InvalidSymbolError(DataProviderError):
    """Raised when stock symbol is invalid or not found."""
    
    def __init__(self, symbol: str, provider: str = None, **kwargs):
        message = f"Invalid or unknown symbol: {symbol}"
        super().__init__(
            message,
            provider=provider,
            error_code='INVALID_SYMBOL',
            severity='low',
            details={'symbol': symbol},
            **kwargs
        )


class DataQualityError(DataProviderError):
    """Raised when data quality is insufficient for analysis."""
    
    def __init__(self, message: str, symbol: str = None, 
                 quality_score: float = None, **kwargs):
        super().__init__(
            message,
            error_code='DATA_QUALITY_INSUFFICIENT',
            severity='medium',
            details={
                'symbol': symbol,
                'quality_score': quality_score
            },
            **kwargs
        )


# Validation Exceptions
class ValidationError(MapleTradeBaseException):
    """Base exception for data validation errors."""
    
    def __init__(self, message: str, field: str = None, 
                 value: Any = None, **kwargs):
        super().__init__(
            message,
            error_code='VALIDATION_ERROR',
            severity='low',
            details={'field': field, 'value': value},
            **kwargs
        )


class PriceDataValidationError(ValidationError):
    """Raised when price data fails validation."""
    
    def __init__(self, message: str, symbol: str = None, 
                 date: str = None, **kwargs):
        super().__init__(
            message,
            error_code='PRICE_DATA_INVALID',
            details={'symbol': symbol, 'date': date},
            **kwargs
        )


class DateRangeError(ValidationError):
    """Raised when date range is invalid."""
    
    def __init__(self, message: str, start_date: str = None, 
                 end_date: str = None, **kwargs):
        super().__init__(
            message,
            error_code='INVALID_DATE_RANGE',
            details={'start_date': start_date, 'end_date': end_date},
            **kwargs
        )


# Analysis Exceptions
class AnalysisError(MapleTradeBaseException):
    """Base exception for analysis-related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_code='ANALYSIS_ERROR',
            severity='medium',
            **kwargs
        )


class InsufficientDataError(AnalysisError):
    """Raised when insufficient data is available for analysis."""
    
    def __init__(self, message: str, symbol: str = None, 
                 required_days: int = None, available_days: int = None, **kwargs):
        super().__init__(
            message,
            error_code='INSUFFICIENT_DATA',
            details={
                'symbol': symbol,
                'required_days': required_days,
                'available_days': available_days
            },
            **kwargs
        )


class CalculationError(AnalysisError):
    """Raised when financial calculations fail."""
    
    def __init__(self, message: str, calculation_type: str = None, 
                 symbol: str = None, **kwargs):
        super().__init__(
            message,
            error_code='CALCULATION_ERROR',
            details={
                'calculation_type': calculation_type,
                'symbol': symbol
            },
            **kwargs
        )


class ModelError(AnalysisError):
    """Raised when machine learning model operations fail."""
    
    def __init__(self, message: str, model_type: str = None, 
                 model_version: str = None, **kwargs):
        super().__init__(
            message,
            error_code='MODEL_ERROR',
            severity='high',
            details={
                'model_type': model_type,
                'model_version': model_version
            },
            **kwargs
        )


# Cache and Storage Exceptions
class CacheError(MapleTradeBaseException):
    """Raised when cache operations fail."""
    
    def __init__(self, message: str, cache_key: str = None, **kwargs):
        super().__init__(
            message,
            error_code='CACHE_ERROR',
            severity='low',
            details={'cache_key': cache_key},
            **kwargs
        )


class DatabaseError(MapleTradeBaseException):
    """Raised when database operations fail."""
    
    def __init__(self, message: str, operation: str = None, 
                 table: str = None, **kwargs):
        super().__init__(
            message,
            error_code='DATABASE_ERROR',
            severity='high',
            details={
                'operation': operation,
                'table': table
            },
            **kwargs
        )


# Configuration and System Exceptions
class ConfigurationError(MapleTradeBaseException):
    """Raised when system configuration is invalid."""
    
    def __init__(self, message: str, config_key: str = None, **kwargs):
        super().__init__(
            message,
            error_code='CONFIGURATION_ERROR',
            severity='critical',
            details={'config_key': config_key},
            **kwargs
        )


class ServiceUnavailableError(MapleTradeBaseException):
    """Raised when required service is unavailable."""
    
    def __init__(self, message: str, service_name: str = None, 
                 retry_after: int = None, **kwargs):
        super().__init__(
            message,
            error_code='SERVICE_UNAVAILABLE',
            severity='high',
            details={'service_name': service_name},
            **kwargs
        )
        self.retry_after = retry_after


# API and Authentication Exceptions
class AuthenticationError(MapleTradeBaseException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication required", **kwargs):
        super().__init__(
            message,
            error_code='AUTHENTICATION_REQUIRED',
            severity='medium',
            **kwargs
        )


class PermissionError(MapleTradeBaseException):
    """Raised when user lacks required permissions."""
    
    def __init__(self, message: str, required_permission: str = None, **kwargs):
        super().__init__(
            message,
            error_code='PERMISSION_DENIED',
            severity='medium',
            details={'required_permission': required_permission},
            **kwargs
        )


class QuotaExceededError(MapleTradeBaseException):
    """Raised when user quota is exceeded."""
    
    def __init__(self, message: str, quota_type: str = None, 
                 current_usage: int = None, limit: int = None, **kwargs):
        super().__init__(
            message,
            error_code='QUOTA_EXCEEDED',
            severity='medium',
            details={
                'quota_type': quota_type,
                'current_usage': current_usage,
                'limit': limit
            },
            **kwargs
        )


# Helper function to create exception from error code
def create_exception_from_code(error_code: str, message: str, **kwargs) -> MapleTradeBaseException:
    """
    Create appropriate exception based on error code.
    
    Args:
        error_code: Error code to map to exception type
        message: Error message
        **kwargs: Additional arguments for exception
        
    Returns:
        Appropriate exception instance
    """
    exception_mapping = {
        'DATA_SOURCE_UNAVAILABLE': DataSourceUnavailableError,
        'RATE_LIMIT_EXCEEDED': RateLimitError,
        'INVALID_SYMBOL': InvalidSymbolError,
        'DATA_QUALITY_INSUFFICIENT': DataQualityError,
        'VALIDATION_ERROR': ValidationError,
        'PRICE_DATA_INVALID': PriceDataValidationError,
        'INVALID_DATE_RANGE': DateRangeError,
        'ANALYSIS_ERROR': AnalysisError,
        'INSUFFICIENT_DATA': InsufficientDataError,
        'CALCULATION_ERROR': CalculationError,
        'MODEL_ERROR': ModelError,
        'CACHE_ERROR': CacheError,
        'DATABASE_ERROR': DatabaseError,
        'CONFIGURATION_ERROR': ConfigurationError,
        'SERVICE_UNAVAILABLE': ServiceUnavailableError,
        'AUTHENTICATION_REQUIRED': AuthenticationError,
        'PERMISSION_DENIED': PermissionError,
        'QUOTA_EXCEEDED': QuotaExceededError,
    }
    
    exception_class = exception_mapping.get(error_code, MapleTradeBaseException)
    return exception_class(message, **kwargs)