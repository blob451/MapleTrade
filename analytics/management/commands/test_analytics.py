"""
Management command to test the analytics engine.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta

from analytics.services import AnalyticsEngine


class Command(BaseCommand):
    help = 'Test the analytics engine with a stock symbol'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'symbol',
            type=str,
            help='Stock symbol to analyze (e.g., AAPL, MSFT, NVDA)'
        )
        parser.add_argument(
            '--months',
            type=int,
            default=6,
            help='Number of months to analyze (default: 6)'
        )
    
    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        months = options['months']
        
        self.stdout.write(f"\nAnalyzing {symbol} over {months} months...\n")
        
        # Create engine and run analysis
        engine = AnalyticsEngine()
        result = engine.analyze_stock(symbol, months)
        
        # Display results
        self.stdout.write(f"Symbol: {result.symbol}")
        self.stdout.write(f"Recommendation: {self.style.SUCCESS(result.recommendation)}")
        self.stdout.write(f"Confidence: {result.confidence:.2%}")
        self.stdout.write(f"Timestamp: {result.timestamp}")
        
        # Display signals
        self.stdout.write("\nSignals:")
        for name, signal in result.signals.items():
            status = "✓" if signal['value'] else "✗"
            self.stdout.write(f"  {status} {name}: {signal['value']}")
        
        # Display metrics
        self.stdout.write("\nMetrics:")
        for name, value in result.metrics.items():
            self.stdout.write(f"  {name}: {value}")
        
        # Display errors if any
        if result.errors:
            self.stdout.write(self.style.ERROR("\nErrors:"))
            for error in result.errors:
                self.stdout.write(f"  - {error}")