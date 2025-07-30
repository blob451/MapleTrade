"""
Django management command to test database performance with financial queries.

This command tests the performance of various database operations
including indexes, views, and complex analytical queries.
"""

import time
from django.core.management.base import BaseCommand
from django.db import connection, transaction, models
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import statistics

from core.models import Stock, Sector, UserPortfolio, PortfolioStock
from users.models import User


class Command(BaseCommand):
    help = 'Test database performance with financial queries'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Create test data before running performance tests'
        )
        parser.add_argument(
            '--iterations',
            type=int,
            default=10,
            help='Number of iterations for each test (default: 10)'
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed query analysis'
        )
    
    def handle(self, *args, **options):
        """Main command handler."""
        self.stdout.write(
            self.style.SUCCESS('Starting database performance tests...')
        )
        
        if options['create_test_data']:
            self._create_test_data()
        
        iterations = options['iterations']
        detailed = options['detailed']
        
        # Test results storage
        results = {}
        
        # Test 1: Basic stock queries
        results['basic_stock_queries'] = self._test_basic_stock_queries(iterations)
        
        # Test 2: Sector-based queries
        results['sector_queries'] = self._test_sector_queries(iterations)
        
        # Test 3: Portfolio queries
        results['portfolio_queries'] = self._test_portfolio_queries(iterations)
        
        # Test 4: Complex analytical views
        results['analytical_views'] = self._test_analytical_views(iterations)
        
        # Test 5: Index effectiveness
        results['index_effectiveness'] = self._test_index_effectiveness(iterations)
        
        # Display results
        self._display_results(results, detailed)
        
        # Test database connection pooling
        self._test_connection_pooling()
        
        self.stdout.write(
            self.style.SUCCESS('\nDatabase performance tests completed!')
        )
    
    def _create_test_data(self):
        """Create test data for performance testing."""
        self.stdout.write('Creating test data...')
        
        # Create test user if doesn't exist
        test_user, created = User.objects.get_or_create(
            username='test_performance_user',
            defaults={
                'email': 'test@mapletrade.com',
                'first_name': 'Test',
                'last_name': 'User'
            }
        )
        
        # Create test portfolio
        portfolio, created = UserPortfolio.objects.get_or_create(
            user=test_user,
            name='Performance Test Portfolio',
            defaults={'description': 'Portfolio for performance testing'}
        )
        
        # Add stocks to portfolio if not already added
        active_stocks = Stock.objects.filter(is_active=True)[:20]
        for stock in active_stocks:
            PortfolioStock.objects.get_or_create(
                portfolio=portfolio,
                stock=stock,
                defaults={'notes': 'Added for performance testing'}
            )
        
        self.stdout.write(f'✓ Test data ready (Portfolio with {active_stocks.count()} stocks)')
    
    def _time_query(self, query_func, iterations=1):
        """Time a query function over multiple iterations."""
        times = []
        
        for _ in range(iterations):
            start_time = time.time()
            result = query_func()
            end_time = time.time()
            times.append(end_time - start_time)
        
        return {
            'avg_time': statistics.mean(times),
            'min_time': min(times),
            'max_time': max(times),
            'total_time': sum(times),
            'result_count': len(result) if hasattr(result, '__len__') else 1
        }
    
    def _test_basic_stock_queries(self, iterations):
        """Test basic stock query performance."""
        self.stdout.write('Testing basic stock queries...')
        
        tests = {}
        
        # Test 1: All active stocks
        tests['all_active_stocks'] = self._time_query(
            lambda: list(Stock.objects.filter(is_active=True)),
            iterations
        )
        
        # Test 2: Stocks with prices
        tests['stocks_with_prices'] = self._time_query(
            lambda: list(Stock.objects.filter(
                is_active=True,
                current_price__isnull=False
            )),
            iterations
        )
        
        # Test 3: Stocks needing updates
        cutoff_time = timezone.now() - timedelta(hours=1)
        tests['stocks_needing_update'] = self._time_query(
            lambda: list(Stock.objects.filter(
                is_active=True,
                last_updated__lt=cutoff_time
            )),
            iterations
        )
        
        # Test 4: Symbol lookup (should be very fast with index)
        tests['symbol_lookup'] = self._time_query(
            lambda: list(Stock.objects.filter(symbol__in=['AAPL', 'MSFT', 'GOOGL'])),
            iterations
        )
        
        return tests
    
    def _test_sector_queries(self, iterations):
        """Test sector-based query performance."""
        self.stdout.write('Testing sector queries...')
        
        tests = {}
        
        # Test 1: Stocks by sector
        tech_sector = Sector.objects.filter(name='Technology').first()
        if tech_sector:
            tests['stocks_by_sector'] = self._time_query(
                lambda: list(Stock.objects.filter(
                    sector=tech_sector,
                    is_active=True
                )),
                iterations
            )
        
        # Test 2: Sector summary statistics
        tests['sector_statistics'] = self._time_query(
            lambda: list(Sector.objects.annotate(
                stock_count=models.Count('stock', filter=models.Q(stock__is_active=True))
            )),
            iterations
        )
        
        return tests
    
    def _test_portfolio_queries(self, iterations):
        """Test portfolio query performance."""
        self.stdout.write('Testing portfolio queries...')
        
        tests = {}
        
        # Test 1: User portfolios with stock counts
        tests['user_portfolios'] = self._time_query(
            lambda: list(UserPortfolio.objects.annotate(
                stock_count=models.Count('stocks')
            )),
            iterations
        )
        
        # Test 2: Portfolio with stocks and sectors
        tests['portfolio_with_details'] = self._time_query(
            lambda: list(PortfolioStock.objects.select_related(
                'stock', 'stock__sector', 'portfolio'
            )),
            iterations
        )
        
        return tests
    
    def _test_analytical_views(self, iterations):
        """Test analytical database views performance."""
        self.stdout.write('Testing analytical views...')
        
        tests = {}
        
        with connection.cursor() as cursor:
            # Test 1: Active stocks with sectors view
            tests['active_stocks_view'] = self._time_query(
                lambda: self._execute_view_query(cursor, "SELECT * FROM vw_active_stocks_with_sectors LIMIT 100"),
                iterations
            )
            
            # Test 2: Sector summary view
            tests['sector_summary_view'] = self._time_query(
                lambda: self._execute_view_query(cursor, "SELECT * FROM vw_sector_summary"),
                iterations
            )
            
            # Test 3: Portfolio analysis view
            tests['portfolio_analysis_view'] = self._time_query(
                lambda: self._execute_view_query(cursor, "SELECT * FROM vw_portfolio_analysis"),
                iterations
            )
            
            # Test 4: Stocks needing update view
            tests['stocks_needing_update_view'] = self._time_query(
                lambda: self._execute_view_query(cursor, "SELECT * FROM vw_stocks_needing_update LIMIT 50"),
                iterations
            )
        
        return tests
    
    def _execute_view_query(self, cursor, query):
        """Execute a view query and return results."""
        cursor.execute(query)
        return cursor.fetchall()
    
    def _test_index_effectiveness(self, iterations):
        """Test the effectiveness of database indexes."""
        self.stdout.write('Testing index effectiveness...')
        
        tests = {}
        
        with connection.cursor() as cursor:
            # Test index usage with EXPLAIN ANALYZE
            test_queries = [
                ("sector_index", "SELECT * FROM mapletrade_stocks WHERE sector_id = 1 AND is_active = true"),
                ("symbol_index", "SELECT * FROM mapletrade_stocks WHERE symbol = 'AAPL'"),
                ("price_index", "SELECT * FROM mapletrade_stocks WHERE current_price > 100 AND last_updated > NOW() - INTERVAL '1 hour'"),
            ]
            
            for test_name, query in test_queries:
                explain_query = f"EXPLAIN ANALYZE {query}"
                tests[test_name] = self._time_query(
                    lambda q=explain_query: self._execute_explain_query(cursor, q),
                    iterations
                )
        
        return tests
    
    def _execute_explain_query(self, cursor, query):
        """Execute an EXPLAIN ANALYZE query."""
        cursor.execute(query)
        return cursor.fetchall()
    
    def _test_connection_pooling(self):
        """Test database connection pooling."""
        self.stdout.write('Testing connection pooling...')
        
        # Test multiple concurrent connections
        start_time = time.time()
        
        for i in range(10):
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        
        end_time = time.time()
        
        self.stdout.write(
            f'✓ 10 connection operations completed in {end_time - start_time:.3f} seconds'
        )
    
    def _display_results(self, results, detailed=False):
        """Display test results in a formatted way."""
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('DATABASE PERFORMANCE TEST RESULTS'))
        self.stdout.write('='*70)
        
        for category, tests in results.items():
            self.stdout.write(f'\n{category.upper().replace("_", " ")}:')
            self.stdout.write('-' * 40)
            
            for test_name, metrics in tests.items():
                avg_time = metrics['avg_time'] * 1000  # Convert to milliseconds
                result_count = metrics.get('result_count', 'N/A')
                
                # Color coding based on performance
                if avg_time < 10:
                    style = self.style.SUCCESS
                elif avg_time < 100:
                    style = self.style.WARNING
                else:
                    style = self.style.ERROR
                
                self.stdout.write(
                    f'  {test_name:25} {style(f"{avg_time:8.2f}ms")} '
                    f'({result_count} results)'
                )
                
                if detailed:
                    self.stdout.write(
                        f'    Min: {metrics["min_time"]*1000:.2f}ms, '
                        f'Max: {metrics["max_time"]*1000:.2f}ms'
                    )
        
        # Performance summary
        self.stdout.write('\n' + '='*70)
        self.stdout.write('PERFORMANCE SUMMARY:')
        self.stdout.write('  ✓ Excellent: < 10ms')
        self.stdout.write('  ⚠ Good: 10-100ms') 
        self.stdout.write('  ✗ Needs optimization: > 100ms')
        self.stdout.write('='*70)