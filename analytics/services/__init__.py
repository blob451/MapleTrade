"""
Analytics services package.
"""

from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
import logging

from .base import BaseAnalyzer, AnalysisResult as BaseAnalysisResult
from .engine import AnalyticsEngine
from .technical import TechnicalIndicators as TechnicalAnalyzer

logger = logging.getLogger(__name__)


class StockAnalyzer:
    """Wrapper to make AnalyticsEngine compatible with the expected interface."""
    
    def __init__(self):
        self.engine = AnalyticsEngine()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def analyze_stock(self, symbol, user, analysis_months=6, force_refresh=False):
        """
        Wrapper method to match expected signature.
        
        Args:
            symbol: Stock ticker symbol
            user: User requesting the analysis
            analysis_months: Number of months to analyze
            force_refresh: Whether to bypass cache
            
        Returns:
            StockAnalysis database object
        """
        # Normalize symbol
        symbol = symbol.upper().strip()
        
        # Check cache first
        cache_key = f"stock_analysis:{symbol}:{analysis_months}:{user.id}"
        if not force_refresh:
            cached = cache.get(cache_key)
            if cached:
                self.logger.info(f"Returning cached analysis for {symbol}")
                return cached
        
        try:
            # Use the existing engine
            result = self.engine.analyze_stock(symbol, analysis_months)
            
            # Check if there were critical errors
            if result.errors:
                error_str = ' '.join(result.errors)
                if 'Could not fetch stock info' in error_str:
                    raise ValueError(f"Invalid symbol or data unavailable: {symbol}")
                if 'No price data available' in error_str:
                    raise ValueError(f"No historical data available for {symbol}")
            
            # Convert to database model
            from analytics.models import StockAnalysis
            from core.models import Stock
            
            # Get or create stock
            stock, _ = Stock.objects.get_or_create(
                symbol=symbol,
                defaults={'name': symbol}
            )
            
            # Extract metrics and signals
            metrics = result.metrics
            signals = result.signals
            
            # Helper function to safely parse metrics
            def parse_metric(value, default=0, is_percentage=True):
                """Safely parse metric values."""
                if value is None:
                    return default
                    
                if isinstance(value, (int, float)):
                    return float(value)
                    
                if isinstance(value, str):
                    # Remove currency symbols and percentage signs
                    cleaned = value.replace('$', '').replace('%', '').strip()
                    
                    # Handle N/A or empty values
                    if cleaned.upper() == 'N/A' or not cleaned:
                        return default
                    
                    try:
                        parsed_value = float(cleaned)
                        # If the original had %, divide by 100
                        if is_percentage and '%' in value:
                            return parsed_value / 100
                        return parsed_value
                    except (ValueError, TypeError):
                        self.logger.warning(f"Could not parse metric value: {value}")
                        return default
                
                return default
            
            # Parse metrics with proper error handling
            stock_return = parse_metric(metrics.get('stock_return', 0))
            sector_return = parse_metric(metrics.get('etf_return', 0))
            volatility = parse_metric(metrics.get('volatility', 0))
            volatility_threshold = parse_metric(metrics.get('volatility_threshold', 42))
            
            # Parse price values
            current_price_str = metrics.get('current_price', '0')
            current_price = parse_metric(current_price_str, default=0, is_percentage=False)
            
            target_price_str = metrics.get('target_price', '0')
            target_price = parse_metric(target_price_str, default=None, is_percentage=False)
            
            # Create database record with transaction to ensure atomicity
            with transaction.atomic():
                analysis = StockAnalysis.objects.create(
                    user=user,
                    stock=stock,
                    sector_etf=metrics.get('sector_etf', 'SPY'),
                    analysis_period_months=analysis_months,
                    signal=result.recommendation,
                    confidence_score=float(result.confidence),
                    stock_return=stock_return,
                    sector_return=sector_return,
                    volatility=volatility,
                    volatility_threshold=volatility_threshold,
                    current_price=current_price if current_price > 0 else None,
                    analyst_target=target_price if target_price and target_price > 0 else None,
                    outperformed_sector=signals.get('outperformance', {}).get('value', False),
                    positive_analyst_outlook=signals.get('target_above_current', {}).get('value', False),
                    rationale=metrics.get('rationale', 'Analysis completed'),
                    analysis_data=result.to_dict(),
                    analysis_duration_ms=int((timezone.now() - result.timestamp).total_seconds() * 1000)
                )
                
                # Calculate derived fields
                if analysis.current_price and analysis.analyst_target:
                    analysis.target_upside = (
                        (analysis.analyst_target - analysis.current_price) / 
                        analysis.current_price
                    )
                
                analysis.relative_performance = analysis.stock_return - analysis.sector_return
                analysis.is_high_volatility = analysis.volatility > analysis.volatility_threshold
                
                # Update signal strength based on confidence
                # analysis.signal_strength = analysis.confidence_score
                analysis.relative_performance = analysis.stock_return - analysis.sector_return
                analysis.is_high_volatility = analysis.volatility > analysis.volatility_threshold
                # Save updates
                analysis.save()
                
                # Update user analysis count
                user.update_analysis_count()
            
            # Cache the result
            cache.set(cache_key, analysis, 3600)  # Cache for 1 hour
            
            return analysis
            
        except ValueError:
            # Re-raise ValueError as-is (invalid symbol, no data, etc.)
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error analyzing {symbol}: {e}")
            raise ValueError(f"Failed to analyze {symbol}: {str(e)}")


