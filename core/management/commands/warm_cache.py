"""
Django management command for warming cache with popular stock data.

This command pre-loads frequently accessed data into cache to improve
performance for common user requests.
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from datetime import datetime
import logging

from core.cache import CacheWarmer, CacheManager
from core.models import Stock, Sector

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Warm cache with popular stock data and sector ETFs'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--stocks',
            type=str,
            help='Comma-separated list of stock symbols to warm (e.g., AAPL,MSFT,GOOGL)'
        )
        parser.add_argument(
            '--popular',
            action='store_true',
            help='Warm cache for popular stocks (predefined list)'
        )
        parser.add_argument(
            '--sectors',
            action='store_true',
            help='Warm cache for sector ETFs'
        )
        parser.add_argument(
            '--user-stocks',
            action='store_true',
            help='Warm cache for stocks in user portfolios'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Warm cache for all categories (popular, sectors, user stocks)'
        )
        parser.add_argument(
            '--clear-first',
            action='store_true',
            help='Clear existing market data cache before warming'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be warmed without actually doing it'
        )
    
    def handle(self, *args, **options):
        """Main command handler."""
        start_time = datetime.now()
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting cache warming at {start_time}...')
        )
        
        # Check if cache warming is enabled
        warming_enabled = getattr(settings, 'MAPLETRADE_SETTINGS', {}).get('CACHE_WARMING_ENABLED', True)
        if not warming_enabled and not options['dry_run']:
            self.stdout.write(
                self.style.WARNING('Cache warming is disabled in settings. Use --dry-run to test.')
            )
            return
        
        # Clear cache if requested
        if options['clear_first'] and not options['dry_run']:
            self.stdout.write('Clearing existing market data cache...')
            CacheManager.clear_cache(CacheManager.MARKET_DATA)
        
        total_warmed = 0
        total_failed = 0
        
        # Determine what to warm
        if options['all']:
            options['popular'] = True
            options['sectors'] = True
            options['user_stocks'] = True
        
        # Warm specific stocks
        if options['stocks']:
            symbols = [s.strip().upper() for s in options['stocks'].split(',')]
            total_warmed, total_failed = self._warm_stock_list(
                symbols, 'Custom stocks', options['dry_run'], total_warmed, total_failed
            )
        
        # Warm popular stocks
        if options['popular']:
            popular_stocks = CacheWarmer.get_popular_stocks()
            total_warmed, total_failed = self._warm_stock_list(
                popular_stocks, 'Popular stocks', options['dry_run'], total_warmed, total_failed
            )
        
        # Warm sector ETFs
        if options['sectors']:
            total_warmed, total_failed = self._warm_sectors(
                options['dry_run'], total_warmed, total_failed
            )
        
        # Warm user portfolio stocks
        if options['user_stocks']:
            total_warmed, total_failed = self._warm_user_stocks(
                options['dry_run'], total_warmed, total_failed
            )
        
        # Default behavior if no specific options
        if not any([options['stocks'], options['popular'], options['sectors'], 
                   options['user_stocks'], options['all']]):
            self.stdout.write('No warming options specified. Warming popular stocks by default...')
            popular_stocks = CacheWarmer.get_popular_stocks()
            total_warmed, total_failed = self._warm_stock_list(
                popular_stocks, 'Popular stocks (default)', options['dry_run'], total_warmed, total_failed
            )
        
        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCache warming completed in {duration:.2f} seconds'
            )
        )
        self.stdout.write(f'Total items warmed: {total_warmed}')
        if total_failed > 0:
            self.stdout.write(
                self.style.WARNING(f'Total failures: {total_failed}')
            )
        
        # Show cache stats
        self._show_cache_stats()
    
    def _warm_stock_list(self, symbols, category_name, dry_run, total_warmed, total_failed):
        """Warm cache for a list of stock symbols."""
        self.stdout.write(f'\n{category_name}: {len(symbols)} symbols')
        
        if dry_run:
            self.stdout.write(f'Would warm: {", ".join(symbols)}')
            return total_warmed, total_failed
        
        results = CacheWarmer.warm_popular_stocks(symbols)
        
        successful = sum(1 for success in results.values() if success)
        failed = len(results) - successful
        
        self.stdout.write(f'✓ Successfully warmed: {successful}')
        if failed > 0:
            self.stdout.write(f'✗ Failed to warm: {failed}')
            failed_symbols = [symbol for symbol, success in results.items() if not success]
            self.stdout.write(f'  Failed symbols: {", ".join(failed_symbols)}')
        
        return total_warmed + successful, total_failed + failed
    
    def _warm_sectors(self, dry_run, total_warmed, total_failed):
        """Warm cache for sector ETFs."""
        sectors = Sector.objects.all()
        etf_symbols = [sector.etf_symbol for sector in sectors]
        
        self.stdout.write(f'\nSector ETFs: {len(etf_symbols)} symbols')
        
        if dry_run:
            self.stdout.write(f'Would warm ETFs: {", ".join(etf_symbols)}')
            return total_warmed, total_failed
        
        results = CacheWarmer.warm_sector_etfs()
        
        successful = sum(1 for success in results.values() if success)
        failed = len(results) - successful
        
        self.stdout.write(f'✓ Successfully warmed ETFs: {successful}')
        if failed > 0:
            self.stdout.write(f'✗ Failed to warm ETFs: {failed}')
            failed_etfs = [etf for etf, success in results.items() if not success]
            self.stdout.write(f'  Failed ETFs: {", ".join(failed_etfs)}')
        
        return total_warmed + successful, total_failed + failed
    
    def _warm_user_stocks(self, dry_run, total_warmed, total_failed):
        """Warm cache for stocks in user portfolios."""
        # Get unique stocks from all user portfolios
        user_stocks = Stock.objects.filter(
            portfoliostock__isnull=False
        ).distinct().values_list('symbol', flat=True)
        
        user_stock_symbols = list(user_stocks)
        
        self.stdout.write(f'\nUser portfolio stocks: {len(user_stock_symbols)} symbols')
        
        if not user_stock_symbols:
            self.stdout.write('No stocks found in user portfolios')
            return total_warmed, total_failed
        
        if dry_run:
            self.stdout.write(f'Would warm user stocks: {", ".join(user_stock_symbols)}')
            return total_warmed, total_failed
        
        results = CacheWarmer.warm_popular_stocks(user_stock_symbols)
        
        successful = sum(1 for success in results.values() if success)
        failed = len(results) - successful
        
        self.stdout.write(f'✓ Successfully warmed user stocks: {successful}')
        if failed > 0:
            self.stdout.write(f'✗ Failed to warm user stocks: {failed}')
        
        return total_warmed + successful, total_failed + failed
    
    def _show_cache_stats(self):
        """Display current cache statistics."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write('Cache Statistics:')
        self.stdout.write('='*50)
        
        stats = CacheManager.get_cache_stats()
        
        for cache_type, cache_stats in stats.items():
            self.stdout.write(f'\n{cache_type.upper()} Cache:')
            for key, value in cache_stats.items():
                self.stdout.write(f'  {key}: {value}')
        
        self.stdout.write('\nCache warming complete!')