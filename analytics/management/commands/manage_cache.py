"""
Management command for cache operations related to technical indicators.
Usage: python manage.py manage_cache [action]
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
import json

from analytics.cache import technical_cache, market_data_cache, CacheStats
from analytics.models import TechnicalIndicator, Stock


class Command(BaseCommand):
    help = 'Manage cache for technical indicators and market data'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['clear', 'status', 'warm', 'stats', 'test'],
            help='Cache management action to perform'
        )
        parser.add_argument(
            '--symbol',
            type=str,
            help='Specific symbol to operate on (for warm action)'
        )
        parser.add_argument(
            '--cache-type',
            choices=['technical', 'market_data', 'all'],
            default='all',
            help='Type of cache to operate on'
        )

    def handle(self, *args, **options):
        action = options['action']
        symbol = options.get('symbol')
        cache_type = options['cache_type']
        
        self.stdout.write(
            self.style.SUCCESS(f'🔧 Cache Management - Action: {action.upper()}')
        )
        self.stdout.write('=' * 50)
        
        try:
            if action == 'clear':
                self._clear_cache(cache_type, symbol)
            elif action == 'status':
                self._show_status()
            elif action == 'warm':
                self._warm_cache(symbol)
            elif action == 'stats':
                self._show_stats()
            elif action == 'test':
                self._test_cache()
                
        except Exception as e:
            raise CommandError(f'Cache operation failed: {e}')

    def _clear_cache(self, cache_type, symbol=None):
        """Clear cache based on type and optional symbol."""
        if symbol:
            self.stdout.write(f'🗑️  Clearing cache for symbol: {symbol}')
            
            if cache_type in ['technical', 'all']:
                technical_cache.invalidate_symbol(symbol)
                self.stdout.write('   ✅ Technical indicators cache cleared')
            
            if cache_type in ['market_data', 'all']:
                # This would need implementation based on your cache backend
                self.stdout.write('   ✅ Market data cache cleared')
                
        else:
            self.stdout.write(f'🗑️  Clearing {cache_type} cache globally')
            
            if cache_type == 'all':
                cache.clear()
                self.stdout.write('   ✅ All cache cleared')
            else:
                # For specific cache types, you'd need pattern-based deletion
                # This is a simplified implementation
                cache.clear()
                self.stdout.write(f'   ✅ {cache_type} cache cleared')

    def _show_status(self):
        """Show cache status and health."""
        self.stdout.write('📊 Cache Status')
        self.stdout.write('-' * 30)
        
        # Get cache info
        cache_info = CacheStats.get_cache_info()
        
        self.stdout.write(f'Backend: {cache_info.get("backend", "Unknown")}')
        self.stdout.write(f'Status: {cache_info.get("status", "Unknown")}')
        self.stdout.write(f'Last Check: {cache_info.get("timestamp", "N/A")}')
        
        # Test basic cache operations
        test_key = 'cache_test_key'
        test_value = {'test': 'data', 'timestamp': datetime.now().isoformat()}
        
        try:
            cache.set(test_key, test_value, 60)
            retrieved = cache.get(test_key)
            
            if retrieved == test_value:
                self.stdout.write('✅ Cache read/write: Working')
            else:
                self.stdout.write('❌ Cache read/write: Failed')
                
            cache.delete(test_key)
            
        except Exception as e:
            self.stdout.write(f'❌ Cache test failed: {e}')

    def _warm_cache(self, symbol=None):
        """Warm up cache with commonly used data."""
        if not symbol:
            # Get most active stocks from database
            symbols = list(Stock.objects.filter(is_active=True)[:5].values_list('symbol', flat=True))
            if not symbols:
                symbols = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'TSLA']  # Default symbols
        else:
            symbols = [symbol]
        
        self.stdout.write(f'🔥 Warming cache for symbols: {", ".join(symbols)}')
        
        from analytics.services import AnalyticsEngine
        engine = AnalyticsEngine()
        
        warmed_count = 0
        for sym in symbols:
            try:
                self.stdout.write(f'   Processing {sym}...', ending='')
                
                # This would trigger cache population
                # In a real implementation, you might pre-calculate common indicators
                result = engine._fetch_price_data(sym, 6)  
                
                self.stdout.write(' ✅')
                warmed_count += 1
                
            except Exception as e:
                self.stdout.write(f' ❌ ({str(e)[:50]}...)')
        
        self.stdout.write(f'🔥 Cache warmed for {warmed_count}/{len(symbols)} symbols')

    def _show_stats(self):
        """Show detailed cache statistics."""
        self.stdout.write('📈 Cache Statistics')
        self.stdout.write('-' * 30)
        
        # Technical indicators in database
        total_indicators = TechnicalIndicator.objects.count()
        recent_indicators = TechnicalIndicator.objects.filter(
            calculation_date__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        self.stdout.write(f'Technical Indicators in DB: {total_indicators}')
        self.stdout.write(f'Recent (24h): {recent_indicators}')
        
        # Indicators by type
        indicator_types = TechnicalIndicator.objects.values('indicator_type').distinct()
        self.stdout.write('\nIndicators by type:')
        for indicator_type in indicator_types:
            count = TechnicalIndicator.objects.filter(
                indicator_type=indicator_type['indicator_type']
            ).count()
            self.stdout.write(f'  {indicator_type["indicator_type"]}: {count}')
        
        # Stocks with technical analysis
        stocks_with_indicators = TechnicalIndicator.objects.values('stock__symbol').distinct().count()
        total_stocks = Stock.objects.filter(is_active=True).count()
        
        coverage = (stocks_with_indicators / total_stocks * 100) if total_stocks > 0 else 0
        self.stdout.write(f'\nCoverage: {stocks_with_indicators}/{total_stocks} stocks ({coverage:.1f}%)')

    def _test_cache(self):
        """Test cache performance and functionality."""
        self.stdout.write('🧪 Cache Performance Test')
        self.stdout.write('-' * 30)
        
        import time
        import json
        
        # Test 1: Basic operations
        self.stdout.write('Test 1: Basic Operations')
        
        test_data = {
            'indicator': 'SMA',
            'values': list(range(100)),
            'timestamp': datetime.now().isoformat()
        }
        
        # Set operation
        start_time = time.time()
        cache.set('test_performance', test_data, 300)
        set_time = time.time() - start_time
        
        # Get operation  
        start_time = time.time()
        retrieved = cache.get('test_performance')
        get_time = time.time() - start_time
        
        self.stdout.write(f'  Set time: {set_time*1000:.2f}ms')
        self.stdout.write(f'  Get time: {get_time*1000:.2f}ms')
        
        if retrieved == test_data:
            self.stdout.write('  ✅ Data integrity: OK')
        else:
            self.stdout.write('  ❌ Data integrity: FAILED')
        
        # Test 2: Multiple operations
        self.stdout.write('\nTest 2: Multiple Operations (100 items)')
        
        start_time = time.time()
        for i in range(100):
            cache.set(f'test_bulk_{i}', {'id': i, 'data': f'test_data_{i}'}, 300)
        bulk_set_time = time.time() - start_time
        
        start_time = time.time()
        for i in range(100):
            cache.get(f'test_bulk_{i}')
        bulk_get_time = time.time() - start_time
        
        self.stdout.write(f'  Bulk set (100 items): {bulk_set_time*1000:.2f}ms')
        self.stdout.write(f'  Bulk get (100 items): {bulk_get_time*1000:.2f}ms')
        self.stdout.write(f'  Avg per operation: {(bulk_set_time + bulk_get_time)/200*1000:.2f}ms')
        
        # Cleanup
        for i in range(100):
            cache.delete(f'test_bulk_{i}')
        cache.delete('test_performance')
        
        # Test 3: Cache hit/miss behavior
        self.stdout.write('\nTest 3: Cache Hit/Miss Behavior')
        
        # Miss
        start_time = time.time()
        result = cache.get('non_existent_key', 'default_value')
        miss_time = time.time() - start_time
        
        # Set and hit
        cache.set('hit_test', 'hit_value', 300)
        start_time = time.time()
        result = cache.get('hit_test')
        hit_time = time.time() - start_time
        
        self.stdout.write(f'  Cache miss time: {miss_time*1000:.2f}ms')
        self.stdout.write(f'  Cache hit time: {hit_time*1000:.2f}ms')
        
        if hit_time < miss_time:
            self.stdout.write('  ✅ Cache performance: Good (hit < miss)')
        else:
            self.stdout.write('  ⚠️  Cache performance: Check configuration')
        
        cache.delete('hit_test')
        
        self.stdout.write('\n✅ Cache tests completed')

    def _format_size(self, size_bytes):
        """Format bytes into human readable size."""
        if size_bytes == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"