# Create PortfolioAnalyzer implementation
class PortfolioAnalyzer(BaseAnalyzer):
    """Portfolio-level analyzer implementation."""
    
    def __init__(self):
        super().__init__()
        self.stock_analyzer = StockAnalyzer()
    
    def analyze(self, symbol: str, start_date, end_date):
        """Implement abstract method for compatibility."""
        # This is a placeholder - real implementation would analyze entire portfolio
        return {
            'symbol': symbol,
            'analysis': 'Portfolio analysis not yet implemented'
        }
    
    def analyze_portfolio(self, user):
        """
        Analyze user's entire portfolio.
        
        Args:
            user: User whose portfolio to analyze
            
        Returns:
            Dictionary with portfolio analysis results
        """
        from core.models import PortfolioStock
        
        # Get user's portfolio stocks
        portfolio_stocks = PortfolioStock.objects.filter(
            portfolio__user=user,
            portfolio__is_default=True
        ).select_related('stock', 'portfolio')
        
        if not portfolio_stocks.exists():
            return {
                'error': 'No stocks in portfolio',
                'total_stocks': 0,
                'analyses': []
            }
        
        analyses = []
        errors = []
        
        for ps in portfolio_stocks:
            try:
                analysis = self.stock_analyzer.analyze_stock(
                    ps.stock.symbol,
                    user,
                    analysis_months=6,
                    force_refresh=False
                )
                analyses.append(analysis)
            except Exception as e:
                self.logger.error(f"Failed to analyze {ps.stock.symbol}: {e}")
                errors.append({
                    'symbol': ps.stock.symbol,
                    'error': str(e)
                })
        
        # Calculate portfolio metrics
        if analyses:
            buy_count = sum(1 for a in analyses if a.signal == 'BUY')
            hold_count = sum(1 for a in analyses if a.signal == 'HOLD')
            sell_count = sum(1 for a in analyses if a.signal == 'SELL')
            
            avg_confidence = sum(a.confidence_score for a in analyses) / len(analyses)
            
            # Calculate weighted returns (equal weight for now)
            total_return = sum(a.stock_return for a in analyses) / len(analyses)
        else:
            buy_count = hold_count = sell_count = 0
            avg_confidence = 0
            total_return = 0
        
        return {
            'total_stocks': portfolio_stocks.count(),
            'analyzed': len(analyses),
            'errors': errors,
            'recommendations': {
                'buy': buy_count,
                'hold': hold_count,
                'sell': sell_count
            },
            'metrics': {
                'average_confidence': float(avg_confidence),
                'portfolio_return': float(total_return),
                'analyses_count': len(analyses)
            },
            'analyses': analyses
        }


# Create alias for compatibility
AnalysisResult = BaseAnalysisResult

__all__ = [
    'StockAnalyzer',
    'TechnicalAnalyzer',
    'PortfolioAnalyzer',
    'BaseAnalyzer',
    'AnalysisResult',
    'AnalyticsEngine',
]