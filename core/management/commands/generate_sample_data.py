"""
Django management command to generate sample financial data for testing.

This command creates realistic sample data including stocks, sectors,
and portfolio information for development and testing purposes.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
import random
from datetime import timedelta

from core.models import Stock, Sector, UserPortfolio, PortfolioStock
from users.models import User


class Command(BaseCommand):
    help = 'Generate sample financial data for testing and development'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--stocks',
            type=int,
            default=50,
            help='Number of sample stocks to create (default: 50)'
        )
        parser.add_argument(
            '--users',
            type=int,
            default=5,
            help='Number of sample users to create (default: 5)'
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Clean existing sample data before generating new data'
        )
    
    # Sample stock data
    SAMPLE_STOCKS = [
        # Technology
        ('AAPL', 'Apple Inc.', 'Technology', 150.00, 175.00, 2800000000000),
        ('MSFT', 'Microsoft Corporation', 'Technology', 380.00, 420.00, 2830000000000),
        ('GOOGL', 'Alphabet Inc.', 'Technology', 140.00, 160.00, 1780000000000),
        ('NVDA', 'NVIDIA Corporation', 'Technology', 450.00, 520.00, 1120000000000),
        ('META', 'Meta Platforms Inc.', 'Technology', 320.00, 380.00, 815000000000),
        ('TSLA', 'Tesla Inc.', 'Technology', 200.00, 280.00, 635000000000),
        ('NFLX', 'Netflix Inc.', 'Technology', 420.00, 480.00, 185000000000),
        ('ADBE', 'Adobe Inc.', 'Technology', 480.00, 560.00, 220000000000),
        
        # Financials
        ('JPM', 'JPMorgan Chase & Co.', 'Financials', 155.00, 175.00, 450000000000),
        ('BAC', 'Bank of America Corp.', 'Financials', 32.00, 38.00, 255000000000),
        ('WFC', 'Wells Fargo & Co.', 'Financials', 42.00, 50.00, 155000000000),
        ('GS', 'Goldman Sachs Group Inc.', 'Financials', 380.00, 420.00, 125000000000),
        ('MS', 'Morgan Stanley', 'Financials', 85.00, 100.00, 145000000000),
        
        # Healthcare
        ('JNJ', 'Johnson & Johnson', 'Healthcare', 165.00, 180.00, 435000000000),
        ('PFE', 'Pfizer Inc.', 'Healthcare', 28.00, 35.00, 160000000000),
        ('UNH', 'UnitedHealth Group Inc.', 'Healthcare', 520.00, 580.00, 485000000000),
        ('ABBV', 'AbbVie Inc.', 'Healthcare', 150.00, 170.00, 265000000000),
        ('MRK', 'Merck & Co. Inc.', 'Healthcare', 105.00, 120.00, 265000000000),
        
        # Energy
        ('XOM', 'Exxon Mobil Corporation', 'Energy', 110.00, 125.00, 465000000000),
        ('CVX', 'Chevron Corporation', 'Energy', 155.00, 175.00, 295000000000),
        ('COP', 'ConocoPhillips', 'Energy', 115.00, 130.00, 145000000000),
        
        # Consumer Discretionary
        ('AMZN', 'Amazon.com Inc.', 'Consumer Discretionary', 140.00, 165.00, 1450000000000),
        ('HD', 'Home Depot Inc.', 'Consumer Discretionary', 350.00, 400.00, 365000000000),
        ('MCD', 'McDonald\'s Corporation', 'Consumer Discretionary', 280.00, 310.00, 205000000000),
        ('NKE', 'Nike Inc.', 'Consumer Discretionary', 85.00, 100.00, 135000000000),
        
        # Industrials
        ('BA', 'Boeing Company', 'Industrials', 200.00, 250.00, 115000000000),
        ('CAT', 'Caterpillar Inc.', 'Industrials', 280.00, 320.00, 145000000000),
        ('GE', 'General Electric Company', 'Industrials', 105.00, 125.00, 115000000000),
        
        # Materials
        ('LIN', 'Linde plc', 'Materials', 420.00, 480.00, 205000000000),
        
        # Utilities
        ('NEE', 'NextEra Energy Inc.', 'Utilities', 65.00, 75.00, 135000000000),
        
        # Communication Services
        ('DIS', 'Walt Disney Company', 'Communication Services', 95.00, 115.00, 175000000000),
        ('VZ', 'Verizon Communications Inc.', 'Communication Services', 40.00, 45.00, 165000000000),
        
        # Consumer Staples
        ('PG', 'Procter & Gamble Company', 'Consumer Staples', 155.00, 170.00, 365000000000),
        ('KO', 'Coca-Cola Company', 'Consumer Staples', 62.00, 70.00, 265000000000),
        ('WMT', 'Walmart Inc.', 'Consumer Staples', 160.00, 180.00, 445000000000),
        
        # Real Estate
        ('AMT', 'American Tower Corporation', 'Real Estate', 190.00, 220.00, 85000000000),
    ]
    
    def handle(self, *args, **options):
        """Main command handler."""
        if options['clean']:
            self._clean_sample_data()
        
        self.stdout.write(
            self.style.SUCCESS('Generating sample financial data...')
        )
        
        # Generate sectors first
        sectors_created = self._create_sectors()
        
        # Generate stocks
        stocks_created = self._create_stocks(options['stocks'])
        
        # Generate users and portfolios
        users_created = self._create_users_and_portfolios(options['users'])
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSample data generation complete:\n'
                f'  - Sectors: {sectors_created}\n'
                f'  - Stocks: {stocks_created}\n'
                f'  - Users: {users_created}'
            )
        )
    
    def _clean_sample_data(self):
        """Clean existing sample data."""
        self.stdout.write('Cleaning existing sample data...')
        
        # Delete test users and their portfolios
        User.objects.filter(username__startswith='test_user_').delete()
        
        # Delete sample stocks (be careful not to delete real data)
        Stock.objects.filter(name__contains='Sample Stock').delete()
        
        self.stdout.write('✓ Sample data cleaned')
    
    def _create_sectors(self):
        """Ensure all required sectors exist."""
        sectors_created = 0
        
        sector_data = [
            ('Technology', 'TECH', 'XLK', 0.50),
            ('Financials', 'FIN', 'XLF', 0.38),
            ('Healthcare', 'HEALTH', 'XLV', 0.38),
            ('Energy', 'ENERGY', 'XLE', 0.46),
            ('Consumer Discretionary', 'DISC', 'XLY', 0.46),
            ('Industrials', 'IND', 'XLI', 0.42),
            ('Materials', 'MAT', 'XLB', 0.42),
            ('Utilities', 'UTIL', 'XLU', 0.32),
            ('Communication Services', 'COMM', 'XLC', 0.42),
            ('Consumer Staples', 'STAPLES', 'XLP', 0.38),
            ('Real Estate', 'REIT', 'XLRE', 0.38),
        ]
        
        for name, code, etf, volatility in sector_data:
            sector, created = Sector.objects.get_or_create(
                name=name,
                defaults={
                    'code': code,
                    'etf_symbol': etf,
                    'volatility_threshold': Decimal(str(volatility)),
                    'description': f'{name} sector stocks'
                }
            )
            if created:
                sectors_created += 1
        
        return sectors_created
    
    def _create_stocks(self, target_count):
        """Create sample stock data."""
        stocks_created = 0
        
        # First, create stocks from our predefined list
        for symbol, name, sector_name, current_price, target_price, market_cap in self.SAMPLE_STOCKS:
            if stocks_created >= target_count:
                break
                
            if not Stock.objects.filter(symbol=symbol).exists():
                try:
                    sector = Sector.objects.get(name=sector_name)
                    
                    # Add some randomness to prices for realism
                    price_variance = random.uniform(0.95, 1.05)
                    current_price = Decimal(str(current_price * price_variance))
                    target_price = Decimal(str(target_price * price_variance))
                    
                    Stock.objects.create(
                        symbol=symbol,
                        name=name,
                        sector=sector,
                        exchange='NASDAQ' if sector_name == 'Technology' else 'NYSE',
                        currency='USD',
                        market_cap=market_cap,
                        current_price=current_price,
                        target_price=target_price,
                        is_active=True,
                        last_updated=timezone.now() - timedelta(
                            minutes=random.randint(1, 1440)  # Random time in last 24 hours
                        )
                    )
                    stocks_created += 1
                    
                except Sector.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f'Sector {sector_name} not found for {symbol}')
                    )
        
        # If we need more stocks, create some synthetic ones
        if stocks_created < target_count:
            sectors = list(Sector.objects.all())
            
            for i in range(stocks_created, target_count):
                sector = random.choice(sectors)
                symbol = f'TEST{i:03d}'
                
                if not Stock.objects.filter(symbol=symbol).exists():
                    base_price = random.uniform(20, 500)
                    current_price = Decimal(str(base_price))
                    target_price = Decimal(str(base_price * random.uniform(1.05, 1.30)))
                    
                    Stock.objects.create(
                        symbol=symbol,
                        name=f'Sample Stock {i}',
                        sector=sector,
                        exchange=random.choice(['NYSE', 'NASDAQ']),
                        currency='USD',
                        market_cap=random.randint(1000000000, 1000000000000),
                        current_price=current_price,
                        target_price=target_price,
                        is_active=True,
                        last_updated=timezone.now() - timedelta(
                            minutes=random.randint(1, 1440)
                        )
                    )
                    stocks_created += 1
        
        return stocks_created
    
    def _create_users_and_portfolios(self, user_count):
        """Create sample users with portfolios."""
        users_created = 0
        
        for i in range(user_count):
            username = f'test_user_{i+1}'
            
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f'test{i+1}@mapletrade.com',
                    password='testpassword123',
                    first_name=f'Test{i+1}',
                    last_name='User',
                    risk_tolerance=random.choice(['conservative', 'moderate', 'aggressive'])
                )
                
                # Create portfolios for each user
                portfolios = [
                    ('My Portfolio', 'Primary investment portfolio'),
                    ('Tech Stocks', 'Technology sector focus'),
                    ('Dividend Portfolio', 'Income-focused investments'),
                ]
                
                available_stocks = list(Stock.objects.filter(is_active=True))
                
                for portfolio_name, description in portfolios:
                    portfolio = UserPortfolio.objects.create(
                        user=user,
                        name=portfolio_name,
                        description=description,
                        is_default=(portfolio_name == 'My Portfolio')
                    )
                    
                    # Add random stocks to portfolio
                    portfolio_stocks = random.sample(
                        available_stocks, 
                        min(random.randint(5, 15), len(available_stocks))
                    )
                    
                    for stock in portfolio_stocks:
                        PortfolioStock.objects.create(
                            portfolio=portfolio,
                            stock=stock,
                            shares=Decimal(str(random.randint(1, 100))),
                            purchase_price=stock.current_price * Decimal(str(random.uniform(0.8, 1.2))),
                            added_date=timezone.now() - timedelta(days=random.randint(1, 365)),
                            notes=f'Added to {portfolio_name}'
                        )
                
                users_created += 1
        
        return users_created