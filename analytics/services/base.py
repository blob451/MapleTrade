"""
Base analyzer class for all analytics services.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """
    Abstract base class for all analyzer services.
    
    Provides common functionality and enforces consistent interface.
    """
    
    def __init__(self):
        """Initialize base analyzer."""
        self.logger = logger
    
    @abstractmethod
    def analyze(self, symbol: str, **kwargs) -> Dict[str, Any]:
        """
        Perform analysis on a stock.
        
        Args:
            symbol: Stock ticker symbol
            **kwargs: Additional parameters specific to the analyzer
            
        Returns:
            Dict containing analysis results
        """
        pass
    
    def validate_symbol(self, symbol: str) -> str:
        """
        Validate and normalize stock symbol.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Normalized symbol (uppercase)
            
        Raises:
            ValueError: If symbol is invalid
        """
        if not symbol or not isinstance(symbol, str):
            raise ValueError("Symbol must be a non-empty string")
        
        symbol = symbol.strip().upper()
        
        if not symbol.isalnum():
            raise ValueError("Symbol must contain only letters and numbers")
        
        if len(symbol) > 5:
            raise ValueError("Symbol must be 5 characters or less")
        
        return symbol
    
    def log_analysis_start(self, symbol: str, analyzer_name: str):
        """Log the start of analysis."""
        self.logger.info(f"Starting {analyzer_name} analysis for {symbol}")
    
    def log_analysis_complete(self, symbol: str, analyzer_name: str):
        """Log the completion of analysis."""
        self.logger.info(f"Completed {analyzer_name} analysis for {symbol}")
    
    def log_analysis_error(self, symbol: str, analyzer_name: str, error: Exception):
        """Log analysis error."""
        self.logger.error(f"{analyzer_name} analysis failed for {symbol}: {str(error)}")