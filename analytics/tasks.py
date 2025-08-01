"""
Celery tasks for background analytics processing.

Provides asynchronous tasks for analysis, batch processing,
and scheduled updates.
"""

from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.cache import cache
from django.utils import timezone
from django.db import models  # Add this import
from datetime import datetime, timedelta
from typing import List, Dict

from core.models import Stock, Sector  # Add Sector here
from users.models import User
from .models import StockAnalysis, SectorAnalysis, TechnicalIndicator  # Add TechnicalIndicator
from .services import StockAnalyzer, TechnicalAnalyzer, PortfolioAnalyzer

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3)
def analyze_stock_async(self, symbol: str, user_id: int, months: int = 6):
    """
    Asynchronously analyze a stock.
    
    Args:
        symbol: Stock ticker symbol
        user_id: ID of user requesting analysis
        months: Analysis period in months
        
    Returns:
        Analysis ID if successful
    """
    try:
        user = User.objects.get(id=user_id)
        analyzer = StockAnalyzer()
        
        analysis = analyzer.analyze_stock(
            symbol=symbol,
            user=user,
            analysis_months=months,
            force_refresh=True
        )
        
        logger.info(f"Successfully analyzed {symbol} for user {user_id}")
        return analysis.id
        
    except Exception as e:
        logger.error(f"Failed to analyze {symbol}: {str(e)}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task
def batch_analyze_stocks(symbols: List[str], user_id: int, months: int = 6):
    """
    Analyze multiple stocks in batch.
    
    Args:
        symbols: List of stock symbols
        user_id: User ID
        months: Analysis period
        
    Returns:
        Dictionary with results
    """
    results = {
        'successful': [],
        'failed': []
    }
    
    for symbol in symbols:
        try:
            analysis_id = analyze_stock_async.delay(symbol, user_id, months)
            results['successful'].append({
                'symbol': symbol,
                'task_id': str(analysis_id)
            })
        except Exception as e:
            results['failed'].append({
                'symbol': symbol,
                'error': str(e)
            })
            logger.error(f"Failed to queue analysis for {symbol}: {e}")
    
    return results


@shared_task
def update_technical_indicators(symbol: str = None):
    """
    Update technical indicators for stocks.
    
    Args:
        symbol: Specific symbol to update, or None for all active stocks
    """
    analyzer = TechnicalAnalyzer()
    
    if symbol:
        stocks = [Stock.objects.get(symbol=symbol)]
    else:
        # Update active stocks with recent analyses
        cutoff = timezone.now() - timedelta(days=7)
        recent_stocks = StockAnalysis.objects.filter(
            created_at__gte=cutoff
        ).values_list('stock', flat=True).distinct()
        
        stocks = Stock.objects.filter(
            id__in=recent_stocks,
            is_active=True
        )
    
    for stock in stocks:
        try:
            indicators = analyzer.calculate_indicators(stock)
            logger.info(f"Updated {len(indicators)} indicators for {stock.symbol}")
        except Exception as e:
            logger.error(f"Failed to update indicators for {stock.symbol}: {e}")


@shared_task
def generate_sector_analysis():
    """Generate aggregate analysis for all sectors."""
    today = timezone.now().date()
    
    for sector in Sector.objects.all():
        try:
            # Get recent analyses for this sector
            recent_analyses = StockAnalysis.objects.filter(
                stock__sector=sector,
                created_at__date=today
            )
            
            if not recent_analyses.exists():
                continue
            
            # Calculate aggregates
            avg_return = recent_analyses.aggregate(
                avg=models.Avg('stock_return')
            )['avg'] or 0
            
            avg_volatility = recent_analyses.aggregate(
                avg=models.Avg('volatility')
            )['avg'] or 0
            
            # Count signals
            buy_count = recent_analyses.filter(signal='BUY').count()
            hold_count = recent_analyses.filter(signal='HOLD').count()
            sell_count = recent_analyses.filter(signal='SELL').count()
            
            # Get top performers
            top_performers = list(
                recent_analyses.filter(signal='BUY').order_by(
                    '-relative_performance'
                ).values(
                    'stock__symbol',
                    'stock__name',
                    'relative_performance'
                )[:5]
            )
            
            # Save or update
            SectorAnalysis.objects.update_or_create(
                sector=sector,
                analysis_date=today,
                defaults={
                    'avg_return': avg_return,
                    'avg_volatility': avg_volatility,
                    'buy_count': buy_count,
                    'hold_count': hold_count,
                    'sell_count': sell_count,
                    'top_performers': top_performers
                }
            )
            
            logger.info(f"Generated sector analysis for {sector.name}")
            
        except Exception as e:
            logger.error(f"Failed to analyze sector {sector.name}: {e}")


@shared_task
def cleanup_old_analyses():
    """Clean up old analysis records beyond retention period."""
    retention_days = 90  # Keep 90 days of history
    cutoff_date = timezone.now() - timedelta(days=retention_days)
    
    # Delete old analyses
    deleted_count = StockAnalysis.objects.filter(
        created_at__lt=cutoff_date
    ).delete()[0]
    
    logger.info(f"Cleaned up {deleted_count} old analysis records")
    
    # Also clean up old technical indicators
    deleted_indicators = TechnicalIndicator.objects.filter(
        date__lt=cutoff_date.date()
    ).delete()[0]
    
    logger.info(f"Cleaned up {deleted_indicators} old indicator records")


@shared_task
def send_portfolio_alerts(user_id: int):
    """
    Send alerts for significant changes in user's portfolio.
    
    Args:
        user_id: User ID to check
    """
    try:
        user = User.objects.get(id=user_id)
        analyzer = PortfolioAnalyzer()
        
        # Get portfolio analysis
        results = analyzer.analyze_portfolio(user)
        
        # Check for alerts conditions
        alerts = []
        
        # Alert on high number of SELL signals
        if results['recommendations']['sell'] > results['total_stocks'] * 0.3:
            alerts.append({
                'type': 'HIGH_SELL_SIGNALS',
                'message': f"{results['recommendations']['sell']} stocks have SELL signals"
            })
        
        # Alert on new BUY opportunities
        if results['recommendations']['buy'] > 0:
            alerts.append({
                'type': 'BUY_OPPORTUNITIES',
                'message': f"{results['recommendations']['buy']} stocks have BUY signals"
            })
        
        if alerts:
            # Here you would send actual notifications
            # For now, just log them
            logger.info(f"Alerts for user {user_id}: {alerts}")
            
            # Cache alerts for API retrieval
            cache_key = f"portfolio_alerts:{user_id}"
            cache.set(cache_key, alerts, timeout=3600)
        
        return alerts
        
    except Exception as e:
        logger.error(f"Failed to generate alerts for user {user_id}: {e}")
        return []


# Scheduled tasks configuration
# Add these to your celery beat schedule:
"""
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'update-technical-indicators': {
        'task': 'analytics.tasks.update_technical_indicators',
        'schedule': crontab(hour=18, minute=0),  # Daily at 6 PM
    },
    'generate-sector-analysis': {
        'task': 'analytics.tasks.generate_sector_analysis',
        'schedule': crontab(hour=19, minute=0),  # Daily at 7 PM
    },
    'cleanup-old-analyses': {
        'task': 'analytics.tasks.cleanup_old_analyses',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Weekly on Sunday
    },
}
"""