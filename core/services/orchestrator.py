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
    BatchAnalysisService,
    FundamentalAnalyzer
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
        self.fundamental_service = FundamentalAnalyzer(
            self.stock_service,
            self.price_service
        )
        self.batch_service = BatchAnalysisService(
            stock_service=self.stock_service,
            price_service=self.price_service
        )
        
        # Initialize management layer
        self.cache_manager = CacheManager()
        self.transaction_manager = TransactionManager()
        
        logger.info("CoreOrchestrator initialized with all services including FundamentalAnalyzer")
    
    # ==================== Stock Operations ====================
    
    def get_stock_info(self, symbol: str, update: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive stock information including fundamental data.
        
        Args:
            symbol: Stock ticker symbol
            update: Force update from data provider
            
        Returns:
            Dict containing stock info, price data, and fundamental metrics
        """
        try:
            # Get basic stock info
            stock = self.stock_service.get_or_fetch_stock(symbol, force_update=update)
            if not stock:
                raise OrchestratorError(f"Stock {symbol} not found")
            
            # Get latest price data
            latest_price = self.price_service.get_latest_price(stock)
            
            # Get sector info
            sector_info = None
            if stock.sector:
                sector_info = {
                    'name': stock.sector.name,
                    'etf_symbol': stock.sector.etf_symbol,
                    'volatility_threshold': float(stock.sector.volatility_threshold)
                }
            
            return {
                'symbol': stock.symbol,
                'name': stock.name,
                'exchange': stock.exchange,
                'sector': sector_info,
                'current_price': float(stock.current_price) if stock.current_price else None,
                'target_price': float(stock.target_price) if stock.target_price else None,
                'market_cap': stock.market_cap,
                'latest_price_data': latest_price,
                'last_updated': stock.updated_at
            }
            
        except Exception as e:
            logger.error(f"Error getting stock info for {symbol}: {str(e)}")
            raise OrchestratorError(f"Failed to get stock info: {str(e)}")
    
    # ==================== Analysis Operations ====================
    
    def perform_comprehensive_analysis(
        self,
        symbol: str,
        months: int = 6,
        include_technical: bool = True,
        include_fundamental: bool = True
    ) -> Dict[str, Any]:
        """
        Perform comprehensive analysis including technical and fundamental.
        
        Args:
            symbol: Stock ticker symbol
            months: Analysis period in months
            include_technical: Include technical indicators
            include_fundamental: Include fundamental analysis
            
        Returns:
            Dict containing all analysis results
        """
        cache_key = f"comprehensive_analysis:{symbol}:{months}:{include_technical}:{include_fundamental}"
        cached_result = self.cache_manager.get(cache_key)
        if cached_result:
            return cached_result
        
        try:
            results = {
                'symbol': symbol,
                'analysis_date': timezone.now(),
                'period_months': months
            }
            
            # Get stock info first
            stock_info = self.get_stock_info(symbol)
            results['stock_info'] = stock_info
            
            # Run three-factor model analysis
            engine_result = self.analytics_engine.analyze_stock(symbol, months)
            results['three_factor_analysis'] = {
                'recommendation': engine_result.recommendation,
                'confidence': float(engine_result.confidence),
                'signals': engine_result.signals,
                'metrics': engine_result.metrics
            }
            
            # Technical analysis
            if include_technical:
                end_date = timezone.now()
                start_date = end_date - timedelta(days=months * 30)
                technical_result = self.technical_service.analyze(
                    symbol, start_date, end_date
                )
                results['technical_analysis'] = technical_result
            
            # Fundamental analysis
            if include_fundamental:
                fundamental_result = self.fundamental_service.analyze(symbol)
                results['fundamental_analysis'] = fundamental_result
            
            # Generate combined recommendation
            results['combined_recommendation'] = self._generate_combined_recommendation(results)
            
            # Cache the results
            self.cache_manager.set(cache_key, results, timeout=3600)
            
            return results
            
        except Exception as e:
            logger.error(f"Comprehensive analysis failed for {symbol}: {str(e)}")
            raise OrchestratorError(f"Analysis failed: {str(e)}")
    
    def analyze_portfolio(
        self,
        portfolio_id: int,
        include_recommendations: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze entire portfolio including fundamental metrics.
        
        Args:
            portfolio_id: Portfolio ID
            include_recommendations: Include buy/sell recommendations
            
        Returns:
            Dict containing portfolio analysis
        """
        try:
            # Get portfolio
            portfolio = UserPortfolio.objects.get(id=portfolio_id)
            
            # Analyze each holding
            holdings_analysis = []
            total_value = Decimal('0')
            
            for holding in portfolio.holdings.all():
                stock_analysis = {
                    'symbol': holding.stock.symbol,
                    'shares': holding.shares,
                    'avg_cost': float(holding.average_cost),
                    'current_price': float(holding.stock.current_price),
                    'market_value': float(holding.current_value),
                    'gain_loss': float(holding.total_gain_loss),
                    'gain_loss_pct': float(holding.gain_loss_percentage)
                }
                
                # Add fundamental metrics
                try:
                    fundamental = self.fundamental_service.analyze(holding.stock.symbol)
                    stock_analysis['fundamental_score'] = fundamental['fundamental_score']
                    stock_analysis['financial_health'] = fundamental['financial_health']['rating']
                    
                    if include_recommendations:
                        stock_analysis['recommendation'] = fundamental['recommendation']
                except Exception as e:
                    logger.warning(f"Fundamental analysis failed for {holding.stock.symbol}: {e}")
                
                holdings_analysis.append(stock_analysis)
                total_value += holding.current_value
            
            # Calculate portfolio metrics
            portfolio_metrics = self.calculations_service.calculate_portfolio_metrics(
                portfolio.id
            )
            
            return {
                'portfolio_id': portfolio.id,
                'portfolio_name': portfolio.name,
                'total_value': float(total_value),
                'holdings': holdings_analysis,
                'metrics': portfolio_metrics,
                'analysis_date': timezone.now()
            }
            
        except Exception as e:
            logger.error(f"Portfolio analysis failed: {str(e)}")
            raise OrchestratorError(f"Portfolio analysis failed: {str(e)}")
    
    # ==================== Batch Operations ====================
    
    def batch_analyze_stocks(
        self,
        symbols: List[str],
        analysis_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Perform batch analysis on multiple stocks.
        
        Args:
            symbols: List of stock symbols
            analysis_types: Types of analysis to perform
                          ['technical', 'fundamental', 'three_factor']
            
        Returns:
            Dict with results for each symbol
        """
        if not analysis_types:
            analysis_types = ['three_factor', 'fundamental']
        
        results = {}
        successful = 0
        failed = []
        
        for symbol in symbols:
            try:
                stock_results = {}
                
                if 'three_factor' in analysis_types:
                    engine_result = self.analytics_engine.analyze_stock(symbol)
                    stock_results['three_factor'] = {
                        'recommendation': engine_result.recommendation,
                        'confidence': float(engine_result.confidence)
                    }
                
                if 'fundamental' in analysis_types:
                    fundamental = self.fundamental_service.analyze(symbol)
                    stock_results['fundamental'] = {
                        'score': fundamental['fundamental_score'],
                        'recommendation': fundamental['recommendation'],
                        'health_rating': fundamental['financial_health']['rating']
                    }
                
                if 'technical' in analysis_types:
                    end_date = timezone.now()
                    start_date = end_date - timedelta(days=180)
                    technical = self.technical_service.analyze(symbol, start_date, end_date)
                    stock_results['technical'] = technical
                
                results[symbol] = stock_results
                successful += 1
                
            except Exception as e:
                logger.error(f"Batch analysis failed for {symbol}: {e}")
                failed.append({'symbol': symbol, 'error': str(e)})
        
        return {
            'results': results,
            'summary': {
                'total': len(symbols),
                'successful': successful,
                'failed': len(failed)
            },
            'failed_symbols': failed,
            'timestamp': timezone.now()
        }
    
    # ==================== Helper Methods ====================
    
    def _generate_combined_recommendation(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a combined recommendation from multiple analysis types.
        """
        recommendations = []
        weights = []
        
        # Three-factor model (highest weight)
        if 'three_factor_analysis' in analysis_results:
            rec = analysis_results['three_factor_analysis']['recommendation']
            conf = analysis_results['three_factor_analysis']['confidence']
            recommendations.append(rec)
            weights.append(conf * 2)  # Double weight for three-factor
        
        # Fundamental analysis
        if 'fundamental_analysis' in analysis_results:
            fund_rec = analysis_results['fundamental_analysis']['recommendation']
            rec = fund_rec['recommendation']
            conf_map = {'HIGH': 0.9, 'MEDIUM': 0.6, 'LOW': 0.3}
            conf = conf_map.get(fund_rec['confidence'], 0.5)
            recommendations.append(rec)
            weights.append(conf)
        
        # Calculate weighted recommendation
        if not recommendations:
            return {'recommendation': 'HOLD', 'confidence': 'LOW', 'method': 'default'}
        
        # Convert to numeric scores
        rec_scores = {'BUY': 1, 'HOLD': 0, 'SELL': -1}
        weighted_score = sum(
            rec_scores[rec] * weight 
            for rec, weight in zip(recommendations, weights)
        ) / sum(weights)
        
        # Convert back to recommendation
        if weighted_score > 0.3:
            final_rec = 'BUY'
        elif weighted_score < -0.3:
            final_rec = 'SELL'
        else:
            final_rec = 'HOLD'
        
        # Determine confidence
        avg_confidence = sum(weights) / len(weights)
        if avg_confidence > 0.7:
            confidence = 'HIGH'
        elif avg_confidence > 0.4:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'
        
        return {
            'recommendation': final_rec,
            'confidence': confidence,
            'weighted_score': weighted_score,
            'method': 'combined',
            'sources': len(recommendations)
        }


# Singleton instance
_orchestrator_instance = None


def get_orchestrator() -> CoreOrchestrator:
    """
    Get or create the singleton orchestrator instance.
    
    Returns:
        CoreOrchestrator: The singleton orchestrator instance
    """
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = CoreOrchestrator()
    return _orchestrator_instance