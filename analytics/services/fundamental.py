"""
Fundamental Analysis Module for MapleTrade.

This module implements financial ratio calculations, valuation models,
and fundamental-based investment recommendations.
"""

import logging
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from data.services import StockService, PriceService
from data.models import Stock, PriceData
from analytics.models import AnalysisResult
from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class FundamentalAnalyzer(BaseAnalyzer):
    """
    Service for fundamental analysis including:
    - Financial ratio calculations
    - Valuation models (P/E multiples, P/B, etc.)
    - Integration with existing recommendation logic
    """
    
    # Industry average thresholds for comparison
    RATIO_THRESHOLDS = {
        'pe_ratio': {
            'undervalued': 15.0,
            'fair': 25.0,
            'overvalued': 35.0
        },
        'pb_ratio': {
            'undervalued': 1.0,
            'fair': 3.0,
            'overvalued': 5.0
        },
        'debt_to_equity': {
            'low': 0.5,
            'moderate': 1.0,
            'high': 2.0
        },
        'current_ratio': {
            'poor': 1.0,
            'acceptable': 1.5,
            'strong': 2.0
        },
        'roe': {  # Return on Equity
            'poor': 0.05,
            'average': 0.15,
            'excellent': 0.25
        }
    }
    
    def __init__(self, stock_service: Optional[StockService] = None,
                 price_service: Optional[PriceService] = None):
        """Initialize the FundamentalAnalyzer with required services."""
        super().__init__()
        self.stock_service = stock_service or StockService()
        self.price_service = price_service or PriceService()
        self.cache_timeout = 86400  # 24 hours for fundamental data
    
    def analyze(self, symbol: str, **kwargs) -> Dict[str, Any]:
        """
        Perform comprehensive fundamental analysis on a stock.
        
        Args:
            symbol: Stock ticker symbol
            **kwargs: Additional parameters for analysis
            
        Returns:
            Dict containing fundamental metrics, ratios, and signals
        """
        try:
            # Get stock data
            stock = self.stock_service.get_or_fetch_stock(symbol)
            if not stock:
                raise ValueError(f"Stock {symbol} not found")
            
            # Calculate all fundamental metrics
            ratios = self.calculate_financial_ratios(stock)
            valuation = self.calculate_valuation_metrics(stock)
            financial_health = self.assess_financial_health(stock, ratios)
            growth_metrics = self.calculate_growth_metrics(stock)
            
            # Generate fundamental signals
            signals = self.get_fundamental_signals(ratios, valuation, financial_health)
            
            # Calculate overall fundamental score
            fundamental_score = self._calculate_fundamental_score(
                ratios, valuation, financial_health, growth_metrics
            )
            
            # Generate recommendation based on fundamental analysis
            recommendation = self._generate_fundamental_recommendation(
                fundamental_score, signals
            )
            
            result = {
                'symbol': symbol,
                'timestamp': timezone.now(),
                'ratios': ratios,
                'valuation': valuation,
                'financial_health': financial_health,
                'growth_metrics': growth_metrics,
                'signals': signals,
                'fundamental_score': fundamental_score,
                'recommendation': recommendation,
                'analysis_summary': self._generate_analysis_summary(
                    stock, ratios, valuation, financial_health
                )
            }
            
            # Cache the results
            cache_key = f"fundamental_analysis:{symbol}"
            cache.set(cache_key, result, self.cache_timeout)
            
            return result
            
        except Exception as e:
            logger.error(f"Fundamental analysis failed for {symbol}: {str(e)}")
            raise
    
    def calculate_financial_ratios(self, stock: Stock) -> Dict[str, Optional[float]]:
        """
        Calculate key financial ratios for the stock.
        
        Returns dict with ratios like P/E, P/B, ROE, debt ratios, etc.
        """
        ratios = {}
        
        try:
            # Price-based ratios
            if stock.current_price and stock.current_price > 0:
                # P/E Ratio
                if hasattr(stock, 'earnings_per_share') and stock.earnings_per_share:
                    ratios['pe_ratio'] = float(stock.current_price / stock.earnings_per_share)
                else:
                    # Estimate from market cap and net income if available
                    ratios['pe_ratio'] = self._estimate_pe_ratio(stock)
                
                # P/B Ratio
                if hasattr(stock, 'book_value_per_share') and stock.book_value_per_share:
                    ratios['pb_ratio'] = float(stock.current_price / stock.book_value_per_share)
                else:
                    ratios['pb_ratio'] = None
                
                # Price to Sales
                if hasattr(stock, 'revenue_per_share') and stock.revenue_per_share:
                    ratios['ps_ratio'] = float(stock.current_price / stock.revenue_per_share)
                else:
                    ratios['ps_ratio'] = None
            
            # Profitability ratios
            ratios['roe'] = self._calculate_roe(stock)
            ratios['roa'] = self._calculate_roa(stock)
            ratios['profit_margin'] = self._calculate_profit_margin(stock)
            
            # Liquidity ratios
            ratios['current_ratio'] = self._calculate_current_ratio(stock)
            ratios['quick_ratio'] = self._calculate_quick_ratio(stock)
            
            # Leverage ratios
            ratios['debt_to_equity'] = self._calculate_debt_to_equity(stock)
            ratios['debt_to_assets'] = self._calculate_debt_to_assets(stock)
            
            # Efficiency ratios
            ratios['asset_turnover'] = self._calculate_asset_turnover(stock)
            ratios['inventory_turnover'] = self._calculate_inventory_turnover(stock)
            
        except Exception as e:
            logger.warning(f"Error calculating ratios for {stock.symbol}: {str(e)}")
        
        return ratios
    
    def calculate_valuation_metrics(self, stock: Stock) -> Dict[str, Any]:
        """
        Calculate valuation metrics including intrinsic value estimates.
        """
        valuation = {
            'current_price': float(stock.current_price) if stock.current_price else None,
            'target_price': float(stock.target_price) if stock.target_price else None,
            'market_cap': stock.market_cap,
        }
        
        # Calculate price targets based on different methods
        if stock.current_price:
            # P/E based valuation
            pe_target = self._calculate_pe_based_target(stock)
            if pe_target:
                valuation['pe_based_target'] = pe_target
            
            # P/B based valuation
            pb_target = self._calculate_pb_based_target(stock)
            if pb_target:
                valuation['pb_based_target'] = pb_target
            
            # Analyst consensus
            if stock.target_price:
                valuation['analyst_upside'] = float(
                    (stock.target_price - stock.current_price) / stock.current_price
                )
            
            # Average fair value
            targets = [v for k, v in valuation.items() 
                      if k.endswith('_target') and v is not None]
            if targets:
                valuation['avg_fair_value'] = sum(targets) / len(targets)
                valuation['upside_potential'] = (
                    valuation['avg_fair_value'] - float(stock.current_price)
                ) / float(stock.current_price)
        
        return valuation
    
    def assess_financial_health(self, stock: Stock, ratios: Dict[str, Optional[float]]) -> Dict[str, Any]:
        """
        Assess the overall financial health of the company.
        """
        health_score = 0
        max_score = 0
        assessments = {}
        
        # Profitability assessment
        if ratios.get('roe') is not None:
            max_score += 1
            if ratios['roe'] > self.RATIO_THRESHOLDS['roe']['excellent']:
                health_score += 1
                assessments['profitability'] = 'Excellent'
            elif ratios['roe'] > self.RATIO_THRESHOLDS['roe']['average']:
                health_score += 0.7
                assessments['profitability'] = 'Good'
            elif ratios['roe'] > self.RATIO_THRESHOLDS['roe']['poor']:
                health_score += 0.4
                assessments['profitability'] = 'Average'
            else:
                assessments['profitability'] = 'Poor'
        
        # Liquidity assessment
        if ratios.get('current_ratio') is not None:
            max_score += 1
            if ratios['current_ratio'] > self.RATIO_THRESHOLDS['current_ratio']['strong']:
                health_score += 1
                assessments['liquidity'] = 'Strong'
            elif ratios['current_ratio'] > self.RATIO_THRESHOLDS['current_ratio']['acceptable']:
                health_score += 0.7
                assessments['liquidity'] = 'Acceptable'
            else:
                assessments['liquidity'] = 'Weak'
        
        # Leverage assessment
        if ratios.get('debt_to_equity') is not None:
            max_score += 1
            if ratios['debt_to_equity'] < self.RATIO_THRESHOLDS['debt_to_equity']['low']:
                health_score += 1
                assessments['leverage'] = 'Low (Good)'
            elif ratios['debt_to_equity'] < self.RATIO_THRESHOLDS['debt_to_equity']['moderate']:
                health_score += 0.7
                assessments['leverage'] = 'Moderate'
            else:
                assessments['leverage'] = 'High (Risky)'
        
        # Calculate overall health score
        overall_score = health_score / max_score if max_score > 0 else 0
        
        return {
            'overall_score': overall_score,
            'rating': self._get_health_rating(overall_score),
            'assessments': assessments,
            'strengths': [k for k, v in assessments.items() if v in ['Excellent', 'Strong', 'Low (Good)']],
            'weaknesses': [k for k, v in assessments.items() if v in ['Poor', 'Weak', 'High (Risky)']]
        }
    
    def calculate_growth_metrics(self, stock: Stock) -> Dict[str, Optional[float]]:
        """
        Calculate growth-related metrics.
        """
        growth_metrics = {}
        
        # Revenue growth (would need historical data)
        growth_metrics['revenue_growth'] = self._estimate_revenue_growth(stock)
        
        # Earnings growth
        growth_metrics['earnings_growth'] = self._estimate_earnings_growth(stock)
        
        # PEG ratio (P/E to Growth)
        if hasattr(stock, 'peg_ratio'):
            growth_metrics['peg_ratio'] = float(stock.peg_ratio) if stock.peg_ratio else None
        
        return growth_metrics
    
    def get_fundamental_signals(self, ratios: Dict[str, Optional[float]], 
                               valuation: Dict[str, Any],
                               financial_health: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Generate buy/sell signals based on fundamental analysis.
        """
        signals = {}
        
        # Valuation signal
        if valuation.get('upside_potential'):
            if valuation['upside_potential'] > 0.20:  # 20% upside
                signals['valuation'] = {
                    'signal': 'BUY',
                    'strength': 'Strong' if valuation['upside_potential'] > 0.30 else 'Moderate',
                    'reason': f"{valuation['upside_potential']:.1%} upside potential"
                }
            elif valuation['upside_potential'] < -0.15:  # 15% downside
                signals['valuation'] = {
                    'signal': 'SELL',
                    'strength': 'Strong' if valuation['upside_potential'] < -0.25 else 'Moderate',
                    'reason': f"{abs(valuation['upside_potential']):.1%} downside risk"
                }
            else:
                signals['valuation'] = {
                    'signal': 'HOLD',
                    'strength': 'Neutral',
                    'reason': 'Fair valuation'
                }
        
        # P/E signal
        if ratios.get('pe_ratio'):
            if ratios['pe_ratio'] < self.RATIO_THRESHOLDS['pe_ratio']['undervalued']:
                signals['pe_ratio'] = {
                    'signal': 'BUY',
                    'strength': 'Strong',
                    'reason': f"P/E of {ratios['pe_ratio']:.1f} indicates undervaluation"
                }
            elif ratios['pe_ratio'] > self.RATIO_THRESHOLDS['pe_ratio']['overvalued']:
                signals['pe_ratio'] = {
                    'signal': 'SELL',
                    'strength': 'Moderate',
                    'reason': f"P/E of {ratios['pe_ratio']:.1f} indicates overvaluation"
                }
        
        # Financial health signal
        if financial_health['overall_score'] > 0.8:
            signals['financial_health'] = {
                'signal': 'BUY',
                'strength': 'Moderate',
                'reason': f"Excellent financial health ({financial_health['rating']})"
            }
        elif financial_health['overall_score'] < 0.3:
            signals['financial_health'] = {
                'signal': 'SELL',
                'strength': 'Strong',
                'reason': f"Poor financial health ({financial_health['rating']})"
            }
        
        return signals
    
    def _calculate_fundamental_score(self, ratios: Dict[str, Optional[float]],
                                   valuation: Dict[str, Any],
                                   financial_health: Dict[str, Any],
                                   growth_metrics: Dict[str, Optional[float]]) -> float:
        """
        Calculate an overall fundamental score (0-100).
        """
        score = 0
        weights_sum = 0
        
        # Valuation component (30% weight)
        if valuation.get('upside_potential') is not None:
            # Convert upside to 0-100 scale
            upside_score = min(max((valuation['upside_potential'] + 0.5) * 100, 0), 100)
            score += upside_score * 0.3
            weights_sum += 0.3
        
        # Financial health component (40% weight)
        if financial_health.get('overall_score') is not None:
            score += financial_health['overall_score'] * 100 * 0.4
            weights_sum += 0.4
        
        # P/E component (20% weight)
        if ratios.get('pe_ratio') and ratios['pe_ratio'] > 0:
            # Lower P/E is better (inverse relationship)
            pe_score = max(0, min(100, (50 - ratios['pe_ratio']) * 2))
            score += pe_score * 0.2
            weights_sum += 0.2
        
        # Growth component (10% weight)
        if growth_metrics.get('revenue_growth'):
            growth_score = min(max(growth_metrics['revenue_growth'] * 200, 0), 100)
            score += growth_score * 0.1
            weights_sum += 0.1
        
        # Normalize by actual weights used
        if weights_sum > 0:
            return score / weights_sum
        else:
            return 50  # Default neutral score
    
    def _generate_fundamental_recommendation(self, fundamental_score: float,
                                           signals: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a recommendation based on fundamental analysis.
        """
        # Count buy/sell signals
        buy_signals = sum(1 for s in signals.values() if s['signal'] == 'BUY')
        sell_signals = sum(1 for s in signals.values() if s['signal'] == 'SELL')
        strong_signals = sum(1 for s in signals.values() if s.get('strength') == 'Strong')
        
        # Determine recommendation
        if fundamental_score > 70 and buy_signals > sell_signals:
            recommendation = 'BUY'
            confidence = 'HIGH' if strong_signals >= 2 else 'MEDIUM'
        elif fundamental_score < 30 and sell_signals > buy_signals:
            recommendation = 'SELL'
            confidence = 'HIGH' if strong_signals >= 2 else 'MEDIUM'
        else:
            recommendation = 'HOLD'
            confidence = 'MEDIUM' if abs(buy_signals - sell_signals) <= 1 else 'LOW'
        
        return {
            'recommendation': recommendation,
            'confidence': confidence,
            'score': fundamental_score,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'reasoning': self._generate_recommendation_reasoning(
                recommendation, signals, fundamental_score
            )
        }
    
    def _generate_analysis_summary(self, stock: Stock, ratios: Dict[str, Optional[float]],
                                 valuation: Dict[str, Any],
                                 financial_health: Dict[str, Any]) -> str:
        """
        Generate a human-readable analysis summary.
        """
        summary_parts = []
        
        # Valuation summary
        if valuation.get('upside_potential'):
            if valuation['upside_potential'] > 0:
                summary_parts.append(
                    f"{stock.symbol} appears undervalued with {valuation['upside_potential']:.1%} upside potential"
                )
            else:
                summary_parts.append(
                    f"{stock.symbol} appears overvalued with {abs(valuation['upside_potential']):.1%} downside risk"
                )
        
        # Financial health summary
        if financial_health.get('rating'):
            summary_parts.append(
                f"The company shows {financial_health['rating'].lower()} financial health"
            )
            if financial_health.get('strengths'):
                summary_parts.append(
                    f"with strengths in {', '.join(financial_health['strengths'])}"
                )
        
        # Ratio highlights
        if ratios.get('pe_ratio'):
            summary_parts.append(f"P/E ratio of {ratios['pe_ratio']:.1f}")
        
        if ratios.get('roe'):
            summary_parts.append(f"ROE of {ratios['roe']:.1%}")
        
        return ". ".join(summary_parts) + "."
    
    def _generate_recommendation_reasoning(self, recommendation: str,
                                         signals: Dict[str, Dict[str, Any]],
                                         score: float) -> str:
        """
        Generate reasoning for the recommendation.
        """
        reasons = []
        
        # Add main reasons based on signals
        for signal_name, signal_data in signals.items():
            if signal_data['signal'] == recommendation:
                reasons.append(signal_data['reason'])
        
        # Add score-based reasoning
        if score > 70:
            reasons.append("Strong fundamental score")
        elif score < 30:
            reasons.append("Weak fundamental score")
        
        if not reasons:
            reasons.append(f"Fundamental score of {score:.0f}/100")
        
        return f"{recommendation} recommendation based on: " + "; ".join(reasons[:3])
    
    # Helper methods for ratio calculations
    def _estimate_pe_ratio(self, stock: Stock) -> Optional[float]:
        """Estimate P/E ratio from available data."""
        # This would typically fetch from financial statements
        # For now, return None if not directly available
        return None
    
    def _calculate_roe(self, stock: Stock) -> Optional[float]:
        """Calculate Return on Equity."""
        # ROE = Net Income / Shareholders' Equity
        # Would need financial statement data
        return None
    
    def _calculate_roa(self, stock: Stock) -> Optional[float]:
        """Calculate Return on Assets."""
        # ROA = Net Income / Total Assets
        return None
    
    def _calculate_profit_margin(self, stock: Stock) -> Optional[float]:
        """Calculate Net Profit Margin."""
        # Profit Margin = Net Income / Revenue
        return None
    
    def _calculate_current_ratio(self, stock: Stock) -> Optional[float]:
        """Calculate Current Ratio."""
        # Current Ratio = Current Assets / Current Liabilities
        return None
    
    def _calculate_quick_ratio(self, stock: Stock) -> Optional[float]:
        """Calculate Quick Ratio."""
        # Quick Ratio = (Current Assets - Inventory) / Current Liabilities
        return None
    
    def _calculate_debt_to_equity(self, stock: Stock) -> Optional[float]:
        """Calculate Debt to Equity Ratio."""
        # D/E = Total Debt / Total Equity
        return None
    
    def _calculate_debt_to_assets(self, stock: Stock) -> Optional[float]:
        """Calculate Debt to Assets Ratio."""
        # D/A = Total Debt / Total Assets
        return None
    
    def _calculate_asset_turnover(self, stock: Stock) -> Optional[float]:
        """Calculate Asset Turnover Ratio."""
        # Asset Turnover = Revenue / Average Total Assets
        return None
    
    def _calculate_inventory_turnover(self, stock: Stock) -> Optional[float]:
        """Calculate Inventory Turnover Ratio."""
        # Inventory Turnover = COGS / Average Inventory
        return None
    
    def _calculate_pe_based_target(self, stock: Stock) -> Optional[float]:
        """Calculate target price based on P/E multiple."""
        # Would use sector average P/E or historical P/E
        return None
    
    def _calculate_pb_based_target(self, stock: Stock) -> Optional[float]:
        """Calculate target price based on P/B multiple."""
        # Would use sector average P/B or historical P/B
        return None
    
    def _estimate_revenue_growth(self, stock: Stock) -> Optional[float]:
        """Estimate revenue growth rate."""
        # Would calculate from historical revenue data
        return None
    
    def _estimate_earnings_growth(self, stock: Stock) -> Optional[float]:
        """Estimate earnings growth rate."""
        # Would calculate from historical earnings data
        return None
    
    def _get_health_rating(self, score: float) -> str:
        """Convert health score to rating."""
        if score >= 0.8:
            return "Excellent"
        elif score >= 0.6:
            return "Good"
        elif score >= 0.4:
            return "Fair"
        elif score >= 0.2:
            return "Poor"
        else:
            return "Very Poor"