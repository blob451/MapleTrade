"""
Tests for Technical Indicators functionality (Task 3.2).
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from django.test import TestCase
from django.core.cache import cache
from unittest.mock import patch, MagicMock

from ..technical_indicators import TechnicalIndicators
from ..models import Stock, Sector, TechnicalIndicator
from ..cache import technical_cache


class TechnicalIndicatorsTest(TestCase):
    """Test cases for TechnicalIndicators class."""
    
    def setUp(self):
        """Set up test data."""
        # Create test sector
        self.sector = Sector.objects.create(
            name='Technology',
            code='TECH',
            etf_symbol='XLK',
            volatility_threshold=0.35
        )
        
        # Create test stock
        self.stock = Stock.objects.create(
            symbol='NVDA',
            name='NVIDIA Corporation',
            sector=self.sector
        )
        
        # Create sample price data
        dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
        np.random.seed(42)  # For reproducible tests
        
        # Generate realistic price data with trend
        base_price = 100
        price_changes = np.random.normal(0.001, 0.02, len(dates))  # Small daily changes
        cumulative_changes = np.cumsum(price_changes)
        
        self.price_data = pd.DataFrame({
            'date': dates,
            'open': base_price + cumulative_changes + np.random.normal(0, 0.5, len(dates)),
            'high': base_price + cumulative_changes + np.random.normal(1, 0.5, len(dates)),
            'low': base_price + cumulative_changes + np.random.normal(-1, 0.5, len(dates)),
            'close': base_price + cumulative_changes,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        })
        
        # Ensure high >= close >= low and open is reasonable
        self.price_data['high'] = np.maximum(self.price_data['high'], self.price_data['close'])
        self.price_data['low'] = np.minimum(self.price_data['low'], self.price_data['close'])
        self.price_data['open'] = np.where(
            self.price_data['open'] > self.price_data['high'],
            self.price_data['high'] - 0.1,
            self.price_data['open']
        )
        self.price_data['open'] = np.where(
            self.price_data['open'] < self.price_data['low'],
            self.price_data['low'] + 0.1,
            self.price_data['open']
        )
        
        # Clear cache before each test
        cache.clear()
    
    def test_initialization(self):
        """Test TechnicalIndicators initialization."""
        indicators = TechnicalIndicators('NVDA', self.price_data)
        
        self.assertEqual(indicators.symbol, 'NVDA')
        self.assertIsInstance(indicators.price_data, pd.DataFrame)
        self.assertTrue(len(indicators.price_data) > 0)
    
    def test_data_validation(self):
        """Test price data validation."""
        # Test with missing columns
        invalid_data = pd.DataFrame({'close': [100, 101, 102]})
        
        with self.assertRaises(ValueError):
            TechnicalIndicators('NVDA', invalid_data)
        
        # Test with insufficient data
        small_data = pd.DataFrame({
            'open': [100, 101],
            'high': [101, 102],
            'low': [99, 100],
            'close': [100.5, 101.5],
            'volume': [1000, 1100]
        })
        
        with self.assertRaises(ValueError):
            TechnicalIndicators('NVDA', small_data)
    
    def test_sma_calculation(self):
        """Test Simple Moving Average calculation."""
        indicators = TechnicalIndicators('NVDA', self.price_data)
        
        sma_result = indicators.calculate_sma(period=20)
        
        self.assertIsInstance(sma_result, dict)
        self.assertEqual(sma_result['indicator'], 'SMA')
        self.assertEqual(sma_result['period'], 20)
        self.assertIsNotNone(sma_result['current_value'])
        self.assertIsInstance(sma_result['series'], list)
        self.assertIn(sma_result['signal'], ['BULLISH', 'BEARISH', 'NEUTRAL'])
        
        # Verify calculation accuracy
        manual_sma = self.price_data['close'].rolling(window=20).mean().iloc[-1]
        self.assertAlmostEqual(sma_result['current_value'], manual_sma, places=2)
    
    def test_ema_calculation(self):
        """Test Exponential Moving Average calculation."""
        indicators = TechnicalIndicators('NVDA', self.price_data)
        
        ema_result = indicators.calculate_ema(period=12)
        
        self.assertIsInstance(ema_result, dict)
        self.assertEqual(ema_result['indicator'], 'EMA')
        self.assertEqual(ema_result['period'], 12)
        self.assertIsNotNone(ema_result['current_value'])
        self.assertIsInstance(ema_result['series'], list)
        
        # Verify calculation accuracy
        manual_ema = self.price_data['close'].ewm(span=12, adjust=False).mean().iloc[-1]
        self.assertAlmostEqual(ema_result['current_value'], manual_ema, places=2)
    
    def test_rsi_calculation(self):
        """Test RSI calculation."""
        indicators = TechnicalIndicators('NVDA', self.price_data)
        
        rsi_result = indicators.calculate_rsi(period=14)
        
        self.assertIsInstance(rsi_result, dict)
        self.assertEqual(rsi_result['indicator'], 'RSI')
        self.assertEqual(rsi_result['period'], 14)
        self.assertIsNotNone(rsi_result['current_value'])
        
        # RSI should be between 0 and 100
        self.assertGreaterEqual(rsi_result['current_value'], 0)
        self.assertLessEqual(rsi_result['current_value'], 100)
        
        # Test signal generation
        self.assertIn(rsi_result['signal'], ['BULLISH', 'BEARISH', 'OVERBOUGHT', 'OVERSOLD', 'NEUTRAL'])
    
    def test_macd_calculation(self):
        """Test MACD calculation."""
        indicators = TechnicalIndicators('NVDA', self.price_data)
        
        macd_result = indicators.calculate_macd()
        
        self.assertIsInstance(macd_result, dict)
        self.assertEqual(macd_result['indicator'], 'MACD')
        self.assertIn('macd_line', macd_result)
        self.assertIn('signal_line', macd_result)
        self.assertIn('histogram', macd_result)
        
        # Verify structure of sub-components
        for component in ['macd_line', 'signal_line', 'histogram']:
            self.assertIn('current_value', macd_result[component])
            self.assertIn('series', macd_result[component])
            self.assertIsNotNone(macd_result[component]['current_value'])
    
    def test_bollinger_bands_calculation(self):
        """Test Bollinger Bands calculation."""
        indicators = TechnicalIndicators('NVDA', self.price_data)
        
        bb_result = indicators.calculate_bollinger_bands()
        
        self.assertIsInstance(bb_result, dict)
        self.assertEqual(bb_result['indicator'], 'Bollinger Bands')
        self.assertIn('upper_band', bb_result)
        self.assertIn('middle_band', bb_result)
        self.assertIn('lower_band', bb_result)
        self.assertIn('position', bb_result)
        
        # Verify band ordering
        upper = bb_result['upper_band']['current_value']
        middle = bb_result['middle_band']['current_value']
        lower = bb_result['lower_band']['current_value']
        
        self.assertGreater(upper, middle)
        self.assertGreater(middle, lower)
        
        # Position should be between 0 and 100
        self.assertGreaterEqual(bb_result['position'], 0)
        self.assertLessEqual(bb_result['position'], 100)
    
    def test_calculate_all_indicators(self):
        """Test calculating all indicators at once."""
        indicators = TechnicalIndicators('NVDA', self.price_data)
        
        all_indicators = indicators.calculate_all_indicators()
        
        expected_indicators = ['sma_20', 'sma_50', 'ema_12', 'ema_26', 'rsi_14', 'macd', 'bollinger_bands']
        
        for indicator in expected_indicators:
            self.assertIn(indicator, all_indicators)
        
        # Check overall signal
        self.assertIn('overall_signal', all_indicators)
        overall = all_indicators['overall_signal']
        self.assertIn('signal', overall)
        self.assertIn('confidence', overall)
        self.assertIn(overall['signal'], ['BUY', 'SELL', 'HOLD', 'STRONG_BUY', 'STRONG_SELL'])
    
    def test_caching_functionality(self):
        """Test that caching is working properly."""
        indicators = TechnicalIndicators('NVDA', self.price_data)
        
        # First calculation should cache result
        sma_result1 = indicators.calculate_sma(period=20)
        
        # Second calculation should use cache
        with patch('analytics.technical_indicators.logger') as mock_logger:
            sma_result2 = indicators.calculate_sma(period=20)
            
            # Results should be identical
            self.assertEqual(sma_result1['current_value'], sma_result2['current_value'])
            
            # Should have logged cache usage
            mock_logger.debug.assert_called()
    
    def test_signal_generation(self):
        """Test signal generation logic."""
        indicators = TechnicalIndicators('NVDA', self.price_data)
        
        # Test SMA signal
        sma_series = pd.Series([100, 101, 102, 103, 104])  # Uptrend
        current_price = 106  # Above SMA
        indicators.price_data = pd.DataFrame({'close': [current_price]})
        
        signal = indicators._generate_sma_signal(sma_series)
        self.assertEqual(signal, 'BULLISH')
        
        # Test RSI signals
        self.assertEqual(indicators._generate_rsi_signal(75), 'OVERBOUGHT')
        self.assertEqual(indicators._generate_rsi_signal(25), 'OVERSOLD')
        self.assertEqual(indicators._generate_rsi_signal(55), 'BULLISH')
        self.assertEqual(indicators._generate_rsi_signal(45), 'BEARISH')
    
    def test_error_handling(self):
        """Test error handling in calculations."""
        # Create data with NaN values to test error handling
        bad_data = self.price_data.copy()
        bad_data.loc[bad_data.index[-10:], 'close'] = np.nan
        
        indicators = TechnicalIndicators('NVDA', bad_data)
        
        # Should handle NaN values gracefully
        try:
            sma_result = indicators.calculate_sma(period=20)
            self.assertIsInstance(sma_result, dict)
        except Exception as e:
            self.fail(f"SMA calculation failed on data with NaN: {e}")


class TechnicalIndicatorModelTest(TestCase):
    """Test TechnicalIndicator model."""
    
    def setUp(self):
        """Set up test data."""
        self.sector = Sector.objects.create(
            name='Technology',
            code='TECH',
            etf_symbol='XLK'
        )
        
        self.stock = Stock.objects.create(
            symbol='NVDA',
            name='NVIDIA Corporation',
            sector=self.sector
        )
    
    def test_technical_indicator_creation(self):
        """Test creating technical indicator records."""
        indicator = TechnicalIndicator.objects.create(
            stock=self.stock,
            indicator_type='RSI',
            calculation_date=datetime.now(),
            period=14,
            current_value=65.5,
            signal='BULLISH',
            confidence=0.8,
            data={'series': [60, 62, 64, 65.5], 'test_data': 'value'}
        )
        
        self.assertEqual(indicator.stock, self.stock)
        self.assertEqual(indicator.indicator_type, 'RSI')
        self.assertEqual(indicator.current_value, 65.5)
        self.assertEqual(indicator.signal, 'BULLISH')
        self.assertEqual(indicator.data['test_data'], 'value')
    
    def test_get_series_data(self):
        """Test getting series data from JSON field."""
        test_series = [60, 62, 64, 65.5]
        
        indicator = TechnicalIndicator.objects.create(
            stock=self.stock,
            indicator_type='SMA',
            calculation_date=datetime.now(),
            period=20,
            current_value=65.5,
            data={'series': test_series}
        )
        
        retrieved_series = indicator.get_series_data()
        self.assertEqual(retrieved_series, test_series)
    
    def test_set_additional_value(self):
        """Test setting additional values in JSON field."""
        indicator = TechnicalIndicator.objects.create(
            stock=self.stock,
            indicator_type='MACD',
            calculation_date=datetime.now()
        )
        
        indicator.set_additional_value('macd_line', 1.5)
        indicator.set_additional_value('signal_line', 1.2)
        indicator.save()
        
        # Refresh from database
        indicator.refresh_from_db()
        
        self.assertEqual(indicator.data['macd_line'], 1.5)
        self.assertEqual(indicator.data['signal_line'], 1.2)


class CacheTest(TestCase):
    """Test caching functionality."""
    
    def setUp(self):
        """Clear cache before each test."""
        cache.clear()
    
    def test_technical_cache_key_generation(self):
        """Test cache key generation."""
        cache_key = technical_cache.get_indicator_key('NVDA', 'sma', period=20)
        
        self.assertIsInstance(cache_key, str)
        self.assertIn('NVDA', cache_key)
        self.assertIn('sma', cache_key)
    
    def test_cache_indicator_result(self):
        """Test caching indicator results."""
        test_result = {
            'indicator': 'SMA',
            'current_value': 150.5,
            'signal': 'BULLISH'
        }
        
        success = technical_cache.cache_indicator_result('NVDA', 'sma', test_result, period=20)
        self.assertTrue(success)
        
        # Retrieve cached result
        cached_result = technical_cache.get_indicator_result('NVDA', 'sma', period=20)
        self.assertIsNotNone(cached_result)
        self.assertEqual(cached_result['current_value'], 150.5)
        self.assertEqual(cached_result['signal'], 'BULLISH')


class IntegrationTest(TestCase):
    """Integration tests for complete technical analysis workflow."""
    
    def setUp(self):
        """Set up test data."""
        self.sector = Sector.objects.create(
            name='Technology',
            code='TECH',
            etf_symbol='XLK'
        )
        
        self.stock = Stock.objects.create(
            symbol='NVDA',
            name='NVIDIA Corporation',
            sector=self.sector
        )
        
        # Create realistic test data
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        np.random.seed(42)
        
        base_price = 100
        price_changes = np.random.normal(0.001, 0.02, len(dates))
        cumulative_changes = np.cumsum(price_changes)
        
        self.price_data = pd.DataFrame({
            'date': dates,
            'open': base_price + cumulative_changes + np.random.normal(0, 0.5, len(dates)),
            'high': base_price + cumulative_changes + np.random.normal(1, 0.5, len(dates)),
            'low': base_price + cumulative_changes + np.random.normal(-1, 0.5, len(dates)),
            'close': base_price + cumulative_changes,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        })
        
        # Fix price relationships
        self.price_data['high'] = np.maximum(self.price_data['high'], self.price_data['close'])
        self.price_data['low'] = np.minimum(self.price_data['low'], self.price_data['close'])
    
    @patch('analytics.services.yf.Ticker')
    def test_complete_technical_analysis_workflow(self, mock_ticker):
        """Test complete workflow from data to database storage."""
        # Mock yfinance data
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {
            'shortName': 'NVIDIA Corporation',
            'sector': 'Technology',
            'exchange': 'NASDAQ'
        }
        mock_ticker.return_value = mock_ticker_instance
        
        from ..services import AnalyticsEngine
        
        engine = AnalyticsEngine()
        
        # Test technical analysis component
        with patch.object(engine, '_fetch_price_data', return_value=self.price_data):
            technical_result = engine._perform_technical_analysis(self.stock, self.price_data)
            
            self.assertIsInstance(technical_result, dict)
            self.assertIn('signal', technical_result)
            self.assertIn('indicators', technical_result)
            self.assertIn('confidence', technical_result)
            
            # Verify indicators were calculated
            indicators = technical_result['indicators']
            expected_indicators = ['sma_20', 'sma_50', 'ema_12', 'ema_26', 'rsi_14', 'macd', 'bollinger_bands']
            
            for indicator in expected_indicators:
                self.assertIn(indicator, indicators)
            
            # Check that technical indicators were saved to database
            saved_indicators = TechnicalIndicator.objects.filter(stock=self.stock)
            self.assertGreater(saved_indicators.count(), 0)


if __name__ == '__main__':
    unittest.main()