"""
User views using the orchestrator.
"""

import logging
from datetime import datetime
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction

from core.services import get_orchestrator, OrchestratorError
from users.models import User, UserPortfolio, PortfolioStock
from users.forms import (
    UserRegistrationForm, 
    UserProfileForm, 
    PortfolioForm,
    PortfolioStockForm
)

logger = logging.getLogger(__name__)


def register(request):
    """User registration view."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            
            # Log the user in
            user = authenticate(username=username, password=password)
            login(request, user)
            
            messages.success(request, 'Registration successful! Welcome to MapleTrade.')
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'users/register.html', {'form': form})


@login_required
def profile(request):
    """User profile view."""
    orchestrator = get_orchestrator()
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    # Get user statistics
    portfolios = UserPortfolio.objects.filter(
        user=request.user,
        is_active=True
    )
    
    total_value = Decimal('0')
    for portfolio in portfolios:
        try:
            value = orchestrator.calculations_service.calculate_portfolio_value(portfolio.id)
            total_value += value
        except:
            pass
    
    context = {
        'form': form,
        'portfolio_count': portfolios.count(),
        'total_value': total_value,
        'analysis_count': request.user.total_analyses_count,
        'last_analysis': request.user.last_analysis_date,
        'member_since': request.user.date_joined
    }
    
    return render(request, 'users/profile.html', context)


@login_required
def portfolio_list(request):
    """List user's portfolios."""
    orchestrator = get_orchestrator()
    
    portfolios = UserPortfolio.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('-created_at')
    
    # Add value and performance to each portfolio
    portfolio_data = []
    
    for portfolio in portfolios:
        try:
            summary = orchestrator.get_portfolio_summary(portfolio.id)
            portfolio_data.append({
                'portfolio': portfolio,
                'summary': summary
            })
        except Exception as e:
            logger.error(f"Error getting portfolio {portfolio.id} summary: {e}")
            portfolio_data.append({
                'portfolio': portfolio,
                'summary': None
            })
    
    return render(request, 'users/portfolio_list.html', {
        'portfolio_data': portfolio_data
    })


@login_required
@require_http_methods(["GET", "POST"])
def portfolio_create(request):
    """Create new portfolio."""
    orchestrator = get_orchestrator()
    
    if request.method == 'POST':
        form = PortfolioForm(request.POST)
        if form.is_valid():
            try:
                portfolio = orchestrator.create_portfolio(
                    request.user,
                    form.cleaned_data['name'],
                    form.cleaned_data.get('description', '')
                )
                
                messages.success(request, f'Portfolio "{portfolio.name}" created successfully!')
                return redirect('portfolio_detail', portfolio_id=portfolio.id)
                
            except OrchestratorError as e:
                messages.error(request, str(e))
    else:
        form = PortfolioForm()
    
    return render(request, 'users/portfolio_form.html', {
        'form': form,
        'action': 'Create'
    })


@login_required
def portfolio_detail(request, portfolio_id):
    """Portfolio detail view."""
    orchestrator = get_orchestrator()
    
    portfolio = get_object_or_404(
        UserPortfolio,
        id=portfolio_id,
        user=request.user,
        is_active=True
    )
    
    try:
        # Get portfolio summary
        summary = orchestrator.get_portfolio_summary(portfolio_id)
        
        # Get holdings with current values
        holdings = PortfolioStock.objects.filter(
            portfolio=portfolio,
            is_active=True
        ).select_related('stock')
        
        # Calculate individual holding performance
        holding_data = []
        for holding in holdings:
            try:
                stock_info = orchestrator.get_stock_info(holding.stock.symbol)
                current_price = Decimal(str(stock_info['current_price']))
                current_value = current_price * holding.shares
                gain_loss = current_value - (holding.purchase_price * holding.shares)
                gain_loss_pct = (gain_loss / (holding.purchase_price * holding.shares) * 100)
                
                holding_data.append({
                    'holding': holding,
                    'current_price': current_price,
                    'current_value': current_value,
                    'gain_loss': gain_loss,
                    'gain_loss_pct': gain_loss_pct,
                    'stock_info': stock_info
                })
            except Exception as e:
                logger.error(f"Error processing holding {holding.id}: {e}")
                holding_data.append({
                    'holding': holding,
                    'error': True
                })
        
        context = {
            'portfolio': portfolio,
            'summary': summary,
            'holding_data': holding_data,
            'can_analyze': len(holdings) > 0
        }
        
        return render(request, 'users/portfolio_detail.html', context)
        
    except Exception as e:
        logger.error(f"Portfolio detail error: {e}")
        messages.error(request, "Error loading portfolio details.")
        return render(request, 'users/portfolio_detail.html', {
            'portfolio': portfolio,
            'error': True
        })


