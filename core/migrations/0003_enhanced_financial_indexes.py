# Generated manually for enhanced financial query performance

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_initial'),
    ]

    operations = [
        # Composite indexes for financial time-series queries
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stock_sector_active ON mapletrade_stocks(sector_id, is_active) WHERE is_active = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_stock_sector_active;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stock_price_updated ON mapletrade_stocks(current_price, last_updated) WHERE current_price IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_stock_price_updated;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stock_target_spread ON mapletrade_stocks(target_price, current_price) WHERE target_price IS NOT NULL AND current_price IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_stock_target_spread;"
        ),
        
        # Portfolio analysis indexes
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_portfolio_stock_added ON mapletrade_portfolio_stocks(portfolio_id, added_date);",
            reverse_sql="DROP INDEX IF EXISTS idx_portfolio_stock_added;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_portfolio_user_default ON mapletrade_portfolios(user_id, is_default);",
            reverse_sql="DROP INDEX IF EXISTS idx_portfolio_user_default;"
        ),
        
        # Sector analysis indexes
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sector_etf_threshold ON mapletrade_sectors(etf_symbol, volatility_threshold);",
            reverse_sql="DROP INDEX IF EXISTS idx_sector_etf_threshold;"
        ),
    ]