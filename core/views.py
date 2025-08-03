"""
Core views using the orchestrator pattern.

All views now use CoreOrchestrator for business logic operations.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.utils import timezone
from django.core.paginator import Paginator

from core.services import get_orchestrator, OrchestratorError
from users.models import UserPortfolio

logger = logging.getLogger(__name__)


def index(request):
    """Home page with market overview."""
    orchestrator = get_orchestrator()
    
    try:
        # Get market overview
        market_data = orchestrator.get_market_overview()
        
        # Get sector performance
        sector_data = orchestrator.get_sector_performance()
        
        context = {
            'market_data': market_data,
            'sector_data': sector_data,
            'last_updated': timezone.now()
        }
        
        return render(request, 'core/index.html', context)
        
    except OrchestratorError as e:
        logger.error(f"Error loading index: {e}")
        messages.error(request, "Unable to load market data. Please try again later.")
        return render(request, 'core/index.html', {})


@login_required
def dashboard(request):
    """User dashboard with portfolio summary."""
    orchestrator = get_orchestrator()
    
    try:
        # Get user portfolios
        portfolios = UserPortfolio.objects.filter(
            user=request.user,
            is_active=True
        ).order_by('-created_at')
        
        # Get summary for each portfolio
        portfolio_summaries = []
        total_value = Decimal('0')
        
        for portfolio in portfolios:
            try:
                summary = orchestrator.get_portfolio_summary(portfolio.id)
                portfolio_summaries.append(summary)
                total_value += Decimal(str(summary['total_value']))
            except Exception as e:
                logger.error(f"Error getting summary for portfolio {portfolio.id}: {e}")
        
        # Get recent analyses
        recent_analyses = orchestrator.analysis_service.get_analysis_history(
            request.user,
            limit=5
        )
        
        context = {
            'portfolios': portfolios,
            'portfolio_summaries': portfolio_summaries,
            'total_value': total_value,
            'recent_analyses': recent_analyses,
            'last_updated': timezone.now()
        }
        
        return render(request, 'core/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Dashboard error for user {request.user.id}: {e}")
        messages.error(request, "Error loading dashboard.")
        return render(request, 'core/dashboard.html', {})


@login_required
@require_http_methods(["GET", "POST"])
def analyze_portfolio(request, portfolio_id):
    """Analyze a portfolio."""
    orchestrator = get_orchestrator()
    
    try:
        # Get portfolio and verify ownership
        portfolio = get_object_or_404(
            UserPortfolio,
            id=portfolio_id,
            user=request.user,
            is_active=True
        )
        
        if request.method == 'POST':
            # Get analysis parameters
            period = int(request.POST.get('period', 30))
            
            # Perform analysis
            analysis = orchestrator.analyze_portfolio(
                request.user,
                portfolio_id,
                analysis_period=period
            )
            
            if 'error' in analysis:
                messages.error(request, f"Analysis failed: {analysis['error']}")
                return redirect('portfolio_detail', portfolio_id=portfolio_id)
            
            messages.success(request, "Portfolio analysis completed successfully!")
            
            # Return analysis results
            return render(request, 'core/analysis_results.html', {
                'portfolio': portfolio,
                'analysis': analysis,
                'period': period
            })
        
        # GET request - show analysis form
        return render(request, 'core/analyze_portfolio.html', {
            'portfolio': portfolio
        })
        
    except OrchestratorError as e:
        logger.error(f"Analysis error: {e}")
        messages.error(request, str(e))
        return redirect('dashboard')


@login_required
@require_http_methods(["GET", "POST"])
def analyze_stock(request, symbol=None):
    """Analyze a single stock."""
    orchestrator = get_orchestrator()
    
    if request.method == 'POST':
        symbol = request.POST.get('symbol', '').upper()
        period = int(request.POST.get('period', 30))
        
        if not symbol:
            messages.error(request, "Please enter a stock symbol.")
            return redirect('analyze_stock')
        
        try:
            # Perform stock analysis
            analysis = orchestrator.analyze_stock(
                symbol,
                analysis_period=period,
                include_technical=True
            )
            
            if 'error' in analysis:
                messages.error(request, f"Analysis failed: {analysis['error']}")
                return redirect('analyze_stock')
            
            return render(request, 'core/stock_analysis.html', {
                'analysis': analysis,
                'symbol': symbol,
                'period': period
            })
            
        except OrchestratorError as e:
            logger.error(f"Stock analysis error: {e}")
            messages.error(request, str(e))
            return redirect('analyze_stock')
    
    # GET request - show form or analyze provided symbol
    if symbol:
        try:
            analysis = orchestrator.analyze_stock(symbol)
            return render(request, 'core/stock_analysis.html', {
                'analysis': analysis,
                'symbol': symbol,
                'period': 30
            })
        except:
            messages.error(request, f"Unable to analyze {symbol}")
    
    return render(request, 'core/analyze_stock_form.html')


@login_required
def stock_search(request):
    """Search for stocks."""
    orchestrator = get_orchestrator()
    query = request.GET.get('q', '')
    
    if not query:
        return JsonResponse({'results': []})
    
    try:
        results = orchestrator.search_stocks(query, limit=10)
        return JsonResponse({'results': results})
    except Exception as e:
        logger.error(f"Stock search error: {e}")
        return JsonResponse({'error': 'Search failed'}, status=500)


@login_required
@require_http_methods(["POST"])
def add_to_portfolio(request):
    """Add a stock to a portfolio."""
    orchestrator = get_orchestrator()
    
    try:
        # Get form data
        portfolio_id = request.POST.get('portfolio_id')
        symbol = request.POST.get('symbol', '').upper()
        quantity = Decimal(request.POST.get('quantity', '0'))
        purchase_price = Decimal(request.POST.get('purchase_price', '0'))
        purchase_date = request.POST.get('purchase_date')
        
        # Validate
        if not all([portfolio_id, symbol, quantity > 0, purchase_price > 0]):
            return JsonResponse({'error': 'Invalid input'}, status=400)
        
        # Parse date
        if purchase_date:
            purchase_date = datetime.strptime(purchase_date, '%Y-%m-%d')
        else:
            purchase_date = timezone.now()
        
        # Add to portfolio
        portfolio_stock = orchestrator.add_stock_to_portfolio(
            int(portfolio_id),
            symbol,
            quantity,
            purchase_price,
            purchase_date
        )
        
        messages.success(request, f"Added {symbol} to portfolio successfully!")
        
        return JsonResponse({
            'success': True,
            'message': f'Added {quantity} shares of {symbol}'
        })
        
    except OrchestratorError as e:
        logger.error(f"Add to portfolio error: {e}")
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return JsonResponse({'error': 'Failed to add stock'}, status=500)


@login_required
def compare_stocks(request):
    """Compare multiple stocks."""
    orchestrator = get_orchestrator()
    symbols = request.GET.get('symbols', '').split(',')
    
    if len(symbols) < 2:
        messages.error(request, "Please select at least 2 stocks to compare.")
        return redirect('stock_search')
    
    try:
        # Clean symbols
        symbols = [s.strip().upper() for s in symbols if s.strip()]
        
        # Perform comparison
        comparison = orchestrator.compare_stocks(symbols)
        
        return render(request, 'core/stock_comparison.html', {
            'comparison': comparison,
            'symbols': symbols
        })
        
    except OrchestratorError as e:
        logger.error(f"Comparison error: {e}")
        messages.error(request, str(e))
        return redirect('dashboard')


@login_required
def screen_stocks(request):
    """Stock screening tool."""
    orchestrator = get_orchestrator()
    
    if request.method == 'POST':
        # Build criteria from form
        criteria = {}
        
        # Price criteria
        if request.POST.get('price_min'):
            criteria['price_min'] = float(request.POST['price_min'])
        if request.POST.get('price_max'):
            criteria['price_max'] = float(request.POST['price_max'])
        
        # Volatility criteria
        if request.POST.get('volatility_max'):
            criteria['volatility_max'] = float(request.POST['volatility_max'])
        
        # RSI criteria
        if request.POST.get('rsi_min'):
            criteria['rsi_min'] = float(request.POST['rsi_min'])
        if request.POST.get('rsi_max'):
            criteria['rsi_max'] = float(request.POST['rsi_max'])
        
        # Trend criteria
        if request.POST.get('trend'):
            criteria['trend'] = request.POST['trend']
        
        try:
            # Run screening
            results = orchestrator.screen_stocks(criteria)
            
            return render(request, 'core/screening_results.html', {
                'results': results,
                'criteria': criteria
            })
            
        except OrchestratorError as e:
            logger.error(f"Screening error: {e}")
            messages.error(request, str(e))
    
    return render(request, 'core/stock_screener.html')


@cache_page(60 * 5)  # Cache for 5 minutes
def market_overview(request):
    """Public market overview page."""
    orchestrator = get_orchestrator()
    
    try:
        market_data = orchestrator.get_market_overview()
        sector_data = orchestrator.get_sector_performance()
        
        return render(request, 'core/market_overview.html', {
            'market_data': market_data,
            'sector_data': sector_data
        })
    except:
        return render(request, 'core/market_overview.html', {
            'error': 'Unable to load market data'
        })


def health_check(request):
    """System health check endpoint."""
    orchestrator = get_orchestrator()
    
    try:
        health = orchestrator.health_check()
        status_code = 200 if health['status'] == 'healthy' else 503
        return JsonResponse(health, status=status_code)
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=503)


# API-style endpoints using JsonResponse

@login_required
def api_portfolio_value(request, portfolio_id):
    """Get current portfolio value."""
    orchestrator = get_orchestrator()
    
    try:
        # Verify ownership
        portfolio = get_object_or_404(
            UserPortfolio,
            id=portfolio_id,
            user=request.user
        )
        
        value = orchestrator.calculations_service.calculate_portfolio_value(portfolio_id)
        
        return JsonResponse({
            'portfolio_id': portfolio_id,
            'value': float(value),
            'currency': 'USD',
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Portfolio value error: {e}")
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_portfolio_allocation(request, portfolio_id):
    """Get portfolio allocation."""
    orchestrator = get_orchestrator()
    
    try:
        # Verify ownership
        portfolio = get_object_or_404(
            UserPortfolio,
            id=portfolio_id,
            user=request.user
        )
        
        allocation = orchestrator.calculations_service.calculate_stock_allocation(portfolio_id)
        
        return JsonResponse({
            'portfolio_id': portfolio_id,
            'allocation': allocation,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Portfolio allocation error: {e}")
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_batch_update_prices(request):
    """Trigger batch price update."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    orchestrator = get_orchestrator()
    
    try:
        symbols = request.POST.getlist('symbols[]')
        results = orchestrator.batch_update_prices(symbols)
        
        return JsonResponse({
            'success': True,
            'results': results,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Batch update error: {e}")
        return JsonResponse({'error': str(e)}, status=500)
    
# Compatibility wrappers for old URLs
def get_stock_info(request, symbol):
    """Wrapper for backward compatibility."""
    return analyze_stock(request, symbol)

def get_analysis_history(request, symbol):
    """Wrapper for backward compatibility."""
    # Redirect to analysis or return empty response
    return JsonResponse({'history': []})