"""
Analytics views using the orchestrator.
"""

import logging
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from core.services import get_orchestrator, OrchestratorError
from users.models import UserPortfolio
from analytics.models import AnalysisResult

logger = logging.getLogger(__name__)


@login_required
def analytics_dashboard(request):
    """Analytics dashboard showing recent analyses and options."""
    orchestrator = get_orchestrator()
    
    try:
        # Get user's portfolios
        portfolios = UserPortfolio.objects.filter(
            user=request.user,
            is_active=True
        ).order_by('name')
        
        # Get recent analysis results
        recent_analyses = AnalysisResult.objects.filter(
            portfolio__user=request.user
        ).select_related('portfolio').order_by('-created_at')[:10]
        
        # Get market overview
        market_overview = orchestrator.get_market_overview()
        
        context = {
            'portfolios': portfolios,
            'recent_analyses': recent_analyses,
            'market_overview': market_overview,
            'analysis_types': [
                {'value': 'comprehensive', 'label': 'Comprehensive Analysis'},
                {'value': 'performance', 'label': 'Performance Report'},
                {'value': 'risk', 'label': 'Risk Assessment'},
            ]
        }
        
        return render(request, 'analytics/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Analytics dashboard error: {e}")
        messages.error(request, "Error loading analytics dashboard.")
        return render(request, 'analytics/dashboard.html', {})


@login_required
@require_http_methods(["GET", "POST"])
def generate_report(request):
    """Generate portfolio report."""
    orchestrator = get_orchestrator()
    
    if request.method == 'POST':
        portfolio_id = request.POST.get('portfolio_id')
        report_type = request.POST.get('report_type', 'comprehensive')
        
        if not portfolio_id:
            messages.error(request, "Please select a portfolio.")
            return redirect('analytics_dashboard')
        
        try:
            # Generate report
            report = orchestrator.generate_portfolio_report(
                request.user,
                int(portfolio_id),
                report_type
            )
            
            if 'error' in report:
                messages.error(request, report['error'])
                return redirect('analytics_dashboard')
            
            # Success - show report
            return render(request, 'analytics/report.html', {
                'report': report,
                'report_type': report_type
            })
            
        except OrchestratorError as e:
            logger.error(f"Report generation error: {e}")
            messages.error(request, str(e))
            return redirect('analytics_dashboard')
    
    # GET - redirect to dashboard
    return redirect('analytics_dashboard')


@login_required
def technical_analysis(request, symbol):
    """Technical analysis for a stock."""
    orchestrator = get_orchestrator()
    
    try:
        # Get analysis period
        days = int(request.GET.get('days', 90))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get technical indicators
        technical = orchestrator.technical_service.analyze(
            symbol,
            start_date,
            end_date
        )
        
        if 'error' in technical:
            messages.error(request, f"Analysis failed: {technical['error']}")
            return redirect('analyze_stock')
        
        # Get stock info
        stock_info = orchestrator.get_stock_info(symbol)
        
        context = {
            'symbol': symbol,
            'stock_info': stock_info,
            'technical': technical,
            'days': days,
            'start_date': start_date,
            'end_date': end_date
        }
        
        return render(request, 'analytics/technical_analysis.html', context)
        
    except Exception as e:
        logger.error(f"Technical analysis error for {symbol}: {e}")
        messages.error(request, "Unable to perform technical analysis.")
        return redirect('analyze_stock')


@login_required
def batch_analysis(request):
    """Batch analysis for multiple portfolios."""
    orchestrator = get_orchestrator()
    
    if request.method == 'POST':
        portfolio_ids = request.POST.getlist('portfolio_ids[]')
        
        if not portfolio_ids:
            return JsonResponse({'error': 'No portfolios selected'}, status=400)
        
        try:
            # Convert to integers
            portfolio_ids = [int(pid) for pid in portfolio_ids]
            
            # Run batch analysis
            results = orchestrator.batch_analyze_portfolios(
                request.user,
                portfolio_ids
            )
            
            # Format results
            summary = {
                'total': len(results),
                'successful': len([r for r in results if r['status'] == 'success']),
                'failed': len([r for r in results if r['status'] == 'error']),
                'results': results
            }
            
            return JsonResponse(summary)
            
        except Exception as e:
            logger.error(f"Batch analysis error: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    
    # GET - show batch analysis form
    portfolios = UserPortfolio.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('name')
    
    return render(request, 'analytics/batch_analysis.html', {
        'portfolios': portfolios
    })


@login_required
def analysis_history(request):
    """View analysis history."""
    orchestrator = get_orchestrator()
    
    try:
        # Get portfolio filter
        portfolio_id = request.GET.get('portfolio_id')
        
        # Get analysis history
        history = orchestrator.analysis_service.get_analysis_history(
            request.user,
            portfolio_id=int(portfolio_id) if portfolio_id else None,
            limit=50
        )
        
        # Get user portfolios for filter
        portfolios = UserPortfolio.objects.filter(
            user=request.user,
            is_active=True
        ).order_by('name')
        
        context = {
            'history': history,
            'portfolios': portfolios,
            'selected_portfolio': portfolio_id
        }
        
        return render(request, 'analytics/history.html', context)
        
    except Exception as e:
        logger.error(f"Analysis history error: {e}")
        messages.error(request, "Unable to load analysis history.")
        return render(request, 'analytics/history.html', {})


@login_required
def compare_portfolios(request):
    """Compare multiple portfolios."""
    orchestrator = get_orchestrator()
    
    if request.method == 'POST':
        portfolio_ids = request.POST.getlist('portfolio_ids[]')
        
        if len(portfolio_ids) < 2:
            messages.error(request, "Please select at least 2 portfolios to compare.")
            return redirect('analytics_dashboard')
        
        try:
            # Get portfolio analyses
            comparisons = []
            
            for pid in portfolio_ids:
                portfolio = UserPortfolio.objects.get(
                    id=int(pid),
                    user=request.user
                )
                
                analysis = orchestrator.analyze_portfolio(
                    request.user,
                    portfolio.id,
                    analysis_period=90
                )
                
                if 'error' not in analysis:
                    comparisons.append({
                        'portfolio': portfolio,
                        'analysis': analysis
                    })
            
            return render(request, 'analytics/portfolio_comparison.html', {
                'comparisons': comparisons
            })
            
        except Exception as e:
            logger.error(f"Portfolio comparison error: {e}")
            messages.error(request, "Unable to compare portfolios.")
            return redirect('analytics_dashboard')
    
    # GET - show selection form
    portfolios = UserPortfolio.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('name')
    
    return render(request, 'analytics/compare_portfolios_form.html', {
        'portfolios': portfolios
    })


@login_required
def sector_analysis(request, sector_code=None):
    """Analyze sector performance."""
    orchestrator = get_orchestrator()
    
    try:
        if sector_code:
            # Analyze specific sector
            analysis = orchestrator.analytics_engine.get_sector_analysis(sector_code)
            
            if 'error' in analysis:
                messages.error(request, analysis['error'])
                return redirect('sector_analysis')
            
            return render(request, 'analytics/sector_detail.html', {
                'analysis': analysis,
                'sector_code': sector_code
            })
        else:
            # Show all sectors
            sectors = orchestrator.sector_service.get_all_sectors()
            sector_performance = orchestrator.get_sector_performance()
            
            return render(request, 'analytics/sectors.html', {
                'sectors': sectors,
                'performance': sector_performance
            })
            
    except Exception as e:
        logger.error(f"Sector analysis error: {e}")
        messages.error(request, "Unable to load sector analysis.")
        return redirect('analytics_dashboard')


# API endpoints for analytics

@login_required
def api_portfolio_metrics(request, portfolio_id):
    """Get portfolio metrics via API."""
    orchestrator = get_orchestrator()
    
    try:
        # Verify ownership
        portfolio = get_object_or_404(
            UserPortfolio,
            id=portfolio_id,
            user=request.user
        )
        
        # Get metrics
        analysis = orchestrator.analyze_portfolio(
            request.user,
            portfolio_id,
            analysis_period=30
        )
        
        if 'error' in analysis:
            return JsonResponse({'error': analysis['error']}, status=400)
        
        # Extract key metrics
        metrics = {
            'portfolio_id': portfolio_id,
            'total_value': analysis['summary']['total_value'],
            'total_return': analysis['summary']['total_return_pct'],
            'volatility': analysis['risk_metrics'].get('portfolio_volatility'),
            'holdings_count': analysis['summary']['number_of_holdings'],
            'timestamp': timezone.now().isoformat()
        }
        
        return JsonResponse(metrics)
        
    except Exception as e:
        logger.error(f"API metrics error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_technical_indicators(request, symbol):
    """Get technical indicators via API."""
    orchestrator = get_orchestrator()
    
    try:
        # Get parameters
        days = int(request.GET.get('days', 30))
        indicators = request.GET.getlist('indicators[]')
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get technical analysis
        technical = orchestrator.technical_service.analyze(
            symbol,
            start_date,
            end_date
        )
        
        if 'error' in technical:
            return JsonResponse({'error': technical['error']}, status=400)
        
        # Filter indicators if specified
        if indicators:
            filtered = {
                'symbol': symbol,
                'start_date': technical['start_date'],
                'end_date': technical['end_date'],
                'data_points': technical['data_points']
            }
            
            for indicator in indicators:
                if indicator in technical:
                    filtered[indicator] = technical[indicator]
            
            technical = filtered
        
        return JsonResponse(technical)
        
    except Exception as e:
        logger.error(f"API technical indicators error: {e}")
        return JsonResponse({'error': str(e)}, status=500)