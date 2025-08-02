"""
Main analytics engine implementing the three-factor model from the prototype.
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import time

from django.core.cache import cache
from core.models import Stock, Sector
from data.providers import YahooFinanceProvider
from .base import AnalysisResult
from .technical import TechnicalIndicators
from django.utils import timezone
from data.providers.mock_provider import MockDataProvider

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """
    Main analytics engine that orchestrates analysis and generates recommendations.
    Implements the three-factor model from the prototype:
    1. Outperformance vs sector ETF
    2. Analyst target price vs current price
    3. Volatility vs sector threshold
    """
    
    def __init__(self, data_provider: Optional[YahooFinanceProvider] = None):
        # Temporarily use mock provider
        # self.data_provider = data_provider or YahooFinanceProvider()
        self.data_provider = data_provider or MockDataProvider()
        self.technical = TechnicalIndicators(self.data_provider)
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def analyze_stock(self, symbol: str, months: int = 6) -> AnalysisResult:
        """
        Perform complete analysis on a stock using the three-factor model.
        
        Args:
            symbol: Stock ticker symbol
            months: Analysis window in months (default 6)
            
        Returns:
            AnalysisResult with recommendation and supporting data
        """
        # Initialize result
        result = AnalysisResult(symbol, 'HOLD')
        
        # Set date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)
        
        try:
            # Get stock info
            stock_info = self._get_or_update_stock(symbol)
            if not stock_info:
                result.add_error(f"Could not fetch stock info for {symbol}")
                return result
            
            # Get sector ETF
            sector_etf = self._get_sector_etf(stock_info)
            result.add_metric('sector_etf', sector_etf)
            
            # Calculate the three factors
            
            # Factor 1: Outperformance vs sector
            outperformance, stock_return, etf_return = self._calculate_outperformance(
                symbol, sector_etf, start_date, end_date
            )
            result.add_signal('outperformance', outperformance)
            result.add_metric('stock_return', f"{stock_return:.2f}%")
            result.add_metric('etf_return', f"{etf_return:.2f}%")
            
            # Factor 2: Analyst target vs current price
            target_above_current = False
            if stock_info.target_price and stock_info.current_price:
                target_above_current = stock_info.target_price > stock_info.current_price
                target_spread = ((stock_info.target_price - stock_info.current_price) 
                               / stock_info.current_price * 100)
                result.add_metric('target_price', f"${stock_info.target_price:.2f}")
                result.add_metric('current_price', f"${stock_info.current_price:.2f}")
                result.add_metric('target_spread', f"{target_spread:.2f}%")
            else:
                result.add_metric('target_price', 'N/A')
                result.add_metric('current_price', f"${stock_info.current_price:.2f}" 
                                if stock_info.current_price else 'N/A')
            
            result.add_signal('target_above_current', target_above_current)
            
            # Factor 3: Volatility vs threshold
            volatility = self._calculate_volatility(symbol, start_date, end_date)
            volatility_threshold = self._get_volatility_threshold(stock_info)
            low_volatility = volatility < volatility_threshold if volatility else False
            
            result.add_signal('low_volatility', low_volatility)
            result.add_metric('volatility', f"{volatility:.2f}%" if volatility else 'N/A')
            result.add_metric('volatility_threshold', f"{volatility_threshold:.2f}%")
            
            # Apply decision logic
            recommendation, rationale = self._apply_decision_logic(
                outperformance, target_above_current, low_volatility
            )
            
            result.recommendation = recommendation
            result.add_metric('rationale', rationale)
            
            # Calculate confidence based on signal agreement
            confidence = self._calculate_confidence(outperformance, target_above_current, low_volatility)
            result.confidence = confidence
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            result.add_error(str(e))
        
        return result
    
    def _get_or_update_stock(self, symbol: str) -> Optional[Stock]:
        """Get stock from database or fetch from provider."""
        try:
            # Try to get from database first
            stock = Stock.objects.filter(symbol__iexact=symbol).first()
            
            # If stock exists and was updated recently (within 1 hour), use it
            if stock and not stock.needs_update:
                self.logger.info(f"Using cached data for {symbol}")
                return stock
            
            # Add delay to avoid rate limiting
            time.sleep(2)  # Wait 2 seconds between API calls
            
            try:
                # Update if needed or create new
                stock_info = self.data_provider.get_stock_info(symbol)
                
                # Get or create sector
                sector = None
                if stock_info.sector:
                    sector, _ = Sector.objects.get_or_create(
                        name=stock_info.sector,
                        defaults={
                            'code': stock_info.sector[:4].upper(),
                            'etf_symbol': self._map_sector_to_etf(stock_info.sector)
                        }
                    )
                
                if stock:
                    # Update existing
                    stock.name = stock_info.name
                    stock.sector = sector
                    stock.current_price = stock_info.current_price
                    stock.target_price = stock_info.target_price
                    stock.last_updated = timezone.now()
                    stock.save()
                else:
                    # Create new
                    stock = Stock.objects.create(
                        symbol=symbol.upper(),
                        name=stock_info.name,
                        sector=sector,
                        current_price=stock_info.current_price,
                        target_price=stock_info.target_price,
                        last_updated=datetime.now()
                    )
                
                return stock
                
            except Exception as e:
                # If API fails but we have cached data, use it
                if stock:
                    self.logger.warning(f"API failed for {symbol}, using cached data: {e}")
                    return stock
                else:
                    raise
                
        except Exception as e:
            logger.error(f"Error getting/updating stock {symbol}: {e}")
            return None
    
    def _get_sector_etf(self, stock: Stock) -> str:
        """Get the appropriate sector ETF for comparison."""
        if stock.sector and stock.sector.etf_symbol:
            return stock.sector.etf_symbol
        
        # Default to SPY if no sector
        return 'SPY'
    
    def _map_sector_to_etf(self, sector_name: str) -> str:
        """Map sector name to ETF symbol (same as prototype)."""
        sector_etf_map = {
            'Technology': 'XLK',
            'Healthcare': 'XLV',
            'Financials': 'XLF',
            'Consumer Discretionary': 'XLY',
            'Consumer Staples': 'XLP',
            'Energy': 'XLE',
            'Materials': 'XLB',
            'Industrials': 'XLI',
            'Utilities': 'XLU',
            'Real Estate': 'XLRE',
            'Communication Services': 'XLC'
        }
        
        return sector_etf_map.get(sector_name, 'SPY')
    
    def _calculate_outperformance(self, symbol: str, etf_symbol: str, 
                                  start_date: datetime, end_date: datetime) -> Tuple[bool, float, float]:
        """
        Calculate if stock outperformed its sector ETF.
        
        Returns:
            Tuple of (outperformed: bool, stock_return: float, etf_return: float)
        """
        try:
            # Check cache first
            cache_key = f"returns_{symbol}_{etf_symbol}_{start_date.date()}_{end_date.date()}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
            
            # Add delay between API calls
            time.sleep(2)
            
            # Get technical analysis for both
            stock_analysis = self.technical.analyze(symbol, start_date, end_date)
            
            # Add delay between API calls
            time.sleep(2)
            
            etf_analysis = self.technical.analyze(etf_symbol, start_date, end_date)
            
            # Get returns
            stock_return = stock_analysis.get('returns', {}).get('total_return', 0)
            etf_return = etf_analysis.get('returns', {}).get('total_return', 0)
            
            outperformed = stock_return > etf_return
            
            result = (outperformed, stock_return, etf_return)
            
            # Cache the result for 1 hour
            cache.set(cache_key, result, 3600)
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating outperformance: {e}")
            return False, 0, 0
    
    def _calculate_volatility(self, symbol: str, start_date: datetime, end_date: datetime) -> Optional[float]:
        """Calculate annualized volatility for the period."""
        try:
            # Check cache first
            cache_key = f"volatility_{symbol}_{start_date.date()}_{end_date.date()}"
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Add delay to avoid rate limiting
            time.sleep(2)
            
            analysis = self.technical.analyze(symbol, start_date, end_date)
            volatility = analysis.get('volatility')
            
            # Cache the result for 1 hour
            if volatility is not None:
                cache.set(cache_key, volatility, 3600)
            
            return volatility
        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return None
    
    def _get_volatility_threshold(self, stock: Stock) -> float:
        """Get volatility threshold for the stock's sector."""
        if stock.sector and stock.sector.volatility_threshold:
            return float(stock.sector.volatility_threshold * 100)  # Convert to percentage
        
        # Default threshold
        return 42.0
    
    def _apply_decision_logic(self, outperformance: bool, target_above_current: bool, 
                             low_volatility: bool) -> Tuple[str, str]:
        """
        Apply the three-factor decision logic from the prototype.
        
        Returns:
            Tuple of (recommendation, rationale)
        """
        # Count positive signals
        positive_signals = sum([outperformance, target_above_current])
        
        # Both positive signals = BUY regardless of volatility
        if positive_signals == 2:
            return 'BUY', 'Both outperformance and target are positive'
        
        # No positive signals
        elif positive_signals == 0:
            if low_volatility:
                return 'HOLD', 'Both performance and target are negative, but volatility is low'
            else:
                return 'SELL', 'Both performance and target are negative, and volatility is high'
        
        # Exactly one positive signal
        else:
            if low_volatility:
                return 'BUY', 'One positive signal and volatility is low'
            else:
                return 'HOLD', 'One positive signal, but volatility is high'
    
    def _calculate_confidence(self, outperformance: bool, target_above_current: bool, 
                            low_volatility: bool) -> float:
        """Calculate confidence score based on signal agreement."""
        # All three positive = high confidence
        if all([outperformance, target_above_current, low_volatility]):
            return 0.9
        
        # Two positive = medium-high confidence
        positive_count = sum([outperformance, target_above_current, low_volatility])
        if positive_count == 2:
            return 0.7
        
        # One positive = medium confidence
        elif positive_count == 1:
            return 0.5
        
        # No positive = low confidence (but confident in negative)
        else:
            return 0.3