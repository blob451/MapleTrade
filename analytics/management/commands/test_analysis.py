"""
Django management command to test stock analysis with delays.

Usage: python manage.py test_analysis
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from analytics.services import StockAnalyzer
import time

User = get_user_model()


class Command(BaseCommand):
    help = 'Test stock analysis with delays to avoid rate limiting'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--symbols',
            type=str,
            default='AAPL,MSFT',
            help='Comma-separated list of symbols to test'
        )
        parser.add_argument(
            '--delay',
            type=int,
            default=30,
            help='Delay in seconds between requests'
        )
        parser.add_argument(
            '--months',
            type=int,
            default=3,
            help='Number of months to analyze'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== MapleTrade Analysis Test ===\n'))
        
        # Get or create user
        user = User.objects.first()
        if not user:
            self.stdout.write('Creating test user...')
            user = User.objects.create_user('testuser', 'test@example.com', 'password')
        
        # Parse symbols
        symbols = [s.strip() for s in options['symbols'].split(',')]
        delay = options['delay']
        months = options['months']
        
        analyzer = StockAnalyzer()
        results = []
        
        for i, symbol in enumerate(symbols):
            self.stdout.write(f'\nAnalyzing {symbol}...')
            
            try:
                start_time = time.time()
                result = analyzer.analyze_stock(symbol, user, analysis_months=months)
                duration = time.time() - start_time
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ {symbol}: {result.signal} (confidence: {result.confidence_score:.2f})'
                    )
                )
                self.stdout.write(f'  Stock return: {result.stock_return:.2%}')
                self.stdout.write(f'  Sector return: {result.sector_return:.2%}')
                self.stdout.write(f'  Volatility: {result.volatility:.2%}')
                self.stdout.write(f'  Analysis time: {duration:.2f}s')
                
                results.append({
                    'symbol': symbol,
                    'signal': result.signal,
                    'confidence': float(result.confidence_score),
                    'success': True
                })
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ {symbol}: {str(e)}')
                )
                results.append({
                    'symbol': symbol,
                    'error': str(e),
                    'success': False
                })
            
            # Delay between requests (except for last symbol)
            if i < len(symbols) - 1 and delay > 0:
                self.stdout.write(f'\nWaiting {delay} seconds...')
                # Progress bar
                for j in range(delay):
                    progress = '=' * (j + 1) + '-' * (delay - j - 1)
                    self.stdout.write(f'\r[{progress}] {j+1}/{delay}s', ending='')
                    self.stdout.flush()
                    time.sleep(1)
                self.stdout.write('\r' + ' ' * 50 + '\r', ending='')  # Clear line
        
        # Summary
        self.stdout.write('\n\n=== Summary ===')
        success_count = sum(1 for r in results if r['success'])
        self.stdout.write(f'Successful: {success_count}/{len(symbols)}')
        
        if success_count > 0:
            buy_count = sum(1 for r in results if r.get('signal') == 'BUY')
            hold_count = sum(1 for r in results if r.get('signal') == 'HOLD')
            sell_count = sum(1 for r in results if r.get('signal') == 'SELL')
            
            self.stdout.write('\nSignal Distribution:')
            self.stdout.write(f'  BUY:  {buy_count}')
            self.stdout.write(f'  HOLD: {hold_count}')
            self.stdout.write(f'  SELL: {sell_count}')
        
        self.stdout.write(
            self.style.SUCCESS('\n✓ Test complete!')
        )