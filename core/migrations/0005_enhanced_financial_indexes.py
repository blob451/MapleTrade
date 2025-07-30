# Enhanced financial indexes migration

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_analytical_database_views'),
    ]

    operations = [
        # Additional performance indexes for financial queries
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_stock_market_cap_sector ON mapletrade_stocks(market_cap, sector_id) WHERE market_cap IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_stock_market_cap_sector;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_stock_updated_active ON mapletrade_stocks(last_updated DESC) WHERE is_active = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_stock_updated_active;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_portfolio_user_created ON mapletrade_portfolio_stocks(portfolio_id, added_date DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_portfolio_user_created;"
        ),
        
        # Partial indexes for performance optimization
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_stock_has_target ON mapletrade_stocks(symbol) WHERE target_price IS NOT NULL AND current_price IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_stock_has_target;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_user_analysis_activity ON mapletrade_users(last_analysis_date DESC) WHERE last_analysis_date IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_user_analysis_activity;"
        ),
    ]