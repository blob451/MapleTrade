#!/usr/bin/env python
"""
Quick test script to verify database optimization is working correctly.
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mapletrade.settings')
django.setup()

from django.db import connection
from core.models import Stock, Sector, UserPortfolio
from users.models import User

def test_database_setup():
    """Test that all database optimizations are working."""
    
    print("🔍 Testing MapleTrade Database Setup...")
    print("=" * 50)
    
    # Test 1: Basic model counts
    print("\n📊 Data Counts:")
    print(f"  Users: {User.objects.count()}")
    print(f"  Sectors: {Sector.objects.count()}")
    print(f"  Stocks: {Stock.objects.count()}")
    print(f"  Portfolios: {UserPortfolio.objects.count()}")
    
    # Test 2: Index verification
    print("\n🔍 Testing Indexes...")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) as index_count 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename LIKE 'mapletrade_%'
            AND indexname LIKE 'idx_%'
        """)
        index_count = cursor.fetchone()[0]
        print(f"  Custom indexes found: {index_count}")
        
        # List the indexes
        cursor.execute("""
            SELECT indexname, tablename
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename LIKE 'mapletrade_%'
            AND indexname LIKE 'idx_%'
            ORDER BY tablename, indexname
        """)
        indexes = cursor.fetchall()
        for idx_name, table_name in indexes:
            print(f"    ✅ {idx_name} on {table_name}")
    
    # Test 3: View verification
    print("\n👁️ Testing Database Views...")
    with connection.cursor() as cursor:
        views_to_test = [
            'vw_active_stocks_with_sectors',
            'vw_sector_summary', 
            'vw_portfolio_analysis',
            'vw_stocks_needing_update',
            'vw_stock_performance_metrics',
            'vw_portfolio_performance',
            'vw_sector_analytics'
        ]
        
        for view_name in views_to_test:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {view_name}")
                count = cursor.fetchone()[0]
                print(f"  ✅ {view_name}: {count} records")
            except Exception as e:
                print(f"  ❌ {view_name}: Error - {e}")
    
    # Test 4: Performance test
    print("\n⚡ Quick Performance Test...")
    import time
    
    start_time = time.time()
    active_stocks = list(Stock.objects.filter(is_active=True).select_related('sector')[:20])
    end_time = time.time()
    
    print(f"  Fetched {len(active_stocks)} stocks with sectors in {(end_time - start_time)*1000:.2f}ms")
    
    # Test 5: Sample data verification
    print("\n📈 Sample Stock Data:")
    if active_stocks:
        for stock in active_stocks[:3]:
            sector_name = stock.sector.name if stock.sector else "No Sector"
            price = f"${stock.current_price}" if stock.current_price else "No Price"
            print(f"  {stock.symbol}: {stock.name} ({sector_name}) - {price}")
    
    # Test 6: View data samples
    print("\n📊 Testing View Data...")
    with connection.cursor() as cursor:
        # Test sector analytics view
        cursor.execute("SELECT sector_name, total_stocks FROM vw_sector_analytics ORDER BY total_stocks DESC LIMIT 3")
        sectors = cursor.fetchall()
        for sector_name, stock_count in sectors:
            print(f"  {sector_name}: {stock_count} stocks")
    
    print("\n✅ Database setup verification complete!")
    print("🚀 Ready for analytics engine implementation!")

if __name__ == "__main__":
    test_database_setup()