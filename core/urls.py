"""
API views for the analytics engine.

This module provides REST API endpoints for running stock analysis
and retrieving analysis results.
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from core.services.analytics_engine import AnalyticsEngine, AnalyticsEngineError
from core.models import Stock, AnalysisResult
from core.serializers import AnalysisResultSerializer, StockSerializer

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([])  # Allow unauthenticated for testing
def analyze_stock(request):
    """
    Run analysis on a stock symbol.
    
    POST /api/analyze/
    {
        "symbol": "NVDA",
        "analysis_months": 12
    }
    """
    
    try:
        # Validate input
        symbol = request.data.get('symbol', '').strip().upper()
        analysis_months = request.data.get('analysis_months', 12)
        
        if not symbol:
            return Response(
                {'error': 'Symbol is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not (1 <= analysis_months <= 60):
            return Response(
                {'error': 'Analysis months must be between 1 and 60'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check cache first
        cache_key = f"analysis_{symbol}_{analysis_months}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            logger.info(f"Returning cached analysis for {symbol}")
            return Response({
                'success': True,
                'cached': True,
                'analysis': cached_result,
                'timestamp': timezone.now()
            })
        
        # Run analysis
        logger.info(f"Running analysis for {symbol} ({analysis_months} months)")
        
        engine = AnalyticsEngine()
        result = engine.analyze_stock(symbol, analysis_months)
        
        # Convert result to dict for API response
        analysis_data = {
            'symbol': symbol,
            'signal': result.signal,
            'confidence': result.confidence,
            'metrics': {
                'stock_return': result.stock_return,
                'sector_return': result.sector_return,
                'outperformance': result.outperformance,
                'volatility': result.volatility,
                'current_price': result.current_price,
                'target_price': result.target_price,
                'target_upside': (
                    (result.target_price - result.current_price) / result.current_price 
                    if result.target_price and result.current_price > 0 else None
                )
            },
            'signals': {
                'outperformed_sector': result.signals.outperformed_sector,
                'target_above_price': result.signals.target_above_price,
                'volatility_below_threshold': result.signals.volatility_below_threshold
            },
            'sector': {
                'name': result.sector_name,
                'etf': result.sector_etf
            },
            'analysis': {
                'period_months': result.analysis_period_months,
                'timestamp': result.timestamp.isoformat(),
                'rationale': result.rationale,
                'conditions_met': result.conditions_met
            }
        }
        
        # Cache result
        cache.set(cache_key, analysis_data, 14400)  # 4 hours
        
        logger.info(f"Analysis complete for {symbol}: {result.signal}")
        
        return Response({
            'success': True,
            'cached': False,
            'analysis': analysis_data,
            'timestamp': timezone.now()
        })
        
    except AnalyticsEngineError as e:
        logger.error(f"Analytics engine error for {symbol}: {e}")
        return Response(
            {'error': f'Analysis failed: {str(e)}'}, 
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    
    except Exception as e:
        logger.error(f"Unexpected error analyzing {symbol}: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([])  # Allow unauthenticated for testing
def get_analysis_history(request, symbol):
    """
    Get analysis history for a stock.
    
    GET /api/analyze/{symbol}/history/
    """
    
    try:
        symbol = symbol.upper()
        
        # Get stock
        try:
            stock = Stock.objects.get(symbol=symbol)
        except Stock.DoesNotExist:
            return Response(
                {'error': f'Stock {symbol} not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get recent analyses
        analyses = AnalysisResult.objects.filter(stock=stock).order_by('-analysis_date')[:10]
        
        if not analyses:
            return Response({
                'symbol': symbol,
                'history': [],
                'message': 'No analysis history found'
            })
        
        # Serialize results
        history = []
        for analysis in analyses:
            history.append({
                'signal': analysis.signal,
                'confidence': analysis.confidence,
                'analysis_date': analysis.analysis_date.isoformat(),
                'stock_return': float(analysis.stock_return),
                'sector_return': float(analysis.sector_return),
                'outperformance': float(analysis.outperformance),
                'volatility': float(analysis.volatility),
                'current_price': float(analysis.current_price),
                'target_price': float(analysis.target_price) if analysis.target_price else None,
                'sector_name': analysis.sector_name,
                'conditions_met': {
                    'outperformed_sector': analysis.outperformed_sector,
                    'target_above_price': analysis.target_above_price,
                    'volatility_below_threshold': analysis.volatility_below_threshold
                }
            })
        
        return Response({
            'symbol': symbol,
            'stock_name': stock.name,
            'current_sector': stock.sector.name if stock.sector else None,
            'history': history,
            'total_analyses': len(history)
        })
        
    except Exception as e:
        logger.error(f"Error getting analysis history for {symbol}: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([])  # Allow unauthenticated for testing
def get_stock_info(request, symbol):
    """
    Get basic stock information.
    
    GET /api/stocks/{symbol}/
    """
    
    try:
        symbol = symbol.upper()
        
        # Try to get from database first
        try:
            stock = Stock.objects.get(symbol=symbol)
            
            # Check if data needs updating
            if stock.needs_update:
                # Refresh stock data
                engine = AnalyticsEngine()
                updated_stock = engine._get_or_create_stock(symbol)
                stock = updated_stock
            
            response_data = {
                'symbol': stock.symbol,
                'name': stock.name,
                'sector': {
                    'name': stock.sector.name if stock.sector else None,
                    'code': stock.sector.code if stock.sector else None,
                    'etf': stock.sector.etf_symbol if stock.sector else None
                },
                'exchange': stock.exchange,
                'currency': stock.currency,
                'market_cap': stock.market_cap,
                'current_price': float(stock.current_price) if stock.current_price else None,
                'target_price': float(stock.target_price) if stock.target_price else None,
                'target_upside': stock.target_upside,
                'last_updated': stock.last_updated.isoformat() if stock.last_updated else None,
                'is_active': stock.is_active
            }
            
            # Add latest analysis if available
            latest_analysis = stock.analysis_results.first()
            if latest_analysis:
                response_data['latest_analysis'] = {
                    'signal': latest_analysis.signal,
                    'confidence': latest_analysis.confidence,
                    'analysis_date': latest_analysis.analysis_date.isoformat(),
                    'rationale': latest_analysis.rationale
                }
            
            return Response(response_data)
            
        except Stock.DoesNotExist:
            # Stock not in database, fetch from provider
            engine = AnalyticsEngine()
            stock = engine._get_or_create_stock(symbol)
            
            return Response({
                'symbol': stock.symbol,
                'name': stock.name,
                'sector': {
                    'name': stock.sector.name if stock.sector else None,
                    'code': stock.sector.code if stock.sector else None,
                    'etf': stock.sector.etf_symbol if stock.sector else None
                },
                'exchange': stock.exchange,
                'currency': stock.currency,
                'market_cap': stock.market_cap,
                'current_price': float(stock.current_price) if stock.current_price else None,
                'target_price': float(stock.target_price) if stock.target_price else None,
                'target_upside': stock.target_upside,
                'last_updated': stock.last_updated.isoformat() if stock.last_updated else None,
                'is_active': stock.is_active,
                'note': 'Newly created stock record'
            })
            
    except Exception as e:
        logger.error(f"Error getting stock info for {symbol}: {e}")
        return Response(
            {'error': f'Failed to get stock info: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([])  # Allow unauthenticated for testing
def health_check(request):
    """
    Health check endpoint for analytics engine.
    
    GET /api/analytics/health/
    """
    
    try:
        # Basic system checks
        from core.models import Sector
        from core.services.sector_mapping import validate_sector_mappings
        
        sector_count = Sector.objects.count()
        validation = validate_sector_mappings()
        
        # Test basic calculations
        from core.services.calculations import ReturnCalculator
        calc = ReturnCalculator()
        
        health_data = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'system': {
                'sectors_configured': sector_count,
                'sectors_valid': len(validation['validation_errors']) == 0,
                'cache_available': cache.get('health_test') is None,  # Test cache
            },
            'services': {
                'analytics_engine': True,
                'calculations': True,
                'sector_mapping': True,
                'data_provider': True
            }
        }
        
        # Test cache
        cache.set('health_test', 'ok', 60)
        health_data['system']['cache_available'] = cache.get('health_test') == 'ok'
        
        return Response(health_data)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return Response({
            'status': 'unhealthy',
            'timestamp': timezone.now().isoformat(),
            'error': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([])  # Allow unauthenticated for testing  
def list_sectors(request):
    """
    List all available sectors.
    
    GET /api/sectors/
    """
    
    try:
        from core.models import Sector
        
        sectors = Sector.objects.all().order_by('name')
        
        sector_data = []
        for sector in sectors:
            sector_data.append({
                'code': sector.code,
                'name': sector.name,
                'etf_symbol': sector.etf_symbol,
                'volatility_threshold': float(sector.volatility_threshold),
                'risk_category': sector.risk_category,
                'is_defensive': sector.is_defensive,
                'description': sector.description
            })
        
        return Response({
            'sectors': sector_data,
            'total': len(sector_data)
        })
        
    except Exception as e:
        logger.error(f"Error listing sectors: {e}")
        return Response(
            {'error': 'Failed to list sectors'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )