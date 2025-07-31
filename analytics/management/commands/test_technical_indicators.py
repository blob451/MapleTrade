"""
Management command to test technical indicators functionality.
Usage: python manage.py test_technical_indicators [symbol]
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.core.cache import cache
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
import json

from analytics.models import Stock, Sector, TechnicalIndicator
from analytics.technical_indicators import TechnicalIndicators
from analytics.services import analyze_stock_complete


class Command(BaseCommand):
    help = 'Test technical indicators functionality with real or sample data'

    def add_arguments(self, parser):
        parser.add_argument(
            'symbol',
            nargs='?',
            type=str,
            default='NVDA',
            help='Stock symbol to test (default: NVDA)'
        )
        parser.add_argument(
            '--use-sample-data',
            action='store_true',
            help='Use generated sample data instead of fetching from Yahoo Finance'
        )
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Clear cache before testing'
        )
        parser.add_argument(
            '--test-all-indicators',
            action='store_true',
            help='Test all individual indicators separately'
        )
        parser.add_argument(
            '--save-to-db',
            action='store_true',
            help='Save results to database'
        )

    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        
        self.stdout.write(
            self.style.SUCCESS(f'🚀 Testing Technical Indicators for {symbol}')
        )
        self.stdout.write('=' * 60)
        
        # Clear cache if requested
        if options['clear_cache']:
            cache.clear()
            self.stdout.write(self.style.WARNING('🗑️  Cache cleared'))
        
        try:
            # Step 1: Get price data
            if options['use_sample_data']:
                price_data = self._generate_sample_data()
                self.stdout.write(self.style.SUCCESS('📊 Generated sample price data'))
            else:
                price_data = self._fetch_real_data(symbol)
                self.stdout.write(self.style.SUCCESS(f'📈 Fetched real price data for {symbol}'))
            
            self.stdout.write(f'   Data points: {len(price_data)}')
            self.stdout.write(f'   Date range: {price_data["date"].iloc[0].date()} to {price_data["date"].iloc[-1].date()}')
            self.stdout.write(f'   Current price: ${price_data["close"].iloc[-1]:.2f}')
            
            # Step 2: Initialize technical indicators
            tech_indicators = TechnicalIndicators(symbol, price_data)
            self.stdout.write('\n✅ TechnicalIndicators initialized successfully')
            
            # Step 3: Test individual indicators if requested
            if options['test_all_indicators']:
                self._test_individual_indicators(tech_indicators)
            
            # Step 4: Test complete analysis
            self.stdout.write('\n🔍 Running complete technical analysis...')
            all_indicators = tech_indicators.calculate_all_indicators()
            
            # Display results
            self._display_results(all_indicators)
            
            # Step 5: Test full analytics engine integration
            self.stdout.write('\n🔧 Testing Analytics Engine integration...')
            if not options['use_sample_data']:
                complete_analysis = analyze_stock_complete(symbol, include_technical=True)
                self._display_complete_analysis(complete_analysis)
            
            # Step 6: Save to database if requested
            if options['save_to_db'] and not options['use_sample_data']:
                self._save_to_database(symbol, all_indicators)
            
            # Step 7: Test caching
            self._test_caching(tech_indicators)
            
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('🎉 All tests completed successfully!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Test failed: {str(e)}'))
            raise CommandError(f'Technical indicators test failed: {e}')

    def _generate_sample_data(self):
        """Generate sample price data for testing."""
        dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
        np.random.seed(42)  # For reproducible results
        
        # Generate realistic price movement
        base_price = 100
        trend = np.linspace(0, 50, len(dates))  # Upward trend
        noise = np.random.normal(0, 2, len(dates))
        volatility = np.random.normal(0, 0.5, len(dates))
        
        close_prices = base_price + trend + np.cumsum(noise) + volatility
        
        # Generate OHLV data
        price_data = pd.DataFrame({
            'date': dates,
            'open': close_prices + np.random.normal(0, 0.5, len(dates)),
            'high': close_prices + np.abs(np.random.normal(1, 0.5, len(dates))),
            'low': close_prices - np.abs(np.random.normal(1, 0.5, len(dates))),
            'close': close_prices,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        })
        
        # Ensure proper OHLC relationships
        price_data['high'] = np.maximum(price_data['high'], price_data['close'])
        price_data['low'] = np.minimum(price_data['low'], price_data['close'])
        price_data['open'] = np.clip(
            price_data['open'], 
            price_data['low'] + 0.01, 
            price_data['high'] - 0.01
        )
        
        return price_data

    def _fetch_real_data(self, symbol):
        """Fetch real price data from Yahoo Finance."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)  # 1 year of data
        
        ticker = yf.Ticker(symbol)
        data = ticker.history(start=start_date, end=end_date)
        
        if data.empty:
            raise CommandError(f'No data found for symbol {symbol}')
        
        price_data = pd.DataFrame({
            'date': data.index,
            'open': data['Open'],
            'high': data['High'],
            'low': data['Low'],
            'close': data['Close'],
            'volume': data['Volume']
        }).reset_index(drop=True)
        
        return price_data

    def _test_individual_indicators(self, tech_indicators):
        """Test each indicator individually."""
        self.stdout.write('\n📋 Testing individual indicators:')
        
        indicators_to_test = [
            ('SMA (20)', lambda: tech_indicators.calculate_sma(20)),
            ('SMA (50)', lambda: tech_indicators.calculate_sma(50)),
            ('EMA (12)', lambda: tech_indicators.calculate_ema(12)),
            ('EMA (26)', lambda: tech_indicators.calculate_ema(26)),
            ('RSI (14)', lambda: tech_indicators.calculate_rsi(14)),
            ('MACD', lambda: tech_indicators.calculate_macd()),
            ('Bollinger Bands', lambda: tech_indicators.calculate_bollinger_bands()),
        ]
        
        for name, calc_func in indicators_to_test:
            try:
                result = calc_func()
                self.stdout.write(f'   ✅ {name}: {self._format_indicator_result(result)}')
            except Exception as e:
                self.stdout.write(f'   ❌ {name}: Failed - {str(e)}')

    def _format_indicator_result(self, result):
        """Format indicator result for display."""
        if 'current_value' in result:
            value = result['current_value']
            signal = result.get('signal', 'N/A')
            return f'Value: {value:.2f}, Signal: {signal}'
        elif 'macd_line' in result:  # MACD
            macd_val = result['macd_line']['current_value']
            signal_val = result['signal_line']['current_value']
            hist_val = result['histogram']['current_value']
            return f'MACD: {macd_val:.4f}, Signal: {signal_val:.4f}, Hist: {hist_val:.4f}'
        elif 'upper_band' in result:  # Bollinger Bands
            position = result['position']
            signal = result.get('signal', 'N/A')
            return f'Position: {position:.1f}%, Signal: {signal}'
        else:
            return 'Calculated successfully'

    def _display_results(self, all_indicators):
        """Display comprehensive results."""
        self.stdout.write('\n📊 TECHNICAL ANALYSIS RESULTS')
        self.stdout.write('-' * 40)
        
        # Overall signal
        overall = all_indicators.get('overall_signal', {})
        signal = overall.get('signal', 'N/A')
        confidence = overall.get('confidence', 0) * 100
        
        self.stdout.write(f'🎯 OVERALL SIGNAL: {signal} (Confidence: {confidence:.1f}%)')
        
        bullish = overall.get('bullish_signals', 0)
        bearish = overall.get('bearish_signals', 0)
        total = overall.get('total_signals', 0)
        
        self.stdout.write(f'   📈 Bullish signals: {bullish}/{total}')
        self.stdout.write(f'   📉 Bearish signals: {bearish}/{total}')
        
        # Individual indicators
        self.stdout.write('\n📋 Individual Indicators:')
        
        indicators = [
            ('SMA (20)', 'sma_20'),
            ('SMA (50)', 'sma_50'),
            ('EMA (12)', 'ema_12'),
            ('EMA (26)', 'ema_26'),
            ('RSI (14)', 'rsi_14'),
            ('MACD', 'macd'),
            ('Bollinger Bands', 'bollinger_bands')
        ]
        
        for display_name, key in indicators:
            if key in all_indicators:
                indicator = all_indicators[key]
                result_str = self._format_indicator_result(indicator)
                self.stdout.write(f'   {display_name}: {result_str}')

    def _display_complete_analysis(self, analysis):
        """Display complete analysis results."""
        self.stdout.write('\n🔍 COMPLETE ANALYSIS RESULTS')
        self.stdout.write('-' * 40)
        
        overall = analysis.get('overall', {})
        fundamental = analysis.get('fundamental', {})
        technical = analysis.get('technical', {})
        
        self.stdout.write(f'🎯 Final Recommendation: {overall.get("signal", "N/A")}')
        self.stdout.write(f'   Confidence: {overall.get("confidence", 0) * 100:.1f}%')
        self.stdout.write(f'   Fundamental: {overall.get("fundamental_signal", "N/A")}')
        self.stdout.write(f'   Technical: {overall.get("technical_signal", "N/A")}')
        
        if 'explanation' in overall:
            self.stdout.write(f'   Explanation: {overall["explanation"]}')

    def _save_to_database(self, symbol, indicators):
        """Save indicators to database."""
        try:
            # Get or create sector first
            sector, created = Sector.objects.get_or_create(
                name='Technology',
                defaults={
                    'code': 'TECH',
                    'etf_symbol': 'XLK',
                    'volatility_threshold': 0.35
                }
            )
            
            # Get or create stock
            stock, created = Stock.objects.get_or_create(
                symbol=symbol,
                defaults={
                    'name': f'{symbol} Corporation',
                    'sector': sector,
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(f'   Created stock record for {symbol}')
            
            # Save indicators
            saved_count = 0
            for indicator_name, indicator_data in indicators.items():
                if indicator_name == 'overall_signal':
                    continue
                
                # Map to model types
                type_mapping = {
                    'sma_20': ('SMA', 20), 'sma_50': ('SMA', 50),
                    'ema_12': ('EMA', 12), 'ema_26': ('EMA', 26),
                    'rsi_14': ('RSI', 14), 'macd': ('MACD', None),
                    'bollinger_bands': ('BOLLINGER', 20)
                }
                
                if indicator_name not in type_mapping:
                    continue
                    
                indicator_type, period = type_mapping[indicator_name]
                
                # Create the technical indicator
                TechnicalIndicator.objects.create(
                    stock=stock,
                    indicator_type=indicator_type,
                    calculation_date=timezone.now(),
                    period=period,
                    current_value=indicator_data.get('current_value'),
                    signal=indicator_data.get('signal', 'NEUTRAL'),
                    confidence=0.8,
                    data=indicator_data
                )
                saved_count += 1
            
            self.stdout.write(f'   💾 Saved {saved_count} indicators to database')
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠️  Database save failed: {e}'))

    def _test_caching(self, tech_indicators):
        """Test caching functionality."""
        self.stdout.write('\n⚡ Testing caching performance:')
        
        import time
        
        # First calculation (should cache)
        start_time = time.time()
        result1 = tech_indicators.calculate_sma(20)
        first_time = time.time() - start_time
        
        # Second calculation (should use cache)
        start_time = time.time()
        result2 = tech_indicators.calculate_sma(20)
        second_time = time.time() - start_time
        
        self.stdout.write(f'   First calculation: {first_time:.3f}s')
        self.stdout.write(f'   Second calculation: {second_time:.3f}s')
        
        if second_time < first_time:
            speedup = first_time / second_time
            self.stdout.write(f'   ⚡ Cache speedup: {speedup:.1f}x faster')
        
        # Verify results are identical
        if result1['current_value'] == result2['current_value']:
            self.stdout.write('   ✅ Cache consistency verified')
        else:
            self.stdout.write('   ❌ Cache consistency failed')

    def _get_cache_stats(self):
        """Get cache statistics."""
        try:
            # This would depend on your cache backend
            return {
                'status': 'healthy',
                'backend': 'redis' if 'redis' in str(cache.__class__).lower() else 'other'
            }
        except:
            return {'status': 'unknown', 'backend': 'unknown'}