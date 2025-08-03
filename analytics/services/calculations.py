"""
Financial calculations service using data services.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
import numpy as np

from django.db import transaction
from django.utils import timezone

from data.services import StockService, PriceService, SectorService
from data.models import Stock, Sector
from analytics.models import AnalysisResult
from users.models import UserPortfolio, PortfolioStock
from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class FinancialCalculations(BaseAnalyzer):
    """
    Service for financial calculations and portfolio analysis.
    """
    
    def __init__(
        self,
        stock_service: Optional[StockService] = None,
        price_service: Optional[PriceService] = None,
        sector_service: Optional[SectorService] = None
    ):
        super().__init__()
        self.stock_service = stock_service or StockService()
        self.price_service = price_service or PriceService()
        self.sector_service = sector_service or SectorService()
    
    def analyze(self, portfolio_id: int, start_date: date, end_date: date) -> Dict[str, any]:
        """
        Perform comprehensive portfolio analysis.
        
        Args:
            portfolio_id: ID of the portfolio to analyze
            start_date: Analysis start date
            end_date: Analysis end date
            
        Returns:
            Dictionary with analysis results
        """
        try:
            portfolio = UserPortfolio.objects.get(id=portfolio_id)
        except UserPortfolio.DoesNotExist:
            logger.error(f"Portfolio {portfolio_id} not found")
            return {'error': 'Portfolio not found'}
        
        # Get portfolio holdings
        holdings = PortfolioStock.objects.filter(
            portfolio=portfolio,
            is_active=True
        ).select_related('stock')
        
        if not holdings:
            return {'error': 'No active holdings in portfolio'}
        
        # Analyze each holding
        holding_analyses = []
        total_value = Decimal('0')
        total_cost = Decimal('0')
        
        for holding in holdings:
            analysis = self._analyze_holding(holding, start_date, end_date)
            if analysis:
                holding_analyses.append(analysis)
                total_value += analysis['current_value']
                total_cost += analysis['total_cost']
        
        # Calculate portfolio-level metrics
        portfolio_analysis = {
            'portfolio_id': portfolio_id,
            'portfolio_name': portfolio.name,
            'analysis_date': timezone.now().isoformat(),
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'holdings': holding_analyses,
            'summary': self._calculate_portfolio_summary(
                holding_analyses,
                total_value,
                total_cost
            ),
            'risk_metrics': self._calculate_portfolio_risk(holding_analyses),
            'sector_allocation': self._calculate_sector_allocation(holding_analyses),
            'recommendations': self._generate_recommendations(holding_analyses)
        }
        
        # Save analysis result
        self._save_analysis_result(portfolio, portfolio_analysis)
        
        return portfolio_analysis
    
    def _analyze_holding(
        self,
        holding: PortfolioStock,
        start_date: date,
        end_date: date
    ) -> Optional[Dict[str, any]]:
        """Analyze individual holding."""
        try:
            stock = holding.stock
            
            # Get current price
            latest_price_data = self.price_service.get_latest_price(stock)
            if not latest_price_data:
                logger.warning(f"No price data for {stock.symbol}")
                return None
            
            current_price = latest_price_data.close_price
            
            # Calculate basic metrics
            current_value = current_price * holding.quantity
            total_cost = holding.purchase_price * holding.quantity
            gain_loss = current_value - total_cost
            gain_loss_pct = (gain_loss / total_cost * 100) if total_cost > 0 else Decimal('0')
            
            # Get price history for period
            price_history = self.price_service.get_price_history(
                stock,
                start_date,
                end_date
            )
            
            # Calculate volatility
            volatility = None
            if len(price_history) >= 20:
                returns = self.price_service.calculate_returns(price_history)
                if returns:
                    daily_returns = [r[1] for r in returns]
                    volatility = float(np.std(daily_returns) * np.sqrt(252) * 100)
            
            return {
                'symbol': stock.symbol,
                'name': stock.name,
                'sector': stock.sector.name if stock.sector else 'Unknown',
                'quantity': float(holding.quantity),
                'purchase_price': float(holding.purchase_price),
                'current_price': float(current_price),
                'current_value': float(current_value),
                'total_cost': float(total_cost),
                'gain_loss': float(gain_loss),
                'gain_loss_pct': float(gain_loss_pct),
                'weight': 0.0,  # Will be calculated at portfolio level
                'volatility': volatility,
                'purchase_date': holding.purchase_date.isoformat(),
                'days_held': (timezone.now().date() - holding.purchase_date).days
            }
            
        except Exception as e:
            logger.error(f"Error analyzing holding {holding.stock.symbol}: {e}")
            return None
    
    def _calculate_portfolio_summary(
        self,
        holdings: List[Dict],
        total_value: Decimal,
        total_cost: Decimal
    ) -> Dict[str, any]:
        """Calculate portfolio summary metrics."""
        if not holdings or total_value == 0:
            return {}
        
        # Update weights
        for holding in holdings:
            holding['weight'] = holding['current_value'] / float(total_value) * 100
        
        # Calculate overall metrics
        total_gain_loss = total_value - total_cost
        total_return_pct = (total_gain_loss / total_cost * 100) if total_cost > 0 else Decimal('0')
        
        return {
            'total_value': float(total_value),
            'total_cost': float(total_cost),
            'total_gain_loss': float(total_gain_loss),
            'total_return_pct': float(total_return_pct),
            'number_of_holdings': len(holdings),
            'best_performer': max(holdings, key=lambda x: x['gain_loss_pct']),
            'worst_performer': min(holdings, key=lambda x: x['gain_loss_pct']),
            'largest_position': max(holdings, key=lambda x: x['weight'])
        }
    
    def _calculate_portfolio_risk(self, holdings: List[Dict]) -> Dict[str, float]:
        """Calculate portfolio risk metrics."""
        if not holdings:
            return {}
        
        # Get volatilities
        volatilities = [h['volatility'] for h in holdings if h.get('volatility')]
        weights = [h['weight'] / 100 for h in holdings if h.get('volatility')]
        
        if not volatilities:
            return {'portfolio_volatility': None}
        
        # Simple weighted average volatility (ignoring correlations)
        portfolio_volatility = sum(
            w * v for w, v in zip(weights, volatilities)
        )
        
        # Concentration risk (Herfindahl index)
        concentration = sum(w ** 2 for w in weights) * 100
        
        return {
            'portfolio_volatility': portfolio_volatility,
            'concentration_index': concentration,
            'max_position_weight': max(h['weight'] for h in holdings),
            'risk_level': self._categorize_risk(portfolio_volatility)
        }
    
    def _calculate_sector_allocation(self, holdings: List[Dict]) -> List[Dict]:
        """Calculate sector allocation."""
        sector_weights = {}
        
        for holding in holdings:
            sector = holding.get('sector', 'Unknown')
            if sector not in sector_weights:
                sector_weights[sector] = 0
            sector_weights[sector] += holding['weight']
        
        return [
            {'sector': sector, 'weight': weight}
            for sector, weight in sorted(
                sector_weights.items(),
                key=lambda x: x[1],
                reverse=True
            )
        ]
    
    def _generate_recommendations(self, holdings: List[Dict]) -> List[str]:
        """Generate portfolio recommendations."""
        recommendations = []
        
        # Check concentration
        max_weight = max(h['weight'] for h in holdings)
        if max_weight > 25:
            recommendations.append(
                f"High concentration risk: largest position is {max_weight:.1f}% of portfolio"
            )
        
        # Check diversification
        if len(holdings) < 5:
            recommendations.append(
                "Low diversification: consider adding more holdings"
            )
        
        # Check volatility
        volatilities = [h['volatility'] for h in holdings if h.get('volatility')]
        if volatilities:
            avg_volatility = sum(volatilities) / len(volatilities)
            if avg_volatility > 40:
                recommendations.append(
                    f"High portfolio volatility ({avg_volatility:.1f}%): consider adding defensive assets"
                )
        
        # Check performance
        poor_performers = [
            h for h in holdings 
            if h['gain_loss_pct'] < -20
        ]
        if poor_performers:
            recommendations.append(
                f"{len(poor_performers)} holdings down >20%: review and consider rebalancing"
            )
        
        return recommendations
    
    def _categorize_risk(self, volatility: float) -> str:
        """Categorize risk level based on volatility."""
        if volatility is None:
            return 'unknown'
        elif volatility < 15:
            return 'low'
        elif volatility < 25:
            return 'moderate'
        elif volatility < 35:
            return 'high'
        else:
            return 'very_high'
    
    def _save_analysis_result(
        self,
        portfolio: UserPortfolio,
        analysis: Dict
    ) -> None:
        """Save analysis result to database."""
        try:
            with transaction.atomic():
                result = AnalysisResult.objects.create(
                    portfolio=portfolio,
                    analysis_type='comprehensive',
                    parameters={
                        'start_date': analysis['start_date'],
                        'end_date': analysis['end_date']
                    },
                    results=analysis,
                    metrics={
                        'total_value': analysis['summary']['total_value'],
                        'total_return_pct': analysis['summary']['total_return_pct'],
                        'volatility': analysis['risk_metrics'].get('portfolio_volatility'),
                        'num_holdings': analysis['summary']['number_of_holdings']
                    }
                )
                
                logger.info(f"Saved analysis result {result.id} for portfolio {portfolio.id}")
                
        except Exception as e:
            logger.error(f"Failed to save analysis result: {e}")
    
    def calculate_portfolio_value(self, portfolio_id: int) -> Decimal:
        """Calculate current portfolio value."""
        try:
            holdings = PortfolioStock.objects.filter(
                portfolio_id=portfolio_id,
                is_active=True
            ).select_related('stock')
            
            total_value = Decimal('0')
            
            for holding in holdings:
                latest_price = self.price_service.get_latest_price(holding.stock)
                if latest_price:
                    total_value += latest_price.close_price * holding.quantity
            
            return total_value
            
        except Exception as e:
            logger.error(f"Error calculating portfolio value: {e}")
            return Decimal('0')
    
    def calculate_stock_allocation(self, portfolio_id: int) -> List[Dict]:
        """Calculate stock allocation in portfolio."""
        try:
            holdings = PortfolioStock.objects.filter(
                portfolio_id=portfolio_id,
                is_active=True
            ).select_related('stock')
            
            allocations = []
            total_value = self.calculate_portfolio_value(portfolio_id)
            
            if total_value > 0:
                for holding in holdings:
                    latest_price = self.price_service.get_latest_price(holding.stock)
                    if latest_price:
                        value = latest_price.close_price * holding.quantity
                        allocations.append({
                            'symbol': holding.stock.symbol,
                            'name': holding.stock.name,
                            'value': float(value),
                            'weight': float(value / total_value * 100),
                            'quantity': float(holding.quantity)
                        })
            
            return sorted(allocations, key=lambda x: x['weight'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error calculating stock allocation: {e}")
            return []