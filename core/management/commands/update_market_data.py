"""
Management command to update market data using the orchestrator.

Usage:
    python manage.py update_market_data
    python manage.py update_market_data --symbols AAPL,MSFT,GOOGL
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.services import get_orchestrator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update market data for stocks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbols',
            type=str,
            help='Comma-separated list of symbols to update',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Update all active stocks',
        )
        parser.add_argument(
            '--stale-hours',
            type=int,
            default=24,
            help='Consider data stale after this many hours',
        )

    def handle(self, *args, **options):
        orchestrator = get_orchestrator()
        
        self.stdout.write('Starting market data update...')
        
        try:
            if options['symbols']:
                # Update specific symbols
                symbols = options['symbols'].split(',')
                symbols = [s.strip().upper() for s in symbols]
                
                self.stdout.write(f'Updating {len(symbols)} stocks: {", ".join(symbols)}')
                
            elif options['all']:
                # Update all stale stocks
                stale_hours = options['stale_hours']
                stocks = orchestrator.stock_service.get_stocks_needing_update(hours=stale_hours)
                symbols = [s.symbol for s in stocks]
                
                self.stdout.write(f'Found {len(symbols)} stocks needing update')
                
            else:
                # Default: update common stocks
                symbols = ['SPY', 'QQQ', 'DIA', 'IWM', 'AAPL', 'MSFT', 'GOOGL', 'AMZN']
                self.stdout.write(f'Updating default stocks: {", ".join(symbols)}')
            
            # Perform update
            results = orchestrator.batch_update_prices(symbols)
            
            # Report results
            self.stdout.write(self.style.SUCCESS(
                f"\nUpdate complete:"
                f"\n  Updated: {len(results['updated'])}"
                f"\n  Created: {len(results['created'])}"
                f"\n  Failed: {len(results['failed'])}"
            ))
            
            if results['failed']:
                self.stdout.write(self.style.ERROR("\nFailed updates:"))
                for failure in results['failed']:
                    self.stdout.write(f"  {failure['symbol']}: {failure['error']}")
            
            # Update sectors
            self.stdout.write("\nUpdating sector ETFs...")
            sectors = orchestrator.sector_service.get_all_sectors()
            sector_symbols = [s.etf_symbol for s in sectors]
            
            sector_results = orchestrator.batch_update_prices(sector_symbols)
            
            self.stdout.write(self.style.SUCCESS(
                f"Sector update complete: {len(sector_results['updated'])} updated"
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
            logger.error(f"Market data update failed: {e}")
            raise