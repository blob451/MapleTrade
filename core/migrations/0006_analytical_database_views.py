# Enhanced analytical database views migration

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_enhanced_financial_indexes'),
    ]

    operations = [
        # Enhanced view for stock performance analysis
        migrations.RunSQL(
            """
            CREATE OR REPLACE VIEW vw_stock_performance_metrics AS
            SELECT 
                s.id,
                s.symbol,
                s.name,
                s.current_price,
                s.target_price,
                s.market_cap,
                s.last_updated,
                sec.name as sector_name,
                sec.volatility_threshold,
                CASE 
                    WHEN s.target_price IS NOT NULL AND s.current_price IS NOT NULL 
                    THEN ROUND(((s.target_price - s.current_price) / s.current_price * 100)::numeric, 2)
                    ELSE NULL 
                END as target_upside_percent,
                CASE
                    WHEN s.last_updated IS NULL THEN 'never_updated'
                    WHEN s.last_updated < NOW() - INTERVAL '1 hour' THEN 'stale'
                    WHEN s.last_updated < NOW() - INTERVAL '15 minutes' THEN 'updating_soon'
                    ELSE 'current'
                END as data_freshness,
                EXTRACT(EPOCH FROM (NOW() - s.last_updated))/3600 as hours_since_update
            FROM mapletrade_stocks s
            LEFT JOIN mapletrade_sectors sec ON s.sector_id = sec.id
            WHERE s.is_active = true
            ORDER BY s.market_cap DESC NULLS LAST;
            """,
            reverse_sql="DROP VIEW IF EXISTS vw_stock_performance_metrics;"
        ),
        
        # View for portfolio performance summary
        migrations.RunSQL(
            """
            CREATE OR REPLACE VIEW vw_portfolio_performance AS
            SELECT 
                p.id as portfolio_id,
                p.name as portfolio_name,
                p.user_id,
                u.username,
                COUNT(ps.stock_id) as total_positions,
                COUNT(DISTINCT s.sector_id) as sector_diversification,
                SUM(CASE WHEN ps.shares IS NOT NULL AND s.current_price IS NOT NULL 
                    THEN ps.shares * s.current_price ELSE 0 END) as current_value,
                SUM(CASE WHEN ps.shares IS NOT NULL AND ps.purchase_price IS NOT NULL 
                    THEN ps.shares * ps.purchase_price ELSE 0 END) as cost_basis,
                AVG(CASE 
                    WHEN s.target_price IS NOT NULL AND s.current_price IS NOT NULL 
                    THEN (s.target_price - s.current_price) / s.current_price * 100
                    ELSE NULL 
                END) as avg_target_upside,
                COUNT(CASE WHEN s.current_price IS NOT NULL THEN 1 END) as stocks_with_prices,
                MIN(ps.added_date) as first_position_date,
                MAX(ps.added_date) as last_position_date
            FROM mapletrade_portfolios p
            JOIN mapletrade_users u ON p.user_id = u.id
            LEFT JOIN mapletrade_portfolio_stocks ps ON p.id = ps.portfolio_id
            LEFT JOIN mapletrade_stocks s ON ps.stock_id = s.id AND s.is_active = true
            GROUP BY p.id, p.name, p.user_id, u.username
            ORDER BY current_value DESC NULLS LAST;
            """,
            reverse_sql="DROP VIEW IF EXISTS vw_portfolio_performance;"
        ),
        
        # View for sector analysis with aggregated metrics
        migrations.RunSQL(
            """
            CREATE OR REPLACE VIEW vw_sector_analytics AS
            SELECT 
                sec.id,
                sec.name as sector_name,
                sec.code as sector_code,
                sec.etf_symbol,
                sec.volatility_threshold,
                COUNT(s.id) as total_stocks,
                COUNT(CASE WHEN s.current_price IS NOT NULL THEN 1 END) as priced_stocks,
                COUNT(CASE WHEN s.target_price IS NOT NULL THEN 1 END) as stocks_with_targets,
                ROUND(AVG(s.current_price)::numeric, 2) as avg_current_price,
                ROUND(AVG(s.target_price)::numeric, 2) as avg_target_price,
                ROUND(AVG(s.market_cap/1000000000.0)::numeric, 2) as avg_market_cap_billions,
                ROUND(AVG(CASE 
                    WHEN s.target_price IS NOT NULL AND s.current_price IS NOT NULL 
                    THEN (s.target_price - s.current_price) / s.current_price * 100
                    ELSE NULL 
                END)::numeric, 2) as avg_upside_percent,
                COUNT(CASE WHEN s.last_updated > NOW() - INTERVAL '1 hour' THEN 1 END) as fresh_data_count,
                ROUND((COUNT(CASE WHEN s.last_updated > NOW() - INTERVAL '1 hour' THEN 1 END)::float / 
                       NULLIF(COUNT(s.id), 0) * 100)::numeric, 1) as data_freshness_percent
            FROM mapletrade_sectors sec
            LEFT JOIN mapletrade_stocks s ON sec.id = s.sector_id AND s.is_active = true
            GROUP BY sec.id, sec.name, sec.code, sec.etf_symbol, sec.volatility_threshold
            ORDER BY total_stocks DESC;
            """,
            reverse_sql="DROP VIEW IF EXISTS vw_sector_analytics;"
        ),
    ]