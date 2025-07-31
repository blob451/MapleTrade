"""
Test analytics using cached stock data to avoid rate limits.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta

from core.models import Stock
from analytics.services import AnalyticsEngine


class Command(BaseCommand):
    help = 'Test analytics using cached stock data'
    
    def handle(self, *args, **options):
        # Get stocks that have data
        stocks = Stock.objects.filter(
            current_price__isnull=False,
            sector__isnull=False
        ).order_by('-last_updated')[:5]  # Get 5 most recently updated
        
        if not stocks:
            self.stdout.write(self.style.ERROR("No stocks with data found in database"))
            return
        
        self.stdout.write(f"\nFound {stocks.count()} stocks with data. Testing analysis...\n")
        
        engine = AnalyticsEngine()
        
        for stock in stocks:
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"Analyzing {stock.symbol} - {stock.name}")
            self.stdout.write(f"Last updated: {stock.last_updated}")
            
            try:
                result = engine.analyze_stock(stock.symbol, months=6)
                
                self.stdout.write(f"\nRecommendation: {self.style.SUCCESS(result.recommendation)}")
                self.stdout.write(f"Confidence: {result.confidence:.2%}")
                
                # Display signals
                self.stdout.write("\nSignals:")
                for name, signal in result.signals.items():
                    status = "✓" if signal['value'] else "✗"
                    style = self.style.SUCCESS if signal['value'] else self.style.ERROR
                    self.stdout.write(f"  {status} {name}")
                
                # Display key metrics
                self.stdout.write("\nKey Metrics:")
                for key in ['stock_return', 'etf_return', 'volatility', 'target_price', 'current_price']:
                    if key in result.metrics:
                        self.stdout.write(f"  {key}: {result.metrics[key]}")
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error: {e}"))
            
            # Add delay between analyses
            import time
            time.sleep(3)