@login_required
@require_http_methods(["GET", "POST"])
def portfolio_edit(request, portfolio_id):
    """Edit portfolio."""
    portfolio = get_object_or_404(
        UserPortfolio,
        id=portfolio_id,
        user=request.user,
        is_active=True
    )
    
    if request.method == 'POST':
        form = PortfolioForm(request.POST, instance=portfolio)
        if form.is_valid():
            form.save()
            messages.success(request, 'Portfolio updated successfully!')
            return redirect('portfolio_detail', portfolio_id=portfolio.id)
    else:
        form = PortfolioForm(instance=portfolio)
    
    return render(request, 'users/portfolio_form.html', {
        'form': form,
        'portfolio': portfolio,
        'action': 'Edit'
    })


@login_required
@require_http_methods(["POST"])
def portfolio_delete(request, portfolio_id):
    """Delete portfolio (soft delete)."""
    portfolio = get_object_or_404(
        UserPortfolio,
        id=portfolio_id,
        user=request.user,
        is_active=True
    )
    
    # Soft delete
    portfolio.is_active = False
    portfolio.save()
    
    # Also deactivate all holdings
    PortfolioStock.objects.filter(portfolio=portfolio).update(is_active=False)
    
    messages.success(request, f'Portfolio "{portfolio.name}" deleted successfully.')
    return redirect('portfolio_list')

@login_required
@require_http_methods(["GET", "POST"])
def add_holding(request, portfolio_id):
    """Add holding to portfolio."""
    orchestrator = get_orchestrator()
    
    portfolio = get_object_or_404(
        UserPortfolio,
        id=portfolio_id,
        user=request.user,
        is_active=True
    )
    
    if request.method == 'POST':
        form = PortfolioStockForm(request.POST)
        if form.is_valid():
            try:
                # The orchestrator expects 'quantity' but form has 'shares'
                holding = orchestrator.add_stock_to_portfolio(
                    portfolio_id,
                    form.cleaned_data['symbol'],
                    form.cleaned_data['shares'],  # This is 'shares' from form
                    form.cleaned_data['purchase_price'],
                    form.cleaned_data.get('added_date')  # This is 'added_date' from form
                )
                
                messages.success(request, f'Added {holding.stock.symbol} to portfolio!')
                return redirect('portfolio_detail', portfolio_id=portfolio.id)
                
            except OrchestratorError as e:
                messages.error(request, str(e))
    else:
        # Pre-fill symbol if provided
        initial = {}
        if request.GET.get('symbol'):
            initial['symbol'] = request.GET['symbol']
        form = PortfolioStockForm(initial=initial)
    
    return render(request, 'users/add_holding.html', {
        'form': form,
        'portfolio': portfolio
    })

