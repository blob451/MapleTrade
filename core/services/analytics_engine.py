"""
Core Analytics Engine for MapleTrade.

This module implements the three-factor model from the Jupyter prototype:
1. Sector Outperformance (Stock vs Sector ETF)
2. Analyst Target Signal (Target > Current Price)  
3. Volatility Threshold (Stock volatility < Sector threshold)
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass

from django.utils import timezone
from django.core.cache import cache

from core.models import Stock, Sector, PriceData
from data.providers.yahoo_finance import YahooFinanceProvider
from .calculations import VolatilityCalculator, ReturnCalculator
from .sector_mapping import SectorMapper

logger = logging.getLogger(__name__)


@dataclass
class AnalysisSignals:
    """Data class for the three analysis signals."""
    outperformed_sector: bool
    target_above_price: bool  
    volatility_below_threshold: bool
    
    # Supporting data
    stock_return: Optional[float] = None
    sector_return: Optional[float] = None
    volatility: Optional[float] = None
    current_price: Optional[float] = None
    target_price: Optional[float] = None
    sector_threshold: Optional[float] = None


@dataclass
class AnalysisResult:
    """Complete analysis result matching prototype output."""
    signal: str  # 'BUY', 'SELL', 'HOLD'
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW'
    
    # Core metrics
    stock_return: float
    sector_return: float
    outperformance: float
    volatility: float
    current_price: float
    target_price: Optional[float]
    
    # Signal breakdown
    signals: AnalysisSignals
    
    # Metadata
    analysis_period_months: int
    sector_name: str
    sector_etf: str
    timestamp: datetime
    
    # Explanation
    rationale: str
    conditions_met: Dict[str, bool]


class AnalyticsEngine:
    """
    Main analytics engine implementing the three-factor model.
    
    This class replicates the logic from the Jupyter prototype:
    - Fetches stock and sector data
    - Calculates returns and volatility  
    - Applies decision logic
    - Returns structured analysis results
    """
    
    def __init__(self):
        self.data_provider = YahooFinanceProvider()
        self.volatility_calc = VolatilityCalculator()
        self.return_calc = ReturnCalculator()
        self.sector_mapper = SectorMapper()
        
    def analyze_stock(self, symbol: str, analysis_months: int = 12) -> AnalysisResult:
        """
        Main analysis method - replicates the prototype workflow.
        
        Args:
            symbol: Stock ticker symbol (e.g., 'NVDA')
            analysis_months: Lookback period in months (default: 12)
            
        Returns:
            AnalysisResult with signal and supporting data
            
        Raises:
            AnalyticsEngineError: If analysis cannot be completed
        """
        try:
            logger.info(f"Starting analysis for {symbol} ({analysis_months} months)")
            
            # Step 1: Get or create stock record
            stock = self._get_or_create_stock(symbol)
            
            # Step 2: Ensure sector mapping
            sector = self._ensure_sector_mapping(stock)
            
            # Step 3: Get price data for analysis period
            end_date = timezone.now()
            start_date = end_date - timedelta(days=analysis_months * 30)
            
            stock_prices = self._get_price_data(symbol, start_date, end_date)
            sector_prices = self._get_price_data(sector.etf_symbol, start_date, end_date)
            
            # Step 4: Calculate core metrics
            stock_return = self.return_calc.calculate_total_return(stock_prices)
            sector_return = self.return_calc.calculate_total_return(sector_prices)
            volatility = self.volatility_calc.calculate_annualized_volatility(stock_prices)
            
            # Step 5: Generate signals
            signals = self._generate_signals(stock, stock_return, sector_return, volatility, sector)
            
            # Step 6: Apply decision logic
            final_signal, confidence = self._apply_decision_logic(signals)
            
            # Step 7: Build result
            result = AnalysisResult(
                signal=final_signal,
                confidence=confidence,
                stock_return=stock_return,
                sector_return=sector_return,
                outperformance=stock_return - sector_return,
                volatility=volatility,
                current_price=float(stock.current_price or 0),
                target_price=float(stock.target_price) if stock.target_price else None,
                signals=signals,
                analysis_period_months=analysis_months,
                sector_name=sector.name,
                sector_etf=sector.etf_symbol,
                timestamp=timezone.now(),
                rationale=self._generate_rationale(signals, final_signal),
                conditions_met=self._get_conditions_met(signals)
            )
            
            # Step 8: Cache result
            self._cache_result(symbol, analysis_months, result)
            
            logger.info(f"Analysis complete for {symbol}: {final_signal}")
            return result
            
        except Exception as e:
            logger.error(f"Analysis failed for {symbol}: {e}")
            raise AnalyticsEngineError(f"Analysis failed for {symbol}: {e}")
    
    def _get_or_create_stock(self, symbol: str) -> Stock:
        """Get existing stock or create new one with fresh data."""
        try:
            stock = Stock.objects.get(symbol=symbol.upper())
            
            # Update if data is stale
            if stock.needs_update:
                stock_info = self.data_provider.get_stock_info(symbol)
                stock.name = stock_info.name
                stock.current_price = stock_info.current_price
                stock.target_price = stock_info.target_price
                stock.market_cap = stock_info.market_cap
                stock.exchange = stock_info.exchange
                stock.currency = stock_info.currency
                stock.last_updated = timezone.now()
                stock.save()
                
        except Stock.DoesNotExist:
            # Create new stock
            stock_info = self.data_provider.get_stock_info(symbol)
            stock = Stock.objects.create(
                symbol=stock_info.symbol,
                name=stock_info.name,
                current_price=stock_info.current_price,
                target_price=stock_info.target_price,
                market_cap=stock_info.market_cap,
                exchange=stock_info.exchange,
                currency=stock_info.currency,
                last_updated=timezone.now()
            )
            
        return stock
    
    def _ensure_sector_mapping(self, stock: Stock) -> Sector:
        """Ensure stock has proper sector classification."""
        if stock.sector:
            return stock.sector
            
        # Get sector from Yahoo Finance if not already mapped
        stock_info = self.data_provider.get_stock_info(stock.symbol)
        sector = self.sector_mapper.map_stock_to_sector(stock_info.sector)
        
        if sector:
            stock.sector = sector
            stock.save()
            return sector
        else:
            # Fallback to default sector (SPY as general market)
            default_sector, _ = Sector.objects.get_or_create(
                code='MARKET',
                defaults={
                    'name': 'General Market',
                    'etf_symbol': 'SPY',
                    'volatility_threshold': Decimal('0.25'),
                    'description': 'Default sector for unclassified stocks'
                }
            )
            stock.sector = default_sector
            stock.save()
            return default_sector
    
    def _get_price_data(self, symbol: str, start_date: datetime, end_date: datetime) -> list:
        """Get price data for analysis period."""
        cache_key = f"price_data_{symbol}_{start_date.date()}_{end_date.date()}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
            
        # Fetch from provider
        price_data = self.data_provider.get_price_history(symbol, start_date, end_date)
        
        # Cache for 1 hour
        cache.set(cache_key, price_data, 3600)
        
        return price_data
    
    def _generate_signals(self, stock: Stock, stock_return: float, sector_return: float, 
                         volatility: float, sector: Sector) -> AnalysisSignals:
        """Generate the three core signals matching prototype logic."""
        
        # Signal 1: Outperformance vs sector
        outperformed_sector = stock_return > sector_return
        
        # Signal 2: Target price above current price
        target_above_price = False
        if stock.target_price and stock.current_price:
            target_above_price = stock.target_price > stock.current_price
            
        # Signal 3: Volatility below sector threshold
        volatility_below_threshold = volatility < float(sector.volatility_threshold)
        
        return AnalysisSignals(
            outperformed_sector=outperformed_sector,
            target_above_price=target_above_price,
            volatility_below_threshold=volatility_below_threshold,
            stock_return=stock_return,
            sector_return=sector_return,
            volatility=volatility,
            current_price=float(stock.current_price) if stock.current_price else None,
            target_price=float(stock.target_price) if stock.target_price else None,
            sector_threshold=float(sector.volatility_threshold)
        )
    
    def _apply_decision_logic(self, signals: AnalysisSignals) -> Tuple[str, str]:
        """
        Apply the three-factor decision logic from prototype.
        
        Logic from prototype:
        - Both outperformance AND target positive → BUY (any volatility)
        - Exactly one positive AND low volatility → BUY  
        - Exactly one positive AND high volatility → HOLD
        - Both negative AND low volatility → HOLD
        - Both negative AND high volatility → SELL
        """
        
        positive_signals = sum([
            signals.outperformed_sector,
            signals.target_above_price
        ])
        
        # Both signals positive
        if positive_signals == 2:
            return "BUY", "HIGH"
            
        # Exactly one signal positive
        elif positive_signals == 1:
            if signals.volatility_below_threshold:
                return "BUY", "MEDIUM"
            else:
                return "HOLD", "MEDIUM"
                
        # Both signals negative
        else:
            if signals.volatility_below_threshold:
                return "HOLD", "LOW"
            else:
                return "SELL", "MEDIUM"
    
    def _generate_rationale(self, signals: AnalysisSignals, final_signal: str) -> str:
        """Generate human-readable explanation matching prototype style."""
        
        rationale_parts = []
        
        # Performance vs sector
        if signals.outperformed_sector:
            perf_diff = signals.stock_return - signals.sector_return
            rationale_parts.append(f"Stock outperformed sector by {perf_diff:.1%}")
        else:
            perf_diff = signals.sector_return - signals.stock_return  
            rationale_parts.append(f"Stock underperformed sector by {perf_diff:.1%}")
            
        # Target price analysis
        if signals.target_price and signals.current_price:
            if signals.target_above_price:
                upside = (signals.target_price - signals.current_price) / signals.current_price
                rationale_parts.append(f"Analyst target implies {upside:.1%} upside")
            else:
                rationale_parts.append("Analyst target below current price")
        else:
            rationale_parts.append("No analyst target available")
            
        # Volatility assessment
        if signals.volatility_below_threshold:
            rationale_parts.append(f"Volatility ({signals.volatility:.1%}) is acceptable for sector")
        else:
            rationale_parts.append(f"High volatility ({signals.volatility:.1%}) adds risk")
            
        # Final decision reasoning
        if final_signal == "BUY":
            rationale_parts.append("Multiple positive factors support a buy recommendation")
        elif final_signal == "SELL":  
            rationale_parts.append("Negative performance and high risk suggest selling")
        else:
            rationale_parts.append("Mixed signals suggest holding current position")
            
        return ". ".join(rationale_parts) + "."
    
    def _get_conditions_met(self, signals: AnalysisSignals) -> Dict[str, bool]:
        """Return checklist of conditions met (matches prototype output)."""
        return {
            'outperformed_sector': signals.outperformed_sector,
            'target_above_price': signals.target_above_price,
            'volatility_acceptable': signals.volatility_below_threshold
        }
    
    def _cache_result(self, symbol: str, months: int, result: AnalysisResult) -> None:
        """Cache analysis result for 4 hours."""
        cache_key = f"analysis_{symbol}_{months}"
        cache.set(cache_key, result, 14400)  # 4 hours


class AnalyticsEngineError(Exception):
    """Custom exception for analytics engine errors."""
    pass