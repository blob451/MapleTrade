"""
High-level analysis service that orchestrates all analytics operations.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from analytics.models import AnalysisResult
from users.models import User, UserPortfolio
from .engine import AnalyticsEngine

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    High-level service for managing analysis operations.
    """
    
    def __init__(self):
        self.engine = AnalyticsEngine()
        self.cache_timeout = 3600  # 1 hour
    
    def create_portfolio_report(
        self,
        user: User,
        portfolio_id: int,
        report_type: str = 'comprehensive'
    ) -> Dict[str, Any]:
        """
        Create a detailed portfolio report.
        
        Args:
            user: User requesting the report
            portfolio_id: Portfolio to analyze
            report_type: Type of report to generate
            
        Returns:
            Complete portfolio report
        """
        try:
            # Verify portfolio ownership
            portfolio = UserPortfolio.objects.get(
                id=portfolio_id,
                user=user,
                is_active=True
            )
        except UserPortfolio.DoesNotExist:
            logger.error(f"Portfolio {portfolio_id} not found for user {user.id}")
            return {'error': 'Portfolio not found or access denied'}
        
        # Generate report based on type
        if report_type == 'comprehensive':
            report = self._generate_comprehensive_report(portfolio)
        elif report_type == 'performance':
            report = self._generate_performance_report(portfolio)
        elif report_type == 'risk':
            report = self._generate_risk_report(portfolio)
        else:
            return {'error': f'Unknown report type: {report_type}'}
        
        # Add metadata
        report['metadata'] = {
            'report_type': report_type,
            'generated_at': timezone.now().isoformat(),
            'user_id': user.id,
            'portfolio_id': portfolio_id,
            'portfolio_name': portfolio.name
        }
        
        # Update user's analysis count
        user.total_analyses_count += 1
        user.last_analysis_date = timezone.now()
        user.save()
        
        return report
    
    def _generate_comprehensive_report(self, portfolio: UserPortfolio) -> Dict[str, Any]:
        """Generate comprehensive portfolio report."""
        # Perform full analysis
        analysis = self.engine.analyze_portfolio(
            portfolio.id,
            analysis_period=90,  # 3 months
            include_technical=True
        )
        
        if 'error' in analysis:
            return analysis
        
        # Add additional sections
        report = {
            'analysis': analysis,
            'performance_summary': self._summarize_performance(analysis),
            'risk_assessment': self._assess_risk(analysis),
            'recommendations': self._generate_recommendations(analysis),
            'action_items': self._generate_action_items(analysis)
        }
        
        return report
    
    def _generate_performance_report(self, portfolio: UserPortfolio) -> Dict[str, Any]:
        """Generate performance-focused report."""
        # Get different time periods
        periods = [30, 90, 180, 365]  # 1 month, 3 months, 6 months, 1 year
        performance_data = {}
        
        for period in periods:
            if period <= 365:  # Don't analyze beyond 1 year
                analysis = self.engine.analyze_portfolio(
                    portfolio.id,
                    analysis_period=period,
                    include_technical=False
                )
                
                if 'error' not in analysis and 'summary' in analysis:
                    performance_data[f'{period}d'] = {
                        'return': analysis['summary'].get('total_return_pct'),
                        'value': analysis['summary'].get('total_value'),
                        'gain_loss': analysis['summary'].get('total_gain_loss')
                    }
        
        return {
            'performance_periods': performance_data,
            'best_performers': self._get_best_performers(portfolio),
            'worst_performers': self._get_worst_performers(portfolio),
            'benchmark_comparison': self._compare_to_benchmark(portfolio)
        }
    
    def _generate_risk_report(self, portfolio: UserPortfolio) -> Dict[str, Any]:
        """Generate risk-focused report."""
        analysis = self.engine.analyze_portfolio(
            portfolio.id,
            analysis_period=90,
            include_technical=True
        )
        
        if 'error' in analysis:
            return analysis
        
        risk_report = {
            'overall_risk': analysis.get('risk_metrics', {}),
            'concentration_analysis': self._analyze_concentration(analysis),
            'volatility_analysis': self._analyze_volatility(analysis),
            'correlation_analysis': self._analyze_correlations(analysis),
            'stress_test': self._perform_stress_test(analysis)
        }
        
        return risk_report
    
    def _summarize_performance(self, analysis: Dict) -> Dict[str, Any]:
        """Summarize portfolio performance."""
        summary = analysis.get('summary', {})
        
        return {
            'total_return': summary.get('total_return_pct'),
            'absolute_gain': summary.get('total_gain_loss'),
            'current_value': summary.get('total_value'),
            'invested_amount': summary.get('total_cost'),
            'performance_rating': self._rate_performance(summary.get('total_return_pct'))
        }
    
    def _assess_risk(self, analysis: Dict) -> Dict[str, Any]:
        """Assess portfolio risk."""
        risk_metrics = analysis.get('risk_metrics', {})
        
        assessment = {
            'risk_level': risk_metrics.get('risk_level', 'unknown'),
            'volatility': risk_metrics.get('portfolio_volatility'),
            'concentration_risk': 'high' if risk_metrics.get('concentration_index', 0) > 30 else 'moderate',
            'risk_score': self._calculate_risk_score(risk_metrics)
        }
        
        # Add risk warnings
        warnings = []
        
        if risk_metrics.get('max_position_weight', 0) > 30:
            warnings.append('Single position exceeds 30% of portfolio')
        
        if risk_metrics.get('portfolio_volatility', 0) > 40:
            warnings.append('High portfolio volatility detected')
        
        if len(analysis.get('holdings', [])) < 5:
            warnings.append('Low diversification - consider adding more positions')
        
        assessment['warnings'] = warnings
        
        return assessment
    
    def _generate_recommendations(self, analysis: Dict) -> List[Dict[str, str]]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Based on the analysis recommendations
        for rec in analysis.get('recommendations', []):
            recommendations.append({
                'type': 'portfolio_optimization',
                'priority': 'high',
                'recommendation': rec
            })
        
        # Add specific recommendations based on holdings
        holdings = analysis.get('holdings', [])
        
        # Check for rebalancing needs
        for holding in holdings:
            if holding.get('weight', 0) > 25:
                recommendations.append({
                    'type': 'rebalancing',
                    'priority': 'medium',
                    'recommendation': f"Consider reducing {holding['symbol']} position (currently {holding['weight']:.1f}% of portfolio)"
                })
            
            # Check technical indicators
            if holding.get('technical', {}).get('rsi', 0) > 70:
                recommendations.append({
                    'type': 'technical',
                    'priority': 'low',
                    'recommendation': f"{holding['symbol']} is overbought (RSI: {holding['technical']['rsi']:.1f})"
                })
        
        return recommendations[:10]  # Limit to top 10 recommendations
    
    def _generate_action_items(self, analysis: Dict) -> List[Dict[str, Any]]:
        """Generate specific action items."""
        action_items = []
        
        risk_metrics = analysis.get('risk_metrics', {})
        holdings = analysis.get('holdings', [])
        
        # High priority actions
        if risk_metrics.get('concentration_index', 0) > 40:
            action_items.append({
                'action': 'Diversify portfolio',
                'priority': 'high',
                'deadline': (timezone.now() + timedelta(days=7)).date().isoformat(),
                'details': 'Portfolio is highly concentrated. Add 3-5 new positions.'
            })
        
        # Medium priority actions
        poor_performers = [h for h in holdings if h.get('gain_loss_pct', 0) < -20]
        if poor_performers:
            action_items.append({
                'action': 'Review underperforming positions',
                'priority': 'medium',
                'deadline': (timezone.now() + timedelta(days=14)).date().isoformat(),
                'details': f"Review {len(poor_performers)} positions down >20%"
            })
        
        return action_items
    
    def _get_best_performers(self, portfolio: UserPortfolio) -> List[Dict]:
        """Get best performing holdings."""
        analysis = self.engine.analyze_portfolio(portfolio.id, analysis_period=30)
        
        if 'error' in analysis or 'holdings' not in analysis:
            return []
        
        holdings = sorted(
            analysis['holdings'],
            key=lambda x: x.get('gain_loss_pct', 0),
            reverse=True
        )[:3]
        
        return [
            {
                'symbol': h['symbol'],
                'name': h['name'],
                'return': h['gain_loss_pct'],
                'gain': h['gain_loss']
            }
            for h in holdings
        ]
    
    def _get_worst_performers(self, portfolio: UserPortfolio) -> List[Dict]:
        """Get worst performing holdings."""
        analysis = self.engine.analyze_portfolio(portfolio.id, analysis_period=30)
        
        if 'error' in analysis or 'holdings' not in analysis:
            return []
        
        holdings = sorted(
            analysis['holdings'],
            key=lambda x: x.get('gain_loss_pct', 0)
        )[:3]
        
        return [
            {
                'symbol': h['symbol'],
                'name': h['name'],
                'return': h['gain_loss_pct'],
                'loss': h['gain_loss']
            }
            for h in holdings
        ]
    
    def _compare_to_benchmark(self, portfolio: UserPortfolio) -> Dict[str, Any]:
        """Compare portfolio performance to benchmark."""
        # Use SPY as default benchmark
        benchmark_analysis = self.engine.analyze_stock('SPY', analysis_period=90)
        
        if 'error' in benchmark_analysis:
            return {'error': 'Could not fetch benchmark data'}
        
        portfolio_analysis = self.engine.analyze_portfolio(
            portfolio.id,
            analysis_period=90
        )
        
        if 'error' in portfolio_analysis:
            return {'error': 'Could not analyze portfolio'}
        
        benchmark_return = benchmark_analysis.get('technical', {}).get('returns', {}).get('total_return', 0)
        portfolio_return = portfolio_analysis.get('summary', {}).get('total_return_pct', 0)
        
        return {
            'benchmark': 'S&P 500 (SPY)',
            'benchmark_return': benchmark_return,
            'portfolio_return': portfolio_return,
            'excess_return': portfolio_return - benchmark_return,
            'outperformed': portfolio_return > benchmark_return
        }
    
    def _analyze_concentration(self, analysis: Dict) -> Dict[str, Any]:
        """Analyze portfolio concentration."""
        holdings = analysis.get('holdings', [])
        
        if not holdings:
            return {}
        
        # Sort by weight
        sorted_holdings = sorted(
            holdings,
            key=lambda x: x.get('weight', 0),
            reverse=True
        )
        
        # Calculate concentration metrics
        top1_weight = sorted_holdings[0]['weight'] if sorted_holdings else 0
        top3_weight = sum(h['weight'] for h in sorted_holdings[:3])
        top5_weight = sum(h['weight'] for h in sorted_holdings[:5])
        
        return {
            'top_holding': {
                'symbol': sorted_holdings[0]['symbol'] if sorted_holdings else None,
                'weight': top1_weight
            },
            'top3_concentration': top3_weight,
            'top5_concentration': top5_weight,
            'concentration_risk': 'high' if top1_weight > 30 or top3_weight > 60 else 'moderate'
        }
    
    def _analyze_volatility(self, analysis: Dict) -> Dict[str, Any]:
        """Analyze portfolio volatility."""
        holdings = analysis.get('holdings', [])
        risk_metrics = analysis.get('risk_metrics', {})
        
        volatilities = [
            h['volatility'] for h in holdings 
            if h.get('volatility') is not None
        ]
        
        if not volatilities:
            return {}
        
        return {
            'portfolio_volatility': risk_metrics.get('portfolio_volatility'),
            'avg_holding_volatility': sum(volatilities) / len(volatilities),
            'max_volatility': max(volatilities),
            'min_volatility': min(volatilities),
            'high_volatility_holdings': [
                {
                    'symbol': h['symbol'],
                    'volatility': h['volatility']
                }
                for h in holdings
                if h.get('volatility', 0) > 40
            ]
        }
    
    def _analyze_correlations(self, analysis: Dict) -> Dict[str, Any]:
        """Analyze correlations between holdings."""
        # Simplified correlation analysis
        sector_allocation = analysis.get('sector_allocation', [])
        
        # Check sector concentration
        sector_concentration = {}
        if sector_allocation:
            max_sector_weight = max(s['weight'] for s in sector_allocation)
            sector_concentration = {
                'most_concentrated_sector': sector_allocation[0]['sector'],
                'concentration': sector_allocation[0]['weight'],
                'risk': 'high' if max_sector_weight > 40 else 'moderate'
            }
        
        return {
            'sector_concentration': sector_concentration,
            'diversification_score': self._calculate_diversification_score(analysis)
        }
    
    def _perform_stress_test(self, analysis: Dict) -> Dict[str, Any]:
        """Perform simple stress test on portfolio."""
        current_value = analysis.get('summary', {}).get('total_value', 0)
        
        if not current_value:
            return {}
        
        # Simple stress scenarios
        scenarios = {
            'market_correction': -10,  # 10% market drop
            'bear_market': -20,  # 20% market drop
            'financial_crisis': -30  # 30% market drop
        }
        
        stress_results = {}
        
        for scenario, drop in scenarios.items():
            new_value = current_value * (1 + drop / 100)
            loss = current_value - new_value
            
            stress_results[scenario] = {
                'percentage_drop': drop,
                'new_value': float(new_value),
                'loss_amount': float(loss)
            }
        
        return stress_results
    
    def _rate_performance(self, return_pct: Optional[float]) -> str:
        """Rate portfolio performance."""
        if return_pct is None:
            return 'unknown'
        elif return_pct > 20:
            return 'excellent'
        elif return_pct > 10:
            return 'good'
        elif return_pct > 0:
            return 'satisfactory'
        elif return_pct > -10:
            return 'poor'
        else:
            return 'very_poor'
    
    def _calculate_risk_score(self, risk_metrics: Dict) -> float:
        """Calculate overall risk score (0-100)."""
        score = 50  # Base score
        
        # Adjust for volatility
        volatility = risk_metrics.get('portfolio_volatility', 0)
        if volatility > 40:
            score += 20
        elif volatility > 25:
            score += 10
        elif volatility < 15:
            score -= 10
        
        # Adjust for concentration
        concentration = risk_metrics.get('concentration_index', 0)
        if concentration > 30:
            score += 15
        elif concentration > 20:
            score += 5
        
        # Adjust for max position
        max_position = risk_metrics.get('max_position_weight', 0)
        if max_position > 40:
            score += 15
        elif max_position > 30:
            score += 10
        
        return max(0, min(100, score))
    
    def _calculate_diversification_score(self, analysis: Dict) -> float:
        """Calculate diversification score (0-100)."""
        score = 0
        
        holdings = analysis.get('holdings', [])
        sectors = analysis.get('sector_allocation', [])
        
        # Number of holdings
        num_holdings = len(holdings)
        if num_holdings >= 20:
            score += 30
        elif num_holdings >= 10:
            score += 20
        elif num_holdings >= 5:
            score += 10
        
        # Number of sectors
        num_sectors = len(sectors)
        if num_sectors >= 8:
            score += 30
        elif num_sectors >= 5:
            score += 20
        elif num_sectors >= 3:
            score += 10
        
        # Weight distribution
        if holdings:
            weights = [h['weight'] for h in holdings]
            max_weight = max(weights)
            
            if max_weight < 15:
                score += 20
            elif max_weight < 25:
                score += 10
        
        # Sector distribution
        if sectors:
            sector_weights = [s['weight'] for s in sectors]
            max_sector_weight = max(sector_weights)
            
            if max_sector_weight < 30:
                score += 20
            elif max_sector_weight < 40:
                score += 10
        
        return min(100, score)
    
    def get_analysis_history(
        self,
        user: User,
        portfolio_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get user's analysis history."""
        query = AnalysisResult.objects.filter(
            portfolio__user=user
        )
        
        if portfolio_id:
            query = query.filter(portfolio_id=portfolio_id)
        
        results = query.order_by('-created_at')[:limit]
        
        return [
            {
                'id': result.id,
                'portfolio': result.portfolio.name if result.portfolio else 'N/A',
                'type': result.analysis_type,
                'created': result.created_at.isoformat(),
                'metrics': result.metrics
            }
            for result in results
        ]