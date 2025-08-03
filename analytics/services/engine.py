"""
Main analytics engine that orchestrates various analysis services.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from data.services import StockService, PriceService, SectorService
from analytics.models import AnalysisResult
from users.models import UserPortfolio
from .technical import TechnicalIndicators
from .calculations import FinancialCalculations
from .batch_analysis import BatchAnalysisService

logger = logging.getLogger(__name__)


class AnalyticsEngineError(Exception):
    """Custom exception for analytics engine errors."""
    pass

class AnalyticsEngine:
    """
    Main analytics engine that coordinates different analysis services.
    """
    
    def __init__(self):
        # Initialize services
        self.stock_service = StockService()
        self.price_service = PriceService()
        self.sector_service = SectorService()
        
        # Initialize analyzers
        self.technical = TechnicalIndicators(self.stock_service, self.price_service)
        self.calculations = FinancialCalculations(
            self.stock_service,
            self.price_service,
            self.sector_service
        )
        self.batch_service = BatchAnalysisService(
            stock_service=self.stock_service,
            price_service=self.price_service
        )
        
        self.cache_timeout = 3600  # 1 hour default cache
    
    def analyze_portfolio(
        self,
        portfolio_id: int,
        analysis_period: int = 30,
        include_technical: bool = True
    ) -> Dict[str, Any]:
        """
        Perform comprehensive portfolio analysis.
        
        Args:
            portfolio_id: Portfolio to analyze
            analysis_period: Days to analyze
            include_technical: Whether to include technical analysis
            
        Returns:
            Complete analysis results
        """
        # Check cache
        cache_key = f"portfolio_analysis_{portfolio_id}_{analysis_period}_{include_technical}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.debug(f"Returning cached analysis for portfolio {portfolio_id}")
            return cached_result
        
        try:
            # Get portfolio
            portfolio = UserPortfolio.objects.get(id=portfolio_id)
            
            # Set date range
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=analysis_period)
            
            # Perform financial analysis
            financial_analysis = self.calculations.analyze(
                portfolio_id,
                start_date,
                end_date
            )
            
            # Add technical analysis if requested
            if include_technical and 'holdings' in financial_analysis:
                symbols = [h['symbol'] for h in financial_analysis['holdings']]
                
                # Get technical analysis for all holdings
                technical_results = self.batch_service.analyze_multiple_stocks(
                    symbols,
                    start_date,
                    end_date,
                    ['technical']
                )
                
                # Merge technical data into holdings
                for holding in financial_analysis['holdings']:
                    symbol = holding['symbol']
                    if symbol in technical_results['results']:
                        tech_data = technical_results['results'][symbol].get('technical', {})
                        holding['technical'] = {
                            'rsi': tech_data.get('rsi_14'),
                            'trend': tech_data.get('trend'),
                            'support_resistance': tech_data.get('support_resistance')
                        }
            
            # Add market context
            financial_analysis['market_context'] = self._get_market_context()
            
            # Cache result
            cache.set(cache_key, financial_analysis, self.cache_timeout)
            
            return financial_analysis
            
        except UserPortfolio.DoesNotExist:
            logger.error(f"Portfolio {portfolio_id} not found")
            return {'error': 'Portfolio not found'}
        except Exception as e:
            logger.error(f"Error analyzing portfolio {portfolio_id}: {e}")
            return {'error': str(e)}
    
    def analyze_stock(
        self,
        symbol: str,
        analysis_period: int = 30,
        analysis_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive stock analysis.
        
        Args:
            symbol: Stock symbol
            analysis_period: Days to analyze
            analysis_types: Types of analysis to perform
            
        Returns:
            Analysis results
        """
        if not analysis_types:
            analysis_types = ['technical', 'fundamental', 'comparison']
        
        # Set date range
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=analysis_period)
        
        result = {
            'symbol': symbol,
            'analysis_date': timezone.now().isoformat(),
            'period_days': analysis_period
        }
        
        try:
            # Get stock info
            stock = self.stock_service.get_or_create_stock(symbol)
            result['stock_info'] = {
                'name': stock.name,
                'sector': stock.sector.name if stock.sector else None,
                'exchange': stock.exchange,
                'market_cap': float(stock.market_cap) if stock.market_cap else None,
                'current_price': float(stock.current_price) if stock.current_price else None
            }
            
            # Technical analysis
            if 'technical' in analysis_types:
                technical_result = self.technical.analyze(
                    symbol,
                    datetime.combine(start_date, datetime.min.time()),
                    datetime.combine(end_date, datetime.min.time())
                )
                result['technical'] = technical_result
            
            # Fundamental metrics
            if 'fundamental' in analysis_types:
                result['fundamental'] = self._get_fundamental_metrics(stock)
            
            # Peer comparison
            if 'comparison' in analysis_types and stock.sector:
                result['peer_comparison'] = self._compare_with_peers(stock)
            
            # Save analysis result
            self._save_stock_analysis(stock, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing stock {symbol}: {e}")
            result['error'] = str(e)
            return result
    
    def screen_stocks(
        self,
        criteria: Dict[str, Any],
        universe: List[str] = None
    ) -> Dict[str, Any]:
        """
        Screen stocks based on criteria.
        
        Args:
            criteria: Screening criteria
            universe: List of symbols to screen (default: all active)
            
        Returns:
            Screening results
        """
        # Get universe of stocks
        if not universe:
            # Get all active stocks
            active_stocks = self.stock_service.search_stocks("")
            universe = [stock.symbol for stock in active_stocks[:100]]  # Limit to 100
        
        # Perform screening
        return self.batch_service.screen_stocks(universe, criteria)
    
    def compare_stocks(
        self,
        symbols: List[str],
        metrics: List[str] = None
    ) -> Dict[str, Any]:
        """
        Compare multiple stocks.
        
        Args:
            symbols: Symbols to compare
            metrics: Metrics to compare
            
        Returns:
            Comparison results
        """
        return self.batch_service.compare_stocks(symbols, metrics)
    
    def get_sector_analysis(self, sector_code: str) -> Dict[str, Any]:
        """
        Analyze a sector.
        
        Args:
            sector_code: Sector code (e.g., 'TECH')
            
        Returns:
            Sector analysis
        """
        try:
            sector = self.sector_service.get_by_code(sector_code)
            if not sector:
                return {'error': 'Sector not found'}
            
            # Get sector statistics
            stats = self.sector_service.get_sector_statistics(sector)
            
            # Get stocks in sector
            stocks = self.stock_service.get_stocks_by_sector(sector)
            
            # Analyze sector performance
            if stocks:
                symbols = [s.symbol for s in stocks[:20]]  # Limit to 20 stocks
                
                batch_results = self.batch_service.analyze_multiple_stocks(
                    symbols,
                    timezone.now().date() - timedelta(days=30),
                    timezone.now().date(),
                    ['technical']
                )
                
                # Calculate sector metrics
                sector_metrics = self._calculate_sector_metrics(batch_results['results'])
                stats['performance'] = sector_metrics
            
            return stats
            
        except Exception as e:
            logger.error(f"Error analyzing sector {sector_code}: {e}")
            return {'error': str(e)}
    
    def _get_market_context(self) -> Dict[str, Any]:
        """Get current market context."""
        try:
            # Analyze major indices
            indices = ['SPY', 'QQQ', 'DIA']  # S&P 500, NASDAQ, Dow
            
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=5)
            
            results = self.batch_service.analyze_multiple_stocks(
                indices,
                start_date,
                end_date,
                ['technical']
            )
            
            context = {
                'timestamp': timezone.now().isoformat(),
                'indices': {}
            }
            
            for symbol, data in results['results'].items():
                if 'error' not in data:
                    context['indices'][symbol] = {
                        'price': data['stock_info'].get('current_price'),
                        'trend': data.get('technical', {}).get('trend', {}).get('short_term')
                    }
            
            # Determine overall market trend
            trends = [idx['trend'] for idx in context['indices'].values() if idx.get('trend')]
            if trends:
                bullish_count = trends.count('bullish')
                context['overall_trend'] = 'bullish' if bullish_count > len(trends) / 2 else 'bearish'
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting market context: {e}")
            return {}
    
    def _get_fundamental_metrics(self, stock) -> Dict[str, Any]:
        """Get fundamental metrics for a stock."""
        metrics = {}
        
        if stock.market_cap:
            metrics['market_cap'] = float(stock.market_cap)
            metrics['market_cap_category'] = self._categorize_market_cap(stock.market_cap)
        
        if stock.current_price and stock.target_price:
            upside = (stock.target_price - stock.current_price) / stock.current_price * 100
            metrics['analyst_upside'] = float(upside)
        
        return metrics
    
    def _categorize_market_cap(self, market_cap: Decimal) -> str:
        """Categorize market cap."""
        if market_cap >= 200_000_000_000:
            return 'mega_cap'
        elif market_cap >= 10_000_000_000:
            return 'large_cap'
        elif market_cap >= 2_000_000_000:
            return 'mid_cap'
        elif market_cap >= 300_000_000:
            return 'small_cap'
        else:
            return 'micro_cap'
    
    def _compare_with_peers(self, stock) -> Dict[str, Any]:
        """Compare stock with sector peers."""
        try:
            # Get peers
            peers = self.stock_service.get_stocks_by_sector(stock.sector)
            peers = [p for p in peers if p.id != stock.id][:10]  # Limit to 10 peers
            
            if not peers:
                return {'message': 'No peers found'}
            
            # Compare key metrics
            comparison = {
                'stock': stock.symbol,
                'peers': len(peers),
                'metrics': {}
            }
            
            # Price performance
            if stock.current_price:
                peer_prices = [p.current_price for p in peers if p.current_price]
                if peer_prices:
                    avg_peer_price = sum(peer_prices) / len(peer_prices)
                    comparison['metrics']['price_vs_peers'] = {
                        'stock_price': float(stock.current_price),
                        'peer_avg': float(avg_peer_price),
                        'relative': float((stock.current_price / avg_peer_price - 1) * 100)
                    }
            
            # Market cap
            if stock.market_cap:
                peer_caps = [p.market_cap for p in peers if p.market_cap]
                if peer_caps:
                    avg_peer_cap = sum(peer_caps) / len(peer_caps)
                    comparison['metrics']['market_cap_vs_peers'] = {
                        'stock_cap': float(stock.market_cap),
                        'peer_avg': float(avg_peer_cap),
                        'relative': float((stock.market_cap / avg_peer_cap - 1) * 100)
                    }
            
            return comparison
            
        except Exception as e:
            logger.error(f"Error comparing with peers: {e}")
            return {'error': str(e)}
    
    def _calculate_sector_metrics(self, stock_results: Dict[str, Dict]) -> Dict[str, Any]:
        """Calculate aggregate sector metrics."""
        metrics = {
            'stocks_analyzed': len(stock_results),
            'avg_return': None,
            'avg_volatility': None,
            'bullish_percentage': None
        }
        
        returns = []
        volatilities = []
        trends = []
        
        for result in stock_results.values():
            if 'error' in result:
                continue
            
            technical = result.get('technical', {})
            
            if technical.get('returns', {}).get('total_return'):
                returns.append(technical['returns']['total_return'])
            
            if technical.get('volatility'):
                volatilities.append(technical['volatility'])
            
            if technical.get('trend', {}).get('short_term'):
                trends.append(technical['trend']['short_term'])
        
        if returns:
            metrics['avg_return'] = sum(returns) / len(returns)
        
        if volatilities:
            metrics['avg_volatility'] = sum(volatilities) / len(volatilities)
        
        if trends:
            bullish = trends.count('bullish')
            metrics['bullish_percentage'] = (bullish / len(trends)) * 100
        
        return metrics
    
    def _save_stock_analysis(self, stock, analysis: Dict) -> None:
        """Save stock analysis result."""
        try:
            # Create a simplified portfolio for stock analysis
            # (In production, you might want a different model for stock-only analysis)
            
            with transaction.atomic():
                result = AnalysisResult.objects.create(
                    portfolio=None,  # No portfolio for stock analysis
                    analysis_type='stock_analysis',
                    parameters={
                        'symbol': stock.symbol,
                        'period_days': analysis.get('period_days', 30)
                    },
                    results=analysis,
                    metrics={
                        'symbol': stock.symbol,
                        'volatility': analysis.get('technical', {}).get('volatility'),
                        'rsi': analysis.get('technical', {}).get('rsi_14'),
                        'return': analysis.get('technical', {}).get('returns', {}).get('total_return')
                    }
                )
                
                logger.info(f"Saved stock analysis {result.id} for {stock.symbol}")
                
        except Exception as e:
            logger.error(f"Failed to save stock analysis: {e}")
    
    def get_recent_analyses(
        self,
        limit: int = 10,
        analysis_type: str = None
    ) -> List[AnalysisResult]:
        """Get recent analysis results."""
        query = AnalysisResult.objects.all()
        
        if analysis_type:
            query = query.filter(analysis_type=analysis_type)
        
        return list(query.order_by('-created_at')[:limit])