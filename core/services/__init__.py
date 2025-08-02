"""
MapleTrade Core Services Package.

This package contains the core business logic services for the MapleTrade
analytics platform, including the main analytics engine and supporting
calculation services.
"""

from .analytics_engine import AnalyticsEngine, AnalysisResult, AnalysisSignals, AnalyticsEngineError
from ...analytics.services.calculations import (
    ReturnCalculator, 
    VolatilityCalculator, 
    TechnicalCalculator, 
    PerformanceMetrics,
    CalculationError
)
from .sector_mapping import (
    SectorMapper, 
    SectorAnalyzer,
    initialize_default_sectors,
    validate_sector_mappings
)

__all__ = [
    # Main analytics engine
    'AnalyticsEngine',
    'AnalysisResult', 
    'AnalysisSignals',
    'AnalyticsEngineError',
    
    # Calculation services
    'ReturnCalculator',
    'VolatilityCalculator', 
    'TechnicalCalculator',
    'PerformanceMetrics',
    'CalculationError',
    
    # Sector mapping services
    'SectorMapper',
    'SectorAnalyzer',
    'initialize_default_sectors',
    'validate_sector_mappings',
]


# Version info
__version__ = '1.0.0'
__author__ = 'MapleTrade Development Team'