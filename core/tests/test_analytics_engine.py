"""
Unit tests for the Analytics Engine implementation.

These tests verify that the analytics engine correctly implements
the three-factor model logic from the prototype.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from core.models import Stock, Sector, PriceData
from core.services.analytics_engine import AnalyticsEngine, AnalysisSignals, AnalyticsEngineError
from core.services.calculations import ReturnCalculator, VolatilityCalculator, CalculationError
from core.services.sector_mapping import SectorMapper
from data.providers.base import StockInfo, PriceData as ProviderPriceData


class AnalyticsEngineTestCase(TestCase):
    """Test cases for the main AnalyticsEngine class."""
    
    def setUp(self):
        """Set up test data."""
        # Create test sector
        self.test_sector = Sector.objects.create(
            name='Technology',
            code='TECH',
            etf_symbol='XLK',
            volatility_threshold=Decimal('0.42'),
            description='Technology sector'
        )
        
        # Create test stock
        self.test_stock = Stock.objects.create(
            symbol='NVDA',
            name='NVIDIA Corporation',
            sector=self.test_sector,
            current_price=Decimal('500.00'),
            target_price=Decimal('600.00'),
            market_cap=1000000000,
            exchange='NASDAQ'
        )
        
        self.engine = AnalyticsEngine()
    
    @patch('core.services.analytics_engine.YahooFinanceProvider')
    def test_analyze_stock_basic_flow(self, mock_provider_class):
        """Test basic analysis flow with mocked data."""
        # Mock the data provider
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        
        # Mock stock info
        mock_provider.get_stock_info.return_value = StockInfo(
            symbol='NVDA',
            name='NVIDIA Corporation',
            sector='Technology',
            current_price=Decimal('500.00'),
            target_price=Decimal('600.00'),
            market_cap=1000000000,
            exchange='NASDAQ',
            currency='USD',
            last_updated=timezone.now()
        )
        
        # Mock price history
        base_date = date(2024, 1, 1)
        mock_stock_prices = [
            ProviderPriceData(
                date=base_date + timedelta(days=i),
                open=100 + i,
                high=105 + i,
                low=95 + i,
                close=100 + i * 2,  # Strong uptrend
                volume=1000000
            ) for i in range(30)
        ]
        
        mock_sector_prices = [
            ProviderPriceData(
                date=base_date + timedelta(days=i),
                open=100 + i * 0.5,
                high=105 + i * 0.5,
                low=95 + i * 0.5,
                close=100 + i,  # Weaker uptrend
                volume=5000000
            ) for i in range(30)
        ]
        
        mock_provider.get_price_history.side_effect = [mock_stock_prices, mock_sector_prices]
        
        # Create engine with mocked provider
        engine = AnalyticsEngine()
        engine.data_provider = mock_provider
        
        # Run analysis
        result = engine.analyze_stock('NVDA', 12)
        
        # Verify result structure
        self.assertIsNotNone(result)
        self.assertIn(result.signal, ['BUY', 'SELL', 'HOLD'])
        self.assertIn(result.confidence, ['HIGH', 'MEDIUM', 'LOW'])
        self.assertIsInstance(result.stock_return, float)
        self.assertIsInstance(result.volatility, float)
        
        # Given our mock data, stock should outperform sector
        self.assertTrue(result.signals.outperformed_sector)
        
        # Target price is above current price
        self.assertTrue(result.signals.target_above_price)
    
    def test_decision_logic_all_positive(self):
        """Test decision logic when all signals are positive."""
        signals = AnalysisSignals(
            outperformed_sector=True,
            target_above_price=True,
            volatility_below_threshold=True
        )
        
        signal, confidence = self.engine._apply_decision_logic(signals)
        
        self.assertEqual(signal, 'BUY')
        self.assertEqual(confidence, 'HIGH')
    
    def test_decision_logic_mixed_signals_low_vol(self):
        """Test decision logic with one positive signal and low volatility."""
        signals = AnalysisSignals(
            outperformed_sector=True,
            target_above_price=False,
            volatility_below_threshold=True
        )
        
        signal, confidence = self.engine._apply_decision_logic(signals)
        
        self.assertEqual(signal, 'BUY')
        self.assertEqual(confidence, 'MEDIUM')
    
    def test_decision_logic_mixed_signals_high_vol(self):
        """Test decision logic with one positive signal and high volatility."""
        signals = AnalysisSignals(
            outperformed_sector=True,
            target_above_price=False,
            volatility_below_threshold=False
        )
        
        signal, confidence = self.engine._apply_decision_logic(signals)
        
        self.assertEqual(signal, 'HOLD')
        self.assertEqual(confidence, 'MEDIUM')
    
    def test_decision_logic_all_negative_low_vol(self):
        """Test decision logic when both signals are negative but volatility is low."""
        signals = AnalysisSignals(
            outperformed_sector=False,
            target_above_price=False,
            volatility_below_threshold=True
        )
        
        signal, confidence = self.engine._apply_decision_logic(signals)
        
        self.assertEqual(signal, 'HOLD')
        self.assertEqual(confidence, 'LOW')
    
    def test_decision_logic_all_negative_high_vol(self):
        """Test decision logic when both signals are negative and volatility is high."""
        signals = AnalysisSignals(
            outperformed_sector=False,
            target_above_price=False,
            volatility_below_threshold=False
        )
        
        signal, confidence = self.engine._apply_decision_logic(signals)
        
        self.assertEqual(signal, 'SELL')
        self.assertEqual(confidence, 'MEDIUM')


class CalculationsTestCase(TestCase):
    """Test cases for calculation services."""
    
    def setUp(self):
        """Set up test calculators."""
        self.return_calc = ReturnCalculator()
        self.vol_calc = VolatilityCalculator()
    
    def test_total_return_calculation(self):
        """Test total return calculation with known data."""
        # Create sample price data
        price_data = [
            ProviderPriceData(date=date(2024, 1, 1), open=100, high=105, low=95, close=100, volume=1000),
            ProviderPriceData(date=date(2024, 1, 2), open=100, high=105, low=95, close=110, volume=1000),
            ProviderPriceData(date=date(2024, 1, 3), open=110, high=115, low=105, close=120, volume=1000),
        ]
        
        total_return = self.return_calc.calculate_total_return(price_data)
        
        # Expected: (120 - 100) / 100 = 0.20 = 20%
        self.assertAlmostEqual(total_return, 0.20, places=4)
    
    def test_return_calculation_insufficient_data(self):
        """Test return calculation with insufficient data."""
        price_data = [
            ProviderPriceData(date=date(2024, 1, 1), open=100, high=105, low=95, close=100, volume=1000)
        ]
        
        with self.assertRaises(CalculationError):
            self.return_calc.calculate_total_return(price_data)
    
    def test_volatility_calculation(self):
        """Test volatility calculation with sample data."""
        # Create sample data with known volatility pattern
        price_data = []
        base_price = 100
        
        for i in range(50):  # 50 days of data
            # Simulate some volatility
            price_change = (-1) ** i * (i % 5)  # Alternating pattern
            close_price = base_price + price_change
            
            price_data.append(ProviderPriceData(
                date=date(2024, 1, 1) + timedelta(days=i),
                open=close_price,
                high=close_price + 2,
                low=close_price - 2,
                close=close_price,
                volume=1000000
            ))
        
        volatility = self.vol_calc.calculate_annualized_volatility(price_data)
        
        # Should return a reasonable volatility value
        self.assertGreater(volatility, 0)
        self.assertLess(volatility, 2.0)  # Less than 200% volatility
    
    def test_period_returns_calculation(self):
        """Test period returns calculation."""
        price_data = [
            ProviderPriceData(date=date(2024, 1, 1), open=100, high=105, low=95, close=100, volume=1000),
            ProviderPriceData(date=date(2024, 1, 2), open=100, high=105, low=95, close=110, volume=1000),
            ProviderPriceData(date=date(2024, 1, 3), open=110, high=115, low=105, close=99, volume=1000),
        ]
        
        returns = self.return_calc.calculate_period_returns(price_data)
        
        # Expected returns: [0.10, -0.10] (10% up, then 10% down)
        self.assertEqual(len(returns), 2)
        self.assertAlmostEqual(returns[0], 0.10, places=4)
        self.assertAlmostEqual(returns[1], -0.10, places=4)


class SectorMappingTestCase(TestCase):
    """Test cases for sector mapping functionality."""
    
    def setUp(self):
        """Set up sector mapper."""
        self.mapper = SectorMapper()
    
    def test_technology_sector_mapping(self):
        """Test mapping of technology sector."""
        sector = self.mapper.map_stock_to_sector('Technology')
        
        self.assertIsNotNone(sector)
        self.assertEqual(sector.code, 'TECH')
        self.assertEqual(sector.etf_symbol, 'XLK')
    
    def test_financial_sector_mapping(self):
        """Test mapping of financial sector."""
        sector = self.mapper.map_stock_to_sector('Financial Services')
        
        self.assertIsNotNone(sector)
        self.assertEqual(sector.code, 'FINANCIALS')
        self.assertEqual(sector.etf_symbol, 'XLF')
    
    def test_partial_sector_matching(self):
        """Test partial matching for sector names."""
        # Should match 'Technology' mapping
        sector = self.mapper.map_stock_to_sector('Technology Hardware')
        
        self.assertIsNotNone(sector)
        self.assertEqual(sector.code, 'TECH')
    
    def test_unknown_sector_mapping(self):
        """Test handling of unknown sector names."""
        sector = self.mapper.map_stock_to_sector('Unknown Sector XYZ')
        
        self.assertIsNone(sector)
    
    def test_empty_sector_mapping(self):
        """Test handling of empty sector name."""
        sector = self.mapper.map_stock_to_sector('')
        self.assertIsNone(sector)
        
        sector = self.mapper.map_stock_to_sector(None)
        self.assertIsNone(sector)


class AnalysisSignalsTestCase(TestCase):
    """Test cases for AnalysisSignals data class."""
    
    def test_signals_creation(self):
        """Test creation of AnalysisSignals."""
        signals = AnalysisSignals(
            outperformed_sector=True,
            target_above_price=False,
            volatility_below_threshold=True,
            stock_return=0.15,
            sector_return=0.10,
            volatility=0.25
        )
        
        self.assertTrue(signals.outperformed_sector)
        self.assertFalse(signals.target_above_price)
        self.assertTrue(signals.volatility_below_threshold)
        self.assertEqual(signals.stock_return, 0.15)
        self.assertEqual(signals.sector_return, 0.10)
        self.assertEqual(signals.volatility, 0.25)


class IntegrationTestCase(TestCase):
    """Integration tests for the complete analytics workflow."""
    
    def setUp(self):
        """Set up integration test environment."""
        # Create complete test environment
        self.sector = Sector.objects.create(
            name='Technology',
            code='TECH',
            etf_symbol='XLK',
            volatility_threshold=Decimal('0.40'),
            description='Technology sector'
        )
        
        self.stock = Stock.objects.create(
            symbol='TEST',
            name='Test Corporation',
            sector=self.sector,
            current_price=Decimal('100.00'),
            target_price=Decimal('120.00'),
            is_active=True
        )
    
    @patch('core.services.analytics_engine.YahooFinanceProvider')
    def test_end_to_end_analysis(self, mock_provider_class):
        """Test complete end-to-end analysis workflow."""
        # Setup mocks
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        
        mock_provider.get_stock_info.return_value = StockInfo(
            symbol='TEST',
            name='Test Corporation',
            sector='Technology',
            current_price=Decimal('100.00'),
            target_price=Decimal('120.00'),
            market_cap=1000000000,
            exchange='NASDAQ',
            currency='USD',
            last_updated=timezone.now()
        )
        
        # Create realistic price data that should generate a BUY signal
        stock_prices = []
        sector_prices = []
        
        for i in range(252):  # 1 year of data
            stock_price = 80 + i * 0.1  # Steady uptrend
            sector_price = 100 + i * 0.05  # Weaker uptrend
            
            price_date = date(2023, 1, 1) + timedelta(days=i)
            
            stock_prices.append(ProviderPriceData(
                date=price_date,
                open=stock_price,
                high=stock_price + 1,
                low=stock_price - 1,
                close=stock_price,
                volume=1000000
            ))
            
            sector_prices.append(ProviderPriceData(
                date=price_date,
                open=sector_price,
                high=sector_price + 0.5,
                low=sector_price - 0.5,
                close=sector_price,
                volume=5000000
            ))
        
        mock_provider.get_price_history.side_effect = [stock_prices, sector_prices]
        
        # Run analysis
        engine = AnalyticsEngine()
        engine.data_provider = mock_provider
        
        result = engine.analyze_stock('TEST', 12)
        
        # Verify results
        self.assertIsNotNone(result)
        self.assertEqual(result.signal, 'BUY')  # Should be BUY based on our data
        self.assertGreater(result.stock_return, result.sector_return)  # Stock outperformed
        self.assertTrue(result.signals.outperformed_sector)
        self.assertTrue(result.signals.target_above_price)  # 120 > 100
        self.assertIsNotNone(result.rationale)
        self.assertTrue(len(result.rationale) > 50)  # Should have meaningful explanation


class ErrorHandlingTestCase(TestCase):
    """Test error handling in analytics engine."""
    
    def setUp(self):
        """Set up error handling tests."""
        self.engine = AnalyticsEngine()
    
    @patch('core.services.analytics_engine.YahooFinanceProvider')
    def test_invalid_symbol_handling(self, mock_provider_class):
        """Test handling of invalid stock symbols."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        
        # Mock provider to raise exception for invalid symbol
        mock_provider.get_stock_info.side_effect = Exception("Symbol not found")
        
        engine = AnalyticsEngine()
        engine.data_provider = mock_provider
        
        with self.assertRaises(AnalyticsEngineError):
            engine.analyze_stock('INVALID', 12)
    
    @patch('core.services.analytics_engine.YahooFinanceProvider')
    def test_insufficient_price_data_handling(self, mock_provider_class):
        """Test handling when insufficient price data is available."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        
        mock_provider.get_stock_info.return_value = StockInfo(
            symbol='TEST',
            name='Test Corporation',
            sector='Technology',
            current_price=Decimal('100.00'),
            target_price=Decimal('120.00'),
            market_cap=1000000000,
            exchange='NASDAQ',
            currency='USD',
            last_updated=timezone.now()
        )
        
        # Return insufficient price data
        mock_provider.get_price_history.return_value = []
        
        engine = AnalyticsEngine()
        engine.data_provider = mock_provider
        
        with self.assertRaises(AnalyticsEngineError):
            engine.analyze_stock('TEST', 12)


# Test fixtures and utilities
class AnalyticsTestUtils:
    """Utility class for analytics testing."""
    
    @staticmethod
    def create_test_sector(code='TEST', name='Test Sector', etf='SPY', vol_threshold=0.30):
        """Create a test sector."""
        return Sector.objects.create(
            code=code,
            name=name,
            etf_symbol=etf,
            volatility_threshold=Decimal(str(vol_threshold)),
            description=f'Test sector: {name}'
        )
    
    @staticmethod
    def create_test_stock(symbol='TEST', sector=None, price=100, target=120):
        """Create a test stock."""
        if sector is None:
            sector = AnalyticsTestUtils.create_test_sector()
            
        return Stock.objects.create(
            symbol=symbol,
            name=f'{symbol} Corporation',
            sector=sector,
            current_price=Decimal(str(price)),
            target_price=Decimal(str(target)),
            is_active=True
        )
    
    @staticmethod
    def create_sample_price_data(num_days=30, start_price=100, trend=0.1):
        """Create sample price data for testing."""
        price_data = []
        base_date = date(2024, 1, 1)
        
        for i in range(num_days):
            price = start_price + i * trend
            price_data.append(ProviderPriceData(
                date=base_date + timedelta(days=i),
                open=price,
                high=price + 2,
                low=price - 2,
                close=price,
                volume=1000000
            ))
        
        return price_data


# Performance tests (can be run separately)
class PerformanceTestCase(TestCase):
    """Performance tests for analytics engine."""
    
    def setUp(self):
        """Set up performance tests."""
        self.sector = Sector.objects.create(
            name='Technology',
            code='TECH',
            etf_symbol='XLK',
            volatility_threshold=Decimal('0.40')
        )
    
    @patch('core.services.analytics_engine.YahooFinanceProvider')
    def test_analysis_performance(self, mock_provider_class):
        """Test analysis performance with realistic data size."""
        import time
        
        # Setup large dataset (3 years of daily data)
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        
        # Create 3 years of price data
        large_dataset = AnalyticsTestUtils.create_sample_price_data(
            num_days=1095,  # ~3 years
            start_price=100,
            trend=0.05
        )
        
        mock_provider.get_stock_info.return_value = StockInfo(
            symbol='PERF',
            name='Performance Test',
            sector='Technology',
            current_price=Decimal('150.00'),
            target_price=Decimal('180.00'),
            market_cap=1000000000,
            exchange='NASDAQ',
            currency='USD',
            last_updated=timezone.now()
        )
        
        mock_provider.get_price_history.return_value = large_dataset
        
        # Time the analysis
        engine = AnalyticsEngine()
        engine.data_provider = mock_provider
        
        start_time = time.time()
        result = engine.analyze_stock('PERF', 36)  # 3 years
        end_time = time.time()
        
        # Analysis should complete in reasonable time (< 5 seconds)
        analysis_time = end_time - start_time
        self.assertLess(analysis_time, 5.0, f"Analysis took {analysis_time:.2f} seconds")
        
        # Result should still be valid
        self.assertIsNotNone(result)
        self.assertIn(result.signal, ['BUY', 'SELL', 'HOLD'])