"""
Tests for the FundamentalAnalyzer service.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from data.models import Stock, Sector
from analytics.services.fundamental import FundamentalAnalyzer


class FundamentalAnalyzerTestCase(TestCase):
    """Test cases for FundamentalAnalyzer."""
    
    def setUp(self):
        """Set up test data."""
        # Create test sector
        self.sector = Sector.objects.create(
            name='Technology',
            code='TECH',
            etf_symbol='XLK',
            volatility_threshold=Decimal('0.35')
        )
        
        # Create test stock with some fundamental data
        self.stock = Stock.objects.create(
            symbol='AAPL',
            name='Apple Inc.',
            sector=self.sector,
            current_price=Decimal('150.00'),
            target_price=Decimal('180.00'),  # 20% upside
            market_cap=2500000000000,  # $2.5T
            exchange='NASDAQ'
        )
        
        # Initialize analyzer
        self.analyzer = FundamentalAnalyzer()
    
    def test_initialization(self):
        """Test FundamentalAnalyzer initialization."""
        self.assertIsNotNone(self.analyzer.stock_service)
        self.assertIsNotNone(self.analyzer.price_service)
        self.assertEqual(self.analyzer.cache_timeout, 86400)  # 24 hours
    
    def test_calculate_financial_ratios_basic(self):
        """Test basic financial ratio calculations."""
        ratios = self.analyzer.calculate_financial_ratios(self.stock)
        
        # Should return a dict with expected keys
        self.assertIsInstance(ratios, dict)
        expected_keys = [
            'pe_ratio', 'pb_ratio', 'ps_ratio', 'roe', 'roa',
            'profit_margin', 'current_ratio', 'quick_ratio',
            'debt_to_equity', 'debt_to_assets', 'asset_turnover',
            'inventory_turnover'
        ]
        
        for key in expected_keys:
            self.assertIn(key, ratios)
    
    def test_calculate_valuation_metrics(self):
        """Test valuation metrics calculation."""
        valuation = self.analyzer.calculate_valuation_metrics(self.stock)
        
        self.assertIsInstance(valuation, dict)
        self.assertEqual(valuation['current_price'], 150.0)
        self.assertEqual(valuation['target_price'], 180.0)
        self.assertEqual(valuation['market_cap'], self.stock.market_cap)
        
        # Check analyst upside calculation
        self.assertAlmostEqual(
            valuation['analyst_upside'],
            0.2,  # 20% upside
            places=2
        )
    
    def test_assess_financial_health_excellent(self):
        """Test financial health assessment for excellent metrics."""
        # Mock excellent ratios
        ratios = {
            'roe': 0.30,  # 30% ROE - Excellent
            'current_ratio': 2.5,  # Strong liquidity
            'debt_to_equity': 0.3  # Low leverage
        }
        
        health = self.analyzer.assess_financial_health(self.stock, ratios)
        
        self.assertEqual(health['overall_score'], 1.0)  # Perfect score
        self.assertEqual(health['rating'], 'Excellent')
        self.assertIn('profitability', health['strengths'])
        self.assertIn('liquidity', health['strengths'])
        self.assertIn('leverage', health['strengths'])
        self.assertEqual(len(health['weaknesses']), 0)
    
    def test_assess_financial_health_poor(self):
        """Test financial health assessment for poor metrics."""
        # Mock poor ratios
        ratios = {
            'roe': 0.02,  # 2% ROE - Poor
            'current_ratio': 0.8,  # Weak liquidity
            'debt_to_equity': 3.0  # High leverage
        }
        
        health = self.analyzer.assess_financial_health(self.stock, ratios)
        
        self.assertEqual(health['overall_score'], 0.0)  # Worst score
        self.assertEqual(health['rating'], 'Very Poor')
        self.assertEqual(len(health['strengths']), 0)
        self.assertIn('profitability', health['weaknesses'])
        self.assertIn('liquidity', health['weaknesses'])
        self.assertIn('leverage', health['weaknesses'])
    
    def test_get_fundamental_signals_buy(self):
        """Test signal generation for buy conditions."""
        ratios = {'pe_ratio': 12.0}  # Undervalued
        valuation = {'upside_potential': 0.25}  # 25% upside
        financial_health = {'overall_score': 0.85, 'rating': 'Excellent'}
        
        signals = self.analyzer.get_fundamental_signals(ratios, valuation, financial_health)
        
        # Should have multiple buy signals
        self.assertIn('valuation', signals)
        self.assertEqual(signals['valuation']['signal'], 'BUY')
        self.assertEqual(signals['valuation']['strength'], 'Strong')
        
        self.assertIn('pe_ratio', signals)
        self.assertEqual(signals['pe_ratio']['signal'], 'BUY')
        
        self.assertIn('financial_health', signals)
        self.assertEqual(signals['financial_health']['signal'], 'BUY')
    
    def test_get_fundamental_signals_sell(self):
        """Test signal generation for sell conditions."""
        ratios = {'pe_ratio': 45.0}  # Overvalued
        valuation = {'upside_potential': -0.30}  # 30% downside
        financial_health = {'overall_score': 0.2, 'rating': 'Poor'}
        
        signals = self.analyzer.get_fundamental_signals(ratios, valuation, financial_health)
        
        # Should have sell signals
        self.assertIn('valuation', signals)
        self.assertEqual(signals['valuation']['signal'], 'SELL')
        self.assertEqual(signals['valuation']['strength'], 'Strong')
        
        self.assertIn('pe_ratio', signals)
        self.assertEqual(signals['pe_ratio']['signal'], 'SELL')
        
        self.assertIn('financial_health', signals)
        self.assertEqual(signals['financial_health']['signal'], 'SELL')
    
    def test_calculate_fundamental_score(self):
        """Test fundamental score calculation."""
        ratios = {'pe_ratio': 20.0}
        valuation = {'upside_potential': 0.15}  # 15% upside
        financial_health = {'overall_score': 0.7}
        growth_metrics = {'revenue_growth': 0.10}  # 10% growth
        
        score = self.analyzer._calculate_fundamental_score(
            ratios, valuation, financial_health, growth_metrics
        )
        
        # Score should be between 0 and 100
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        
        # With positive metrics, score should be above 50
        self.assertGreater(score, 50)
    
    def test_generate_fundamental_recommendation_buy(self):
        """Test recommendation generation for buy scenario."""
        fundamental_score = 75.0
        signals = {
            'valuation': {'signal': 'BUY', 'strength': 'Strong'},
            'pe_ratio': {'signal': 'BUY', 'strength': 'Strong'},
            'financial_health': {'signal': 'BUY', 'strength': 'Moderate'}
        }
        
        recommendation = self.analyzer._generate_fundamental_recommendation(
            fundamental_score, signals
        )
        
        self.assertEqual(recommendation['recommendation'], 'BUY')
        self.assertEqual(recommendation['confidence'], 'HIGH')
        self.assertEqual(recommendation['buy_signals'], 3)
        self.assertEqual(recommendation['sell_signals'], 0)
        self.assertIn('reasoning', recommendation)
    
    def test_generate_fundamental_recommendation_hold(self):
        """Test recommendation generation for hold scenario."""
        fundamental_score = 50.0
        signals = {
            'valuation': {'signal': 'BUY', 'strength': 'Moderate'},
            'pe_ratio': {'signal': 'SELL', 'strength': 'Moderate'},
            'financial_health': {'signal': 'HOLD', 'strength': 'Neutral'}
        }
        
        recommendation = self.analyzer._generate_fundamental_recommendation(
            fundamental_score, signals
        )
        
        self.assertEqual(recommendation['recommendation'], 'HOLD')
        self.assertIn(recommendation['confidence'], ['MEDIUM', 'LOW'])
        self.assertEqual(recommendation['buy_signals'], 1)
        self.assertEqual(recommendation['sell_signals'], 1)
    
    @patch('analytics.services.fundamental.cache')
    def test_analyze_full_integration(self, mock_cache):
        """Test full analysis integration."""
        # Mock cache to return None (not cached)
        mock_cache.get.return_value = None
        
        # Run analysis
        result = self.analyzer.analyze('AAPL')
        
        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertEqual(result['symbol'], 'AAPL')
        self.assertIn('timestamp', result)
        self.assertIn('ratios', result)
        self.assertIn('valuation', result)
        self.assertIn('financial_health', result)
        self.assertIn('growth_metrics', result)
        self.assertIn('signals', result)
        self.assertIn('fundamental_score', result)
        self.assertIn('recommendation', result)
        self.assertIn('analysis_summary', result)
        
        # Verify cache was set
        mock_cache.set.assert_called_once()
        cache_key, cache_data, timeout = mock_cache.set.call_args[0]
        self.assertEqual(cache_key, 'fundamental_analysis:AAPL')
        self.assertEqual(timeout, 86400)  # 24 hours
    
    def test_generate_analysis_summary(self):
        """Test analysis summary generation."""
        ratios = {'pe_ratio': 18.5, 'roe': 0.22}
        valuation = {'upside_potential': 0.15}
        financial_health = {
            'rating': 'Good',
            'strengths': ['profitability', 'liquidity']
        }
        
        summary = self.analyzer._generate_analysis_summary(
            self.stock, ratios, valuation, financial_health
        )
        
        # Summary should contain key information
        self.assertIn('AAPL', summary)
        self.assertIn('undervalued', summary.lower())
        self.assertIn('15.0%', summary)
        self.assertIn('good financial health', summary.lower())
        self.assertIn('profitability', summary)
    
    def test_error_handling(self):
        """Test error handling in analysis."""
        # Test with non-existent stock
        with self.assertRaises(ValueError) as context:
            self.analyzer.analyze('INVALID_SYMBOL')
        
        self.assertIn('not found', str(context.exception))
    
    def test_ratio_thresholds(self):
        """Test that ratio thresholds are properly defined."""
        thresholds = FundamentalAnalyzer.RATIO_THRESHOLDS
        
        # Check P/E thresholds
        self.assertLess(
            thresholds['pe_ratio']['undervalued'],
            thresholds['pe_ratio']['fair']
        )
        self.assertLess(
            thresholds['pe_ratio']['fair'],
            thresholds['pe_ratio']['overvalued']
        )
        
        # Check debt thresholds
        self.assertLess(
            thresholds['debt_to_equity']['low'],
            thresholds['debt_to_equity']['moderate']
        )
        
        # Check ROE thresholds
        self.assertGreater(
            thresholds['roe']['excellent'],
            thresholds['roe']['average']
        )


class FundamentalAnalyzerIntegrationTestCase(TestCase):
    """Integration tests with other services."""
    
    def setUp(self):
        """Set up test environment."""
        # Create test data
        self.sector = Sector.objects.create(
            name='Technology',
            code='TECH',
            etf_symbol='XLK'
        )
        
        self.stock = Stock.objects.create(
            symbol='MSFT',
            name='Microsoft Corporation',
            sector=self.sector,
            current_price=Decimal('300.00'),
            target_price=Decimal('350.00'),
            market_cap=2200000000000
        )
    
    def test_integration_with_orchestrator(self):
        """Test integration with CoreOrchestrator."""
        from core.services.orchestrator import CoreOrchestrator
        
        orchestrator = CoreOrchestrator()
        
        # Verify FundamentalAnalyzer is initialized
        self.assertIsNotNone(orchestrator.fundamental_service)
        self.assertIsInstance(
            orchestrator.fundamental_service,
            FundamentalAnalyzer
        )
    
    @patch('data.services.stock_service.StockService.get_or_fetch_stock')
    def test_comprehensive_analysis_includes_fundamental(self, mock_get_stock):
        """Test that comprehensive analysis includes fundamental analysis."""
        from core.services.orchestrator import CoreOrchestrator
        
        mock_get_stock.return_value = self.stock
        
        orchestrator = CoreOrchestrator()
        result = orchestrator.perform_comprehensive_analysis(
            'MSFT',
            include_fundamental=True
        )
        
        # Verify fundamental analysis is included
        self.assertIn('fundamental_analysis', result)
        fund_analysis = result['fundamental_analysis']
        
        self.assertIn('ratios', fund_analysis)
        self.assertIn('valuation', fund_analysis)
        self.assertIn('financial_health', fund_analysis)
        self.assertIn('recommendation', fund_analysis)