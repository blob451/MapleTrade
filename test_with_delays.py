# test_with_delays.py
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mapletrade.settings')
django.setup()

# Now import Django modules
from analytics.services import StockAnalyzer
from users.models import User
import time

print("=== MapleTrade Test with Delays ===\n")

user = User.objects.first()
if not user:
    print("No user found. Creating test user...")
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.create_user('testuser', 'test@example.com', 'password')

analyzer = StockAnalyzer()

# Test with significant delays
stocks = ['AAPL', 'MSFT']
for symbol in stocks:
    print(f"\nAnalyzing {symbol}...")
    try:
        result = analyzer.analyze_stock(symbol, user, analysis_months=3)
        print(f"✓ {symbol}: {result.signal} (confidence: {result.confidence_score})")
        print(f"  Stock return: {result.stock_return:.2%}")
        print(f"  Sector return: {result.sector_return:.2%}")
        print(f"  Volatility: {result.volatility:.2%}")
    except Exception as e:
        print(f"✗ {symbol}: {e}")
        import traceback
        traceback.print_exc()
    
    # Wait 30 seconds between requests to avoid rate limiting
    if symbol != stocks[-1]:
        print("\nWaiting 30 seconds to avoid rate limit...")
        for i in range(30, 0, -1):
            print(f"\r{i} seconds remaining...", end='', flush=True)
            time.sleep(1)
        print("\r                        ", end='\r')  # Clear the line

print("\n\n✓ Test complete!")