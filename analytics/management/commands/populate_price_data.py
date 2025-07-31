"""
Populate price data for stocks without hitting external APIs.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import random

from core.models import Stock, PriceData


class Command(BaseCommand):
    help = 'Populate sample price data for stocks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            help='Specific stock symbol to populate data for'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=180,
            help='Number of days of data to generate (default: 180)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing price data before populating'
        )
    
    def handle(self, *args, **options):
        symbol = options.get('symbol')
        days = options['days']
        clear = options.get('clear', False)
        
        if symbol:
            stocks = Stock.objects.filter(symbol__iexact=symbol)
            if not stocks.exists():
                self.stdout.write(self.style.ERROR(f"Stock {symbol} not found"))
                return
        else:
            # Get stocks with current prices
            stocks = Stock.objects.filter(
                current_price__isnull=False
            ).order_by('symbol')[:10]
        
        if not stocks:
            self.stdout.write(self.style.ERROR("No stocks found with current prices"))
            return
        
        self.stdout.write(f"Populating price data for {stocks.count()} stocks...")
        
        for stock in stocks:
            if clear:
                # Clear existing price data
                deleted_count = PriceData.objects.filter(stock=stock).delete()[0]
                if deleted_count > 0:
                    self.stdout.write(f"  Cleared {deleted_count} existing records for {stock.symbol}")
            
            self._generate_price_data(stock, days)
        
        self.stdout.write(self.style.SUCCESS("\nPrice data population complete!"))
    
    def _generate_price_data(self, stock: Stock, days: int):
        """Generate realistic price data for a stock."""
        self.stdout.write(f"\nGenerating {days} days of data for {stock.symbol}...")
        
        # Use current price as base, or default to 100
        base_price = float(stock.current_price) if stock.current_price else 100.0
        
        # Determine volatility based on sector
        if stock.sector:
            # Use sector volatility threshold as a guide
            sector_vol = float(stock.sector.volatility_threshold)
            daily_vol = sector_vol / 100 / 16  # Convert annual to daily
        else:
            daily_vol = 0.02  # Default 2% daily volatility
        
        # Calculate dates
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get existing data to avoid duplicates
        existing_dates = set(
            PriceData.objects.filter(
                stock=stock,
                date__gte=start_date,
                date__lte=end_date
            ).values_list('date', flat=True)
        )
        
        # Generate prices working backwards from current
        prices = []
        current_price = base_price
        dates_to_generate = []
        
        # Collect trading days
        current_date = end_date
        while current_date >= start_date:
            if current_date.weekday() < 5 and current_date not in existing_dates:  # Weekday and not exists
                dates_to_generate.append(current_date)
            current_date -= timedelta(days=1)
        
        # Generate prices from oldest to newest
        dates_to_generate.reverse()
        
        for date in dates_to_generate:
            # Generate daily movement
            daily_return = random.gauss(0, daily_vol)
            
            # Add slight trend based on target price
            if stock.target_price and stock.current_price:
                target_return = float((stock.target_price - stock.current_price) / stock.current_price)
                # Add small bias towards target
                daily_return += target_return / 252 * 0.5
            
            # Calculate OHLC
            open_price = current_price
            close_price = open_price * (1 + daily_return)
            
            # Intraday movement
            intraday_high = random.uniform(0, daily_vol)
            intraday_low = random.uniform(0, daily_vol)
            
            high_price = max(open_price, close_price) * (1 + intraday_high)
            low_price = min(open_price, close_price) * (1 - intraday_low)
            
            # Volume - base it on market cap if available
            if stock.market_cap:
                avg_volume = stock.market_cap / base_price / 100  # Rough estimate
                volume = int(avg_volume * random.uniform(0.5, 1.5))
            else:
                volume = random.randint(1_000_000, 50_000_000)
            
            prices.append(PriceData(
                stock=stock,
                date=date,
                open_price=Decimal(str(round(open_price, 4))),
                high_price=Decimal(str(round(high_price, 4))),
                low_price=Decimal(str(round(low_price, 4))),
                close_price=Decimal(str(round(close_price, 4))),
                adjusted_close=Decimal(str(round(close_price, 4))),
                volume=volume
            ))
            
            current_price = close_price
        
        # Bulk create
        if prices:
            PriceData.objects.bulk_create(prices, batch_size=100)
            self.stdout.write(
                self.style.SUCCESS(f"  Created {len(prices)} price records for {stock.symbol}")
            )
            
            # Update stock's current price to match most recent
            most_recent = PriceData.objects.filter(
                stock=stock
            ).order_by('-date').first()
            
            if most_recent:
                stock.current_price = most_recent.close_price
                stock.last_updated = timezone.now()
                stock.save()
                self.stdout.write(f"  Updated {stock.symbol} current price to ${most_recent.close_price}")
        else:
            self.stdout.write(f"  No new prices to generate for {stock.symbol}")