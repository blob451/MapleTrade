"""
Management command to test fundamental analysis functionality.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal

from analytics.services import FundamentalAnalyzer
from data.models import Stock, Sector
from core.services.orchestrator import CoreOrchestrator


class Command(BaseCommand):
    help = 'Test fundamental analysis on a stock'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'symbol',
            type=str,
            help='Stock symbol to analyze (e.g., AAPL, MSFT, NVDA)'
        )
        parser.add_argument(
            '--comprehensive',
            action='store_true',
            help='Run comprehensive analysis including all components'
        )
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Create test data if stock does not exist'
        )
    
    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Testing Fundamental Analysis for {symbol}")
        self.stdout.write(f"{'='*60}\n")
        
        # Create test data if requested
        if options['create_test_data']:
            self._create_test_data(symbol)
        
        if options['comprehensive']:
            self._run_comprehensive_analysis(symbol)
        else:
            self._run_fundamental_analysis(symbol)
    
    def _run_fundamental_analysis(self, symbol: str):
        """Run standalone fundamental analysis."""
        try:
            # Initialize analyzer
            analyzer = FundamentalAnalyzer()
            
            self.stdout.write("Running fundamental analysis...")
            result = analyzer.analyze(symbol)
            
            # Display results
            self._display_fundamental_results(result)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Analysis failed: {str(e)}"))
    
    def _run_comprehensive_analysis(self, symbol: str):
        """Run comprehensive analysis using orchestrator."""
        try:
            # Initialize orchestrator
            orchestrator = CoreOrchestrator()
            
            self.stdout.write("Running comprehensive analysis...")
            result = orchestrator.perform_comprehensive_analysis(
                symbol,
                include_technical=True,
                include_fundamental=True
            )
            
            # Display three-factor results
            self.stdout.write("\n" + self.style.SUCCESS("Three-Factor Analysis:"))
            three_factor = result['three_factor_analysis']
            self.stdout.write(f"  Recommendation: {three_factor['recommendation']}")
            self.stdout.write(f"  Confidence: {three_factor['confidence']:.2%}")
            
            # Display fundamental results
            if 'fundamental_analysis' in result:
                self.stdout.write("\n" + self.style.SUCCESS("Fundamental Analysis:"))
                self._display_fundamental_results(result['fundamental_analysis'])
            
            # Display combined recommendation
            if 'combined_recommendation' in result:
                self.stdout.write("\n" + self.style.SUCCESS("Combined Recommendation:"))
                combined = result['combined_recommendation']
                self.stdout.write(f"  Recommendation: {combined['recommendation']}")
                self.stdout.write(f"  Confidence: {combined['confidence']}")
                self.stdout.write(f"  Method: {combined['method']}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Comprehensive analysis failed: {str(e)}"))
    
    def _display_fundamental_results(self, result: dict):
        """Display fundamental analysis results."""
        # Basic info
        self.stdout.write(f"\nAnalysis completed at: {result['timestamp']}")
        
        # Financial Ratios
        self.stdout.write("\n" + self.style.SUCCESS("Financial Ratios:"))
        ratios = result['ratios']
        for name, value in ratios.items():
            if value is not None:
                if name.endswith('ratio'):
                    self.stdout.write(f"  {name}: {value:.2f}")
                elif name in ['roe', 'roa', 'profit_margin']:
                    self.stdout.write(f"  {name}: {value:.2%}")
                else:
                    self.stdout.write(f"  {name}: {value}")
        
        # Valuation Metrics
        self.stdout.write("\n" + self.style.SUCCESS("Valuation Metrics:"))
        valuation = result['valuation']
        if valuation.get('current_price'):
            self.stdout.write(f"  Current Price: ${valuation['current_price']:.2f}")
        if valuation.get('target_price'):
            self.stdout.write(f"  Target Price: ${valuation['target_price']:.2f}")
        if valuation.get('analyst_upside'):
            self.stdout.write(f"  Analyst Upside: {valuation['analyst_upside']:.1%}")
        if valuation.get('avg_fair_value'):
            self.stdout.write(f"  Average Fair Value: ${valuation['avg_fair_value']:.2f}")
        if valuation.get('upside_potential'):
            self.stdout.write(f"  Upside Potential: {valuation['upside_potential']:.1%}")
        
        # Financial Health
        self.stdout.write("\n" + self.style.SUCCESS("Financial Health:"))
        health = result['financial_health']
        self.stdout.write(f"  Overall Score: {health['overall_score']:.2f}/1.00")
        self.stdout.write(f"  Rating: {health['rating']}")
        if health.get('strengths'):
            self.stdout.write(f"  Strengths: {', '.join(health['strengths'])}")
        if health.get('weaknesses'):
            self.stdout.write(f"  Weaknesses: {', '.join(health['weaknesses'])}")
        
        # Signals
        self.stdout.write("\n" + self.style.SUCCESS("Fundamental Signals:"))
        for signal_name, signal_data in result['signals'].items():
            self.stdout.write(f"  {signal_name}:")
            self.stdout.write(f"    Signal: {signal_data['signal']}")
            self.stdout.write(f"    Strength: {signal_data.get('strength', 'N/A')}")
            self.stdout.write(f"    Reason: {signal_data.get('reason', 'N/A')}")
        
        # Final Recommendation
        self.stdout.write("\n" + self.style.SUCCESS("Fundamental Recommendation:"))
        recommendation = result['recommendation']
        self.stdout.write(f"  Recommendation: {recommendation['recommendation']}")
        self.stdout.write(f"  Confidence: {recommendation['confidence']}")
        self.stdout.write(f"  Score: {recommendation['score']:.1f}/100")
        self.stdout.write(f"  Buy Signals: {recommendation['buy_signals']}")
        self.stdout.write(f"  Sell Signals: {recommendation['sell_signals']}")
        self.stdout.write(f"  Reasoning: {recommendation['reasoning']}")
        
        # Summary
        self.stdout.write("\n" + self.style.SUCCESS("Analysis Summary:"))
        self.stdout.write(f"  {result['analysis_summary']}")
    
    def _create_test_data(self, symbol: str):
        """Create test stock data for demonstration."""
        self.stdout.write(f"\nCreating test data for {symbol}...")
        
        # Create or get sector
        sector, _ = Sector.objects.get_or_create(
            code='TECH',
            defaults={
                'name': 'Technology',
                'etf_symbol': 'XLK',
                'volatility_threshold': Decimal('0.35')
            }
        )
        
        # Define test data based on symbol
        test_data = {
            'AAPL': {
                'name': 'Apple Inc.',
                'current_price': Decimal('150.00'),
                'target_price': Decimal('180.00'),
                'market_cap': 2500000000000
            },
            'MSFT': {
                'name': 'Microsoft Corporation',
                'current_price': Decimal('350.00'),
                'target_price': Decimal('400.00'),
                'market_cap': 2600000000000
            },
            'NVDA': {
                'name': 'NVIDIA Corporation',
                'current_price': Decimal('500.00'),
                'target_price': Decimal('600.00'),
                'market_cap': 1200000000000
            }
        }
        
        # Get data or use defaults
        data = test_data.get(symbol, {
            'name': f'{symbol} Corporation',
            'current_price': Decimal('100.00'),
            'target_price': Decimal('120.00'),
            'market_cap': 100000000000
        })
        
        # Create or update stock
        stock, created = Stock.objects.update_or_create(
            symbol=symbol,
            defaults={
                'name': data['name'],
                'sector': sector,
                'current_price': data['current_price'],
                'target_price': data['target_price'],
                'market_cap': data['market_cap'],
                'exchange': 'NASDAQ'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created test stock: {symbol}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated test stock: {symbol}"))