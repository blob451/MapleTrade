"""
Base classes for analytics services.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
import logging
from django.utils import timezone  # Add this import


class BaseAnalyzer(ABC):
    """
    Abstract base class for all analyzers.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def analyze(self, symbol: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Perform analysis on a stock.
        
        Args:
            symbol: Stock ticker symbol
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            Dictionary containing analysis results
        """
        pass


class AnalysisResult:
    """
    Container for analysis results.
    """
    
    def __init__(self, symbol: str, recommendation: str, confidence: float = 0.0):
        self.symbol = symbol
        self.recommendation = recommendation  # BUY, HOLD, SELL
        self.confidence = confidence
        self.timestamp = timezone.now()  # Changed from datetime.now()
        self.signals = {}
        self.metrics = {}
        self.errors = []
    
    def add_signal(self, name: str, value: bool, weight: float = 1.0):
        """Add a signal to the analysis."""
        self.signals[name] = {
            'value': value,
            'weight': weight
        }
    
    def add_metric(self, name: str, value: Any):
        """Add a metric to the analysis."""
        self.metrics[name] = value
    
    def add_error(self, error: str):
        """Add an error message."""
        self.errors.append(error)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'symbol': self.symbol,
            'recommendation': self.recommendation,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'signals': self.signals,
            'metrics': self.metrics,
            'errors': self.errors
        }