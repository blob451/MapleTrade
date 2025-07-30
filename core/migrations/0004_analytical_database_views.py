# Database views for complex analytical queries

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_enhanced_financial_indexes'),
    ]

    operations = [
        # View for active stocks with sector information
        migrations.RunSQL(
            """
            CREATE OR REPLACE VIEW vw_active_stocks_with_sectors AS
            SELECT 
                s.id,
                s.symbol,
                s.name,
                s.current_price,
                s.target_price,
                s.market_cap,
                s.last_updated,
                sec.name as sector_name,
                sec.code as sector_code,
                sec.etf_symbol,
                sec.volatility_threshold,
                CASE 
                    WHEN s.target_price IS NOT NULL AND s.current_price IS NOT NULL 
                    THEN (s.target_price - s.current_price) / s.current_price * 100
                    ELSE NULL 
                END as target_upside_percent
            FROM mapletrade_stocks s
            LEFT JOIN mapletrade_sectors sec ON s.sector_id = sec.id
            WHERE s.is_active = true;
            """,
            reverse_sql="DROP VIEW IF EXISTS vw_active_stocks_with_sectors;"
        ),
        
        # View for sector performance summary
        migrations.RunSQL(
            """
            CREATE OR REPLACE VIEW vw_sector_summary AS
            SELECT 
                sec.id,
                sec.name as sector_name,
                sec.code as sector_code,
                sec.etf_symbol,
                sec.volatility_threshold,
                COUNT(s.id) as total_stocks,
                COUNT(CASE WHEN s.current_price IS NOT NULL THEN 1 END) as stocks_with_price,
                COUNT(CASE WHEN s.target_price IS NOT NULL THEN 1 END) as stocks_with_target,
                AVG(s.current_price) as avg_current_price,
                AVG(s.target_price) as avg_target_price,
                AVG(s.market_cap) as avg_market_cap,
                MIN(s.last_updated) as oldest_update,
                MAX(s.last_updated) as newest_update
            FROM mapletrade_sectors sec
            LEFT JOIN mapletrade_stocks s ON sec.id = s.sector_id AND s.is_active = true
            GROUP BY sec.id, sec.name, sec.code, sec.etf_symbol, sec.volatility_threshold;
            """,
            reverse_sql="DROP VIEW IF EXISTS vw_sector_summary;"
        ),
        
        # View for portfolio analysis
        migrations.RunSQL(
            """
            CREATE OR REPLACE VIEW vw_portfolio_analysis AS
            SELECT 
                p.id as portfolio_id,
                p.name as portfolio_name,
                p.user_id,
                COUNT(ps.stock_id) as total_stocks,
                COUNT(DISTINCT s.sector_id) as unique_sectors,
                AVG(s.current_price) as avg_stock_price,
                SUM(s.market_cap) as total_market_cap,
                AVG(CASE 
                    WHEN s.target_price IS NOT NULL AND s.current_price IS NOT NULL 
                    THEN (s.target_price - s.current_price) / s.current_price * 100
                    ELSE NULL 
                END) as avg_target_upside_percent,
                MIN(ps.added_date) as first_stock_added,
                MAX(ps.added_date) as last_stock_added
            FROM mapletrade_portfolios p
            LEFT JOIN mapletrade_portfolio_stocks ps ON p.id = ps.portfolio_id
            LEFT JOIN mapletrade_stocks s ON ps.stock_id = s.id AND s.is_active = true
            GROUP BY p.id, p.name, p.user_id;
            """,
            reverse_sql="DROP VIEW IF EXISTS vw_portfolio_analysis;"
        ),
        
        # View for stocks needing data updates
        migrations.RunSQL(
            """
            CREATE OR REPLACE VIEW vw_stocks_needing_update AS
            SELECT 
                s.id,
                s.symbol,
                s.name,
                s.last_updated,
                CASE 
                    WHEN s.last_updated IS NULL THEN 'Never updated'
                    WHEN s.last_updated < NOW() - INTERVAL '1 hour' THEN 'Stale data'
                    WHEN s.current_price IS NULL THEN 'Missing price'
                    WHEN s.target_price IS NULL THEN 'Missing target'
                    ELSE 'Up to date'
                END as update_status,
                EXTRACT(EPOCH FROM (NOW() - s.last_updated))/3600 as hours_since_update
            FROM mapletrade_stocks s
            WHERE s.is_active = true
            ORDER BY s.last_updated ASC NULLS FIRST;
            """,
            reverse_sql="DROP VIEW IF EXISTS vw_stocks_needing_update;"
        ),
    ]