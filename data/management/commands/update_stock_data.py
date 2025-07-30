"""
Django management command to update stock data from external sources.

This command fetches and updates stock information and price data
using the configured data providers.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, timedelta
from typing import List, Optional

from core.models import Stock, Sector
from data.providers import YahooFinanceProvider, DataProviderError
from data.validators import DataValidator


class Command(BaseCommand):
    help = 'Update stock data from external sources'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--symbols',
            type=str,
            help='Comma-separated list of stock symbols to update (e.g., AAPL,MSFT,GOOGL)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Update all stocks in the database'
        )
        parser.add_argument(
            '--create-missing',
            action='store_true',
            help='Create stock records if they don\'t exist'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days of historical data to fetch (default: 30)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even if recently updated'
        )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.provider = YahooFinanceProvider()
        self.validator = DataValidator()
    
    def handle(self, *args, **options):
        """Main command handler."""
        self.stdout.write(
            self.style.SUCCESS('Starting stock data update...')
        )
        
        # Determine which stocks to update
        if options['symbols']:
            symbols = [s.strip().upper() for s in options['symbols'].split(',')]
            stocks_to_update = self._get_stocks_by_symbols(symbols, options['create_missing'])
        elif options['all']:
            stocks_to_update = Stock.objects.filter(is_active=True)
            symbols = [stock.symbol for stock in stocks_to_update]
        else:
            # Update stocks that haven't been updated recently
            cutoff_time = timezone.now() - timedelta(hours=1)
            stocks_to_update = Stock.objects.filter(
                is_active=True,
                last_updated__lt=cutoff_time
            ) | Stock.objects.filter(last_updated__isnull=True)
            symbols = [stock.symbol for stock in stocks_to_update]
        
        if not symbols:
            self.stdout.write(
                self.style.WARNING('No stocks to update.')
            )
            return
        
        self.stdout.write(f'Updating {len(symbols)} stocks: {", ".join(symbols)}')
        
        # Update stocks
        success_count = 0
        error_count = 0
        
        for stock in stocks_to_update:
            try:
                if options['force'] or self._needs_update(stock):
                    self._update_stock(stock, options['days'])
                    success_count += 1
                    self.stdout.write(f'✓ Updated {stock.symbol}')
                else:
                    self.stdout.write(f'- Skipped {stock.symbol} (recently updated)')
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to update {stock.symbol}: {e}')
                )
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nUpdate complete: {success_count} successful, {error_count} errors'
            )
        )
    
    def _get_stocks_by_symbols(self, symbols: List[str], create_missing: bool) -> List[Stock]:
        """Get stock objects for given symbols, optionally creating missing ones."""
        stocks = []
        
        for symbol in symbols:
            try:
                stock = Stock.objects.get(symbol=symbol)
                stocks.append(stock)
            except Stock.DoesNotExist:
                if create_missing:
                    stock = self._create_stock_from_symbol(symbol)
                    if stock:
                        stocks.append(stock)
                        self.stdout.write(f'Created new stock record for {symbol}')
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Stock {symbol} not found in database')
                    )
        
        return stocks
    
    def _create_stock_from_symbol(self, symbol: str) -> Optional[Stock]:
        """Create a new stock record from symbol using external data."""
        try:
            stock_info = self.provider.get_stock_info(symbol)
            validated_info = self.validator.validate_stock_info(stock_info)
            
            # Get or create sector
            sector = None
            if validated_info.sector:
                sector, created = Sector.objects.get_or_create(
                    name=validated_info.sector,
                    defaults={
                        'code': validated_info.sector.upper()[:10],
                        'etf_symbol': self.provider.get_sector_etf_mapping().get(
                            validated_info.sector, 'SPY'
                        )
                    }
                )
            
            # Create stock
            stock = Stock.objects.create(
                symbol=validated_info.symbol,
                name=validated_info.name or symbol,
                sector=sector,
                exchange=validated_info.exchange,
                currency=validated_info.currency,
                market_cap=validated_info.market_cap,
                current_price=validated_info.current_price,
                target_price=validated_info.target_price,
                is_active=True,
                last_updated=timezone.now()
            )
            
            return stock
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to create stock for {symbol}: {e}')
            )
            return None
    
    def _needs_update(self, stock: Stock) -> bool:
        """Check if stock needs updating."""
        if not stock.last_updated:
            return True
        
        # Update if last updated more than 1 hour ago
        return (timezone.now() - stock.last_updated).total_seconds() > 3600
    
    def _update_stock(self, stock: Stock, days: int):
        """Update a single stock's data."""
        # Get current stock info
        stock_info = self.provider.get_stock_info(stock.symbol)
        validated_info = self.validator.validate_stock_info(stock_info)
        
        # Update stock fields
        stock.name = validated_info.name or stock.name
        stock.current_price = validated_info.current_price
        stock.target_price = validated_info.target_price
        stock.market_cap = validated_info.market_cap
        stock.last_updated = timezone.now()
        
        # Update sector if needed
        if validated_info.sector and (not stock.sector or stock.sector.name != validated_info.sector):
            sector, created = Sector.objects.get_or_create(
                name=validated_info.sector,
                defaults={
                    'code': validated_info.sector.upper()[:10],
                    'etf_symbol': self.provider.get_sector_etf_mapping().get(
                        validated_info.sector, 'SPY'
                    )
                }
            )
            stock.sector = sector
        
        stock.save()