"""
Core orchestrator service that coordinates between all app services.

This is the main entry point for all business logic operations,
ensuring proper coordination between data, analytics, and user services.
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date, timedelta
from decimal import Decimal

from django.db import transaction
from django.core.cache import cache
from django.utils import timezone

# Import services from their proper locations
from data.services import StockService, PriceService, SectorService
from analytics.services import (
    AnalyticsEngine,
    AnalysisService,
    TechnicalIndicators,
    FinancialCalculations,
    BatchAnalysisService
)
from users.models import User, UserPortfolio, PortfolioStock

from .cache_manager import CacheManager
from .transaction_manager import TransactionManager

logger = logging.getLogger(__name__)


class OrchestratorError(Exception):
    """Custom exception for orchestrator errors."""
    pass


class CoreOrchestrator:
    """
    Main orchestrator that coordinates all services.
    
    This class provides a unified interface for all operations,
    handling service coordination, caching, and transaction management.
    """
    
    def __init__(self):
        # Initialize service layer
        self.stock_service = StockService()
        self.price_service = PriceService()
        self.sector_service = SectorService()
        
        # Initialize analytics layer
        self.analytics_engine = AnalyticsEngine()
        self.analysis_service = AnalysisService()
        self.technical_service = TechnicalIndicators(
            self.stock_service,
            self.price_service
        )
        self.calculations_service = FinancialCalculations(
            self.stock_service,
            self.price_service,
            self.sector_service
        )
        self.batch_service = BatchAnalysisService(
            stock_service=self.stock_service,
            price_service=self.price_service
        )
        
        # Initialize management layer
        self.cache_manager = CacheManager()
        self.transaction_manager = TransactionManager()
        
        logger.info("CoreOrchestrator initialized with all services")
    
    # ==================== Stock Operations ====================
    
    def get_stock_info(self, symbol: str, update: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive stock information.
        
        Args:
            symbol: Stock ticker symbol
            update: Force update from data provider
            
        Returns:
            Dictionary with stock info and current metrics
        """
        cache_key = f"stock_info_{symbol}"
        
        if not update:
            cached = self.cache_manager.get(cache_key)
            if cached:
                return cached
        
        try:
            # Get stock data
            stock = self.stock_service.get_or_create_stock(symbol, update_if_stale=update)
            
            # Get latest price
            latest_price = self.price_service.get_latest_price(stock)
            
            # Get price statistics
            price_stats = self.price_service.get_price_range(stock, days=30)
            
            # Build response
            result = {
                'symbol': stock.symbol,
                'name': stock.name,
                'sector': stock.sector.name if stock.sector else 'Unknown',
                'exchange': stock.exchange,
                'currency': stock.currency,
                'current_price': float(stock.current_price) if stock.current_price else None,
                'target_price': float(stock.target_price) if stock.target_price else None,
                'market_cap': float(stock.market_cap) if stock.market_cap else None,
                'price_stats': {
                    'high_30d': float(price_stats['high']) if price_stats['high'] else None,
                    'low_30d': float(price_stats['low']) if price_stats['low'] else None,
                    'avg_30d': float(price_stats['avg']) if price_stats['avg'] else None,
                },
                'last_updated': stock.last_updated.isoformat() if stock.last_updated else None
            }
            
            # Cache for 5 minutes
            self.cache_manager.set(cache_key, result, timeout=300)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting stock info for {symbol}: {e}")
            raise OrchestratorError(f"Failed to get stock info: {str(e)}")
    
    def search_stocks(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for stocks by symbol or name.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching stocks
        """
        try:
            stocks = self.stock_service.search_stocks(query, limit)
            
            return [
                {
                    'symbol': stock.symbol,
                    'name': stock.name,
                    'sector': stock.sector.name if stock.sector else None,
                    'exchange': stock.exchange,
                    'current_price': float(stock.current_price) if stock.current_price else None
                }
                for stock in stocks
            ]
            
        except Exception as e:
            logger.error(f"Error searching stocks: {e}")
            raise OrchestratorError(f"Stock search failed: {str(e)}")
    
    # ==================== Portfolio Operations ====================
    
    def create_portfolio(self, user: User, name: str, description: str = "") -> UserPortfolio:
        """
        Create a new portfolio for a user.
        
        Args:
            user: User instance
            name: Portfolio name
            description: Optional description
            
        Returns:
            Created portfolio
        """
        try:
            with self.transaction_manager.atomic():
                portfolio = UserPortfolio.objects.create(
                    user=user,
                    name=name,
                    description=description,
                    is_active=True
                )
                
                logger.info(f"Created portfolio {portfolio.id} for user {user.id}")
                return portfolio
                
        except Exception as e:
            logger.error(f"Error creating portfolio: {e}")
            raise OrchestratorError(f"Failed to create portfolio: {str(e)}")
    
    def add_stock_to_portfolio(
        self,
        portfolio_id: int,
        symbol: str,
        quantity: Decimal,
        purchase_price: Decimal,
        purchase_date: date = None
    ) -> PortfolioStock:
        """
        Add a stock to a portfolio.
        
        Args:
            portfolio_id: Portfolio ID
            symbol: Stock symbol
            quantity: Number of shares
            purchase_price: Price per share
            purchase_date: Date of purchase (default: today)
            
        Returns:
            Created PortfolioStock instance
        """
        try:
            with self.transaction_manager.atomic():
                # Get or create stock
                stock = self.stock_service.get_or_create_stock(symbol)
                
                # Get portfolio
                portfolio = UserPortfolio.objects.get(id=portfolio_id)
                
                # Create portfolio stock
                portfolio_stock = PortfolioStock.objects.create(
                    portfolio=portfolio,
                    stock=stock,
                    quantity=quantity,
                    purchase_price=purchase_price,
                    purchase_date=purchase_date or timezone.now().date(),
                    is_active=True
                )
                
                # Invalidate portfolio cache
                self.cache_manager.delete_pattern(f"portfolio_{portfolio_id}_*")
                
                logger.info(f"Added {symbol} to portfolio {portfolio_id}")
                return portfolio_stock
                
        except UserPortfolio.DoesNotExist:
            raise OrchestratorError("Portfolio not found")
        except Exception as e:
            logger.error(f"Error adding stock to portfolio: {e}")
            raise OrchestratorError(f"Failed to add stock: {str(e)}")
    
    def get_portfolio_summary(self, portfolio_id: int) -> Dict[str, Any]:
        """
        Get portfolio summary with current values.
        
        Args:
            portfolio_id: Portfolio ID
            
        Returns:
            Portfolio summary
        """
        cache_key = f"portfolio_summary_{portfolio_id}"
        cached = self.cache_manager.get(cache_key)
        if cached:
            return cached
        
        try:
            # Get portfolio
            portfolio = UserPortfolio.objects.get(id=portfolio_id)
            
            # Calculate current value
            current_value = self.calculations_service.calculate_portfolio_value(portfolio_id)
            
            # Get allocation
            allocation = self.calculations_service.calculate_stock_allocation(portfolio_id)
            
            # Build summary
            summary = {
                'portfolio_id': portfolio_id,
                'name': portfolio.name,
                'created_date': portfolio.created_at.isoformat(),
                'total_value': float(current_value),
                'holdings_count': len(allocation),
                'top_holdings': allocation[:5],  # Top 5 holdings
                'last_updated': timezone.now().isoformat()
            }
            
            # Cache for 5 minutes
            self.cache_manager.set(cache_key, summary, timeout=300)
            
            return summary
            
        except UserPortfolio.DoesNotExist:
            raise OrchestratorError("Portfolio not found")
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            raise OrchestratorError(f"Failed to get portfolio summary: {str(e)}")
    
    # ==================== Analysis Operations ====================
    
    def analyze_portfolio(
        self,
        user: User,
        portfolio_id: int,
        analysis_period: int = 30
    ) -> Dict[str, Any]:
        """
        Perform comprehensive portfolio analysis.
        
        Args:
            user: User requesting analysis
            portfolio_id: Portfolio to analyze
            analysis_period: Days to analyze
            
        Returns:
            Analysis results
        """
        try:
            # Verify ownership
            portfolio = UserPortfolio.objects.get(
                id=portfolio_id,
                user=user
            )
            
            # Use analytics engine
            analysis = self.analytics_engine.analyze_portfolio(
                portfolio_id,
                analysis_period,
                include_technical=True
            )
            
            # Update user stats
            user.total_analyses_count += 1
            user.last_analysis_date = timezone.now()
            user.save()
            
            return analysis
            
        except UserPortfolio.DoesNotExist:
            raise OrchestratorError("Portfolio not found or access denied")
        except Exception as e:
            logger.error(f"Error analyzing portfolio: {e}")
            raise OrchestratorError(f"Analysis failed: {str(e)}")
    
    def analyze_stock(
        self,
        symbol: str,
        analysis_period: int = 30,
        include_technical: bool = True
    ) -> Dict[str, Any]:
        """
        Perform stock analysis.
        
        Args:
            symbol: Stock symbol
            analysis_period: Days to analyze
            include_technical: Include technical indicators
            
        Returns:
            Analysis results
        """
        try:
            analysis_types = ['fundamental', 'comparison']
            if include_technical:
                analysis_types.append('technical')
            
            return self.analytics_engine.analyze_stock(
                symbol,
                analysis_period,
                analysis_types
            )
            
        except Exception as e:
            logger.error(f"Error analyzing stock {symbol}: {e}")
            raise OrchestratorError(f"Stock analysis failed: {str(e)}")
    
    def screen_stocks(
        self,
        criteria: Dict[str, Any],
        universe: List[str] = None
    ) -> Dict[str, Any]:
        """
        Screen stocks based on criteria.
        
        Args:
            criteria: Screening criteria
            universe: List of symbols to screen
            
        Returns:
            Screening results
        """
        try:
            return self.analytics_engine.screen_stocks(criteria, universe)
        except Exception as e:
            logger.error(f"Error screening stocks: {e}")
            raise OrchestratorError(f"Stock screening failed: {str(e)}")
    
    def compare_stocks(
        self,
        symbols: List[str],
        metrics: List[str] = None
    ) -> Dict[str, Any]:
        """
        Compare multiple stocks.
        
        Args:
            symbols: List of symbols to compare
            metrics: Metrics to compare
            
        Returns:
            Comparison results
        """
        try:
            return self.analytics_engine.compare_stocks(symbols, metrics)
        except Exception as e:
            logger.error(f"Error comparing stocks: {e}")
            raise OrchestratorError(f"Stock comparison failed: {str(e)}")
    
    # ==================== Batch Operations ====================
    
    def batch_update_prices(self, symbols: List[str] = None) -> Dict[str, Any]:
        """
        Update prices for multiple stocks.
        
        Args:
            symbols: List of symbols (None = all active stocks)
            
        Returns:
            Update results
        """
        try:
            if not symbols:
                # Get all active stocks
                stocks = self.stock_service.get_stocks_needing_update(hours=24)
                symbols = [s.symbol for s in stocks[:50]]  # Limit to 50
            
            # Update in batches
            results = self.stock_service.bulk_update_stocks(symbols)
            
            # Clear relevant caches
            for symbol in results['updated']:
                self.cache_manager.delete_pattern(f"*{symbol}*")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in batch price update: {e}")
            raise OrchestratorError(f"Batch update failed: {str(e)}")
    
    def batch_analyze_portfolios(
        self,
        user: User,
        portfolio_ids: List[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple portfolios.
        
        Args:
            user: User requesting analysis
            portfolio_ids: List of portfolio IDs (None = all user portfolios)
            
        Returns:
            List of analysis results
        """
        try:
            if not portfolio_ids:
                portfolios = UserPortfolio.objects.filter(
                    user=user,
                    is_active=True
                )
                portfolio_ids = [p.id for p in portfolios]
            
            results = []
            for portfolio_id in portfolio_ids:
                try:
                    analysis = self.analyze_portfolio(user, portfolio_id)
                    results.append({
                        'portfolio_id': portfolio_id,
                        'status': 'success',
                        'analysis': analysis
                    })
                except Exception as e:
                    results.append({
                        'portfolio_id': portfolio_id,
                        'status': 'error',
                        'error': str(e)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in batch portfolio analysis: {e}")
            raise OrchestratorError(f"Batch analysis failed: {str(e)}")
    
    # ==================== Report Generation ====================
    
    def generate_portfolio_report(
        self,
        user: User,
        portfolio_id: int,
        report_type: str = 'comprehensive'
    ) -> Dict[str, Any]:
        """
        Generate a detailed portfolio report.
        
        Args:
            user: User requesting report
            portfolio_id: Portfolio ID
            report_type: Type of report
            
        Returns:
            Report data
        """
        try:
            return self.analysis_service.create_portfolio_report(
                user,
                portfolio_id,
                report_type
            )
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            raise OrchestratorError(f"Report generation failed: {str(e)}")
    
    # ==================== Market Data Operations ====================
    
    def get_market_overview(self) -> Dict[str, Any]:
        """Get market overview with major indices."""
        cache_key = "market_overview"
        cached = self.cache_manager.get(cache_key)
        if cached:
            return cached
        
        try:
            # Analyze major indices
            indices = ['SPY', 'QQQ', 'DIA', 'IWM']  # S&P, NASDAQ, Dow, Russell
            
            overview = {
                'timestamp': timezone.now().isoformat(),
                'indices': {}
            }
            
            for symbol in indices:
                try:
                    stock_info = self.get_stock_info(symbol)
                    
                    # Get 1-day return
                    end_date = timezone.now().date()
                    start_date = end_date - timedelta(days=5)
                    
                    technical = self.technical_service.analyze(
                        symbol,
                        datetime.combine(start_date, datetime.min.time()),
                        datetime.combine(end_date, datetime.min.time())
                    )
                    
                    overview['indices'][symbol] = {
                        'name': stock_info['name'],
                        'price': stock_info['current_price'],
                        'change_pct': technical.get('returns', {}).get('total_return', 0)
                    }
                except Exception as e:
                    logger.warning(f"Failed to get data for {symbol}: {e}")
            
            # Cache for 5 minutes
            self.cache_manager.set(cache_key, overview, timeout=300)
            
            return overview
            
        except Exception as e:
            logger.error(f"Error getting market overview: {e}")
            raise OrchestratorError(f"Market overview failed: {str(e)}")
    
    def get_sector_performance(self) -> Dict[str, Any]:
        """Get performance by sector."""
        cache_key = "sector_performance"
        cached = self.cache_manager.get(cache_key)
        if cached:
            return cached
        
        try:
            sectors = self.sector_service.get_all_sectors()
            
            performance = {
                'timestamp': timezone.now().isoformat(),
                'sectors': []
            }
            
            for sector in sectors:
                try:
                    # Analyze sector ETF
                    etf_info = self.get_stock_info(sector.etf_symbol)
                    
                    # Get sector statistics
                    stats = self.sector_service.get_sector_statistics(sector)
                    
                    performance['sectors'].append({
                        'name': sector.name,
                        'code': sector.code,
                        'etf_symbol': sector.etf_symbol,
                        'etf_price': etf_info['current_price'],
                        'stock_count': stats['stocks']['total'],
                        'avg_market_cap': stats['market_cap'].get('avg_market_cap')
                    })
                except Exception as e:
                    logger.warning(f"Failed to get data for sector {sector.code}: {e}")
            
            # Sort by name
            performance['sectors'].sort(key=lambda x: x['name'])
            
            # Cache for 15 minutes
            self.cache_manager.set(cache_key, performance, timeout=900)
            
            return performance
            
        except Exception as e:
            logger.error(f"Error getting sector performance: {e}")
            raise OrchestratorError(f"Sector performance failed: {str(e)}")
    
    # ==================== Health Check ====================
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform system health check.
        
        Returns:
            Health status of all services
        """
        health = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'services': {}
        }
        
        # Check database
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health['services']['database'] = {'status': 'healthy'}
        except Exception as e:
            health['services']['database'] = {'status': 'unhealthy', 'error': str(e)}
            health['status'] = 'unhealthy'
        
        # Check cache
        try:
            cache.set('health_check', 'ok', 1)
            if cache.get('health_check') == 'ok':
                health['services']['cache'] = {'status': 'healthy'}
            else:
                health['services']['cache'] = {'status': 'unhealthy', 'error': 'Cache not working'}
                health['status'] = 'unhealthy'
        except Exception as e:
            health['services']['cache'] = {'status': 'unhealthy', 'error': str(e)}
            health['status'] = 'unhealthy'
        
        # Check data provider
        try:
            from data.providers.yahoo_finance import YahooFinanceProvider
            provider = YahooFinanceProvider()
            if provider.validate_connection():
                health['services']['data_provider'] = {'status': 'healthy'}
            else:
                health['services']['data_provider'] = {'status': 'unhealthy', 'error': 'Provider validation failed'}
                health['status'] = 'degraded'
        except Exception as e:
            health['services']['data_provider'] = {'status': 'unhealthy', 'error': str(e)}
            health['status'] = 'degraded'
        
        return health


# Convenience function for getting orchestrator instance
_orchestrator_instance = None

def get_orchestrator() -> CoreOrchestrator:
    """Get singleton instance of CoreOrchestrator."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = CoreOrchestrator()
    return _orchestrator_instance