@login_required
@require_http_methods(["GET", "POST"])
def edit_holding(request, portfolio_id, holding_id):
    """Edit portfolio holding."""
    portfolio = get_object_or_404(
        UserPortfolio,
        id=portfolio_id,
        user=request.user,
        is_active=True
    )
    
    holding = get_object_or_404(
        PortfolioStock,
        id=holding_id,
        portfolio=portfolio,
        is_active=True
    )
    
    if request.method == 'POST':
        form = PortfolioStockForm(request.POST, instance=holding)
        if form.is_valid():
            form.save()
            
            # Clear portfolio cache
            orchestrator = get_orchestrator()
            orchestrator.cache_manager.invalidate_portfolio(portfolio_id)
            
            messages.success(request, 'Holding updated successfully!')
            return redirect('portfolio_detail', portfolio_id=portfolio.id)
    else:
        form = PortfolioStockForm(instance=holding, initial={
            'symbol': holding.stock.symbol
        })
    
    return render(request, 'users/edit_holding.html', {
        'form': form,
        'portfolio': portfolio,
        'holding': holding
    })


@login_required
@require_http_methods(["POST"])
def remove_holding(request, portfolio_id, holding_id):
    """Remove holding from portfolio."""
    portfolio = get_object_or_404(
        UserPortfolio,
        id=portfolio_id,
        user=request.user,
        is_active=True
    )
    
    holding = get_object_or_404(
        PortfolioStock,
        id=holding_id,
        portfolio=portfolio,
        is_active=True
    )
    
    # Soft delete
    holding.is_active = False
    holding.save()
    
    # Clear cache
    orchestrator = get_orchestrator()
    orchestrator.cache_manager.invalidate_portfolio(portfolio_id)
    
    messages.success(request, f'Removed {holding.stock.symbol} from portfolio.')
    return redirect('portfolio_detail', portfolio_id=portfolio.id)


@login_required
def watchlist(request):
    """User's stock watchlist."""
    orchestrator = get_orchestrator()
    
    # Get watchlist from user preferences (stored in session for now)
    watchlist = request.session.get('watchlist', [])
    
    if request.method == 'POST':
        action = request.POST.get('action')
        symbol = request.POST.get('symbol', '').upper()
        
        if action == 'add' and symbol:
            if symbol not in watchlist:
                watchlist.append(symbol)
                messages.success(request, f'Added {symbol} to watchlist.')
        elif action == 'remove' and symbol:
            if symbol in watchlist:
                watchlist.remove(symbol)
                messages.success(request, f'Removed {symbol} from watchlist.')
        
        request.session['watchlist'] = watchlist
        return redirect('watchlist')
    
    # Get current data for watchlist stocks
    watchlist_data = []
    for symbol in watchlist:
        try:
            stock_info = orchestrator.get_stock_info(symbol)
            watchlist_data.append(stock_info)
        except:
            pass
    
    return render(request, 'users/watchlist.html', {
        'watchlist_data': watchlist_data
    })


# API endpoints

@login_required
def api_portfolio_performance(request, portfolio_id):
    """Get portfolio performance data."""
    orchestrator = get_orchestrator()
    
    try:
        # Verify ownership
        portfolio = get_object_or_404(
            UserPortfolio,
            id=portfolio_id,
            user=request.user
        )
        
        # Get time period
        days = int(request.GET.get('days', 30))
        
        # Get performance data
        analysis = orchestrator.analyze_portfolio(
            request.user,
            portfolio_id,
            analysis_period=days
        )
        
        if 'error' in analysis:
            return JsonResponse({'error': analysis['error']}, status=400)
        
        # Extract performance data
        performance = {
            'portfolio_id': portfolio_id,
            'period_days': days,
            'total_return': analysis['summary']['total_return_pct'],
            'total_value': analysis['summary']['total_value'],
            'total_gain_loss': analysis['summary']['total_gain_loss'],
            'holdings': []
        }
        
        # Add individual holding performance
        for holding in analysis.get('holdings', []):
            performance['holdings'].append({
                'symbol': holding['symbol'],
                'return_pct': holding['gain_loss_pct'],
                'gain_loss': holding['gain_loss'],
                'weight': holding['weight']
            })
        
        return JsonResponse(performance)
        
    except Exception as e:
        logger.error(f"Portfolio performance API error: {e}")
        return JsonResponse({'error': str(e)}, status=500)