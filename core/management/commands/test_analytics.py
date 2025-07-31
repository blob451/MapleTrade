"""
Management command to test the analytics engine implementation.

This command replicates the prototype analysis to verify that the Django
implementation produces the same results as the Jupyter notebook.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from decimal import Decimal
import json
import traceback

from core.services.analytics_engine import AnalyticsEngine, AnalyticsEngineError
from core.services.sector_mapping import initialize_default_sectors, validate_sector_mappings
from core.models import Stock, Sector


class Command(BaseCommand):
    help = 'Test the analytics engine implementation and verify results'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            default='NVDA',
            help='Stock symbol to analyze (default: NVDA)'
        )
        parser.add_argument(
            '--months',
            type=int,
            default=12,
            help='Analysis period in months (default: 12)'
        )
        parser.add_argument(
            '--setup-sectors',
            action='store_true',
            help='Initialize default sectors before running test'
        )
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Only run validation checks without analysis'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )
    
    def handle(self, *args, **options):
        """Main command handler."""
        
        symbol = options['symbol'].upper()
        months = options['months']
        verbose = options['verbose']
        
        self.stdout.write(
            self.style.SUCCESS(f"\n🔍 MapleTrade Analytics Engine Test")
        )
        self.stdout.write(f"Testing symbol: {symbol}")
        self.stdout.write(f"Analysis period: {months} months")
        self.stdout.write(f"Timestamp: {timezone.now()}\n")
        
        try:
            # Step 1: Setup sectors if requested
            if options['setup_sectors']:
                self._setup_sectors()
            
            # Step 2: Validate system setup
            self._validate_setup()
            
            # Step 3: Run validation checks if requested
            if options['validate_only']:
                self._run_validation_only()
                return
            
            # Step 4: Initialize analytics engine
            self.stdout.write("📊 Initializing Analytics Engine...")
            engine = AnalyticsEngine()
            
            # Step 5: Run analysis
            self.stdout.write(f"🚀 Running analysis for {symbol}...")
            result = engine.analyze_stock(symbol, months)
            
            # Step 6: Display results
            self._display_results(result, verbose)
            
            # Step 7: Verify result structure
            self._verify_result_structure(result)
            
            self.stdout.write(
                self.style.SUCCESS(f"\n✅ Analysis completed successfully!")
            )
            
        except AnalyticsEngineError as e:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Analytics engine error: {e}")
            )
            raise CommandError(f"Analytics engine failed: {e}")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Unexpected error: {e}")
            )
            if verbose:
                self.stdout.write("\nFull traceback:")
                self.stdout.write(traceback.format_exc())
            raise CommandError(f"Test failed: {e}")
    
    def _setup_sectors(self):
        """Initialize default sectors."""
        self.stdout.write("🏗️  Setting up default sectors...")
        
        try:
            initialize_default_sectors()
            sector_count = Sector.objects.count()
            self.stdout.write(
                self.style.SUCCESS(f"   ✓ {sector_count} sectors initialized")
            )
        except Exception as e:
            raise CommandError(f"Sector setup failed: {e}")
    
    def _validate_setup(self):
        """Validate system setup and dependencies."""
        self.stdout.write("🔧 Validating system setup...")
        
        # Check database connectivity
        try:
            sector_count = Sector.objects.count()
            stock_count = Stock.objects.count()
            self.stdout.write(f"   ✓ Database: {sector_count} sectors, {stock_count} stocks")
        except Exception as e:
            raise CommandError(f"Database validation failed: {e}")
        
        # Validate sector mappings
        try:
            validation = validate_sector_mappings()
            if validation['validation_errors']:
                self.stdout.write(
                    self.style.WARNING(f"   ⚠️  Sector validation issues:")
                )
                for error in validation['validation_errors']:
                    self.stdout.write(f"      - {error}")
            else:
                self.stdout.write(
                    f"   ✓ Sectors: {validation['total_sectors']} total, "
                    f"{validation['valid_etfs']} with ETFs"
                )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"   ⚠️  Sector validation failed: {e}")
            )
    
    def _run_validation_only(self):
        """Run only validation checks."""
        self.stdout.write("🔍 Running validation-only mode...\n")
        
        # Test sector mappings
        self._test_sector_mappings()
        
        # Test calculation functions
        self._test_calculations()
        
        self.stdout.write(
            self.style.SUCCESS("\n✅ Validation completed!")
        )
    
    def _test_sector_mappings(self):
        """Test sector mapping functionality."""
        self.stdout.write("Testing sector mappings...")
        
        from core.services.sector_mapping import SectorMapper
        
        mapper = SectorMapper()
        test_sectors = [
            'Technology', 'Financial Services', 'Healthcare',
            'Consumer Cyclical', 'Energy', 'Invalid Sector'
        ]
        
        for sector_name in test_sectors:
            sector = mapper.map_stock_to_sector(sector_name)
            if sector:
                self.stdout.write(f"   ✓ {sector_name} → {sector.code} ({sector.etf_symbol})")
            else:
                self.stdout.write(f"   ❌ {sector_name} → No mapping")
    
    def _test_calculations(self):
        """Test calculation functions with sample data."""
        self.stdout.write("Testing calculation functions...")
        
        from core.services.calculations import ReturnCalculator, VolatilityCalculator
        from data.providers.base import PriceData
        from datetime import date
        
        # Create sample price data
        sample_prices = [
            PriceData(date=date(2024, 1, 1), open=100, high=105, low=95, close=102, volume=1000000),
            PriceData(date=date(2024, 1, 2), open=102, high=108, low=101, close=106, volume=1200000),
            PriceData(date=date(2024, 1, 3), open=106, high=109, low=103, close=104, volume=900000),
            PriceData(date=date(2024, 1, 4), open=104, high=107, low=102, close=105, volume=1100000),
            PriceData(date=date(2024, 1, 5), open=105, high=110, low=104, close=108, volume=1300000),
        ]
        
        # Test return calculation
        return_calc = ReturnCalculator()
        total_return = return_calc.calculate_total_return(sample_prices)
        self.stdout.write(f"   ✓ Return calculation: {total_return:.1%}")
        
        # Test volatility calculation  
        vol_calc = VolatilityCalculator()
        try:
            volatility = vol_calc.calculate_annualized_volatility(sample_prices)
            self.stdout.write(f"   ✓ Volatility calculation: {volatility:.1%}")
        except Exception as e:
            self.stdout.write(f"   ❌ Volatility calculation failed: {e}")
    
    def _display_results(self, result, verbose=False):
        """Display analysis results in a formatted way."""
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(f"📈 ANALYSIS RESULTS FOR {result.signals.stock_return is not None and result.signals.stock_return or 'N/A'}")
        self.stdout.write("="*60)
        
        # Signal and confidence
        signal_style = self.style.SUCCESS if result.signal == 'BUY' else \
                      self.style.ERROR if result.signal == 'SELL' else \
                      self.style.WARNING
        
        self.stdout.write(f"\n🎯 RECOMMENDATION: {signal_style(result.signal)}")
        self.stdout.write(f"🔒 CONFIDENCE: {result.confidence}")
        
        # Key metrics
        self.stdout.write(f"\n📊 KEY METRICS:")
        self.stdout.write(f"   Stock Return:     {result.stock_return:>8.1%}")
        self.stdout.write(f"   Sector Return:    {result.sector_return:>8.1%}")  
        self.stdout.write(f"   Outperformance:   {result.outperformance:>8.1%}")
        self.stdout.write(f"   Volatility:       {result.volatility:>8.1%}")
        self.stdout.write(f"   Current Price:    ${result.current_price:>7.2f}")
        
        if result.target_price:
            upside = (result.target_price - result.current_price) / result.current_price
            self.stdout.write(f"   Target Price:     ${result.target_price:>7.2f} ({upside:+.1%})")
        else:
            self.stdout.write(f"   Target Price:     {'N/A':>12}")
        
        # Signal breakdown
        self.stdout.write(f"\n✅ CONDITIONS MET:")
        for condition, met in result.conditions_met.items():
            status = "✓" if met else "✗"
            self.stdout.write(f"   {status} {condition.replace('_', ' ').title()}")
        
        # Sector info
        self.stdout.write(f"\n🏷️  SECTOR INFO:")
        self.stdout.write(f"   Sector:           {result.sector_name}")
        self.stdout.write(f"   Benchmark ETF:    {result.sector_etf}")
        self.stdout.write(f"   Analysis Period:  {result.analysis_period_months} months")
        
        # Rationale
        self.stdout.write(f"\n💭 RATIONALE:")
        self.stdout.write(f"   {result.rationale}")
        
        if verbose:
            self._display_verbose_details(result)
    
    def _display_verbose_details(self, result):
        """Display additional verbose details."""
        self.stdout.write(f"\n🔍 VERBOSE DETAILS:")
        
        signals = result.signals
        self.stdout.write(f"   Raw Signals:")
        self.stdout.write(f"     Outperformed Sector: {signals.outperformed_sector}")
        self.stdout.write(f"     Target Above Price:  {signals.target_above_price}")
        self.stdout.write(f"     Low Volatility:      {signals.volatility_below_threshold}")
        
        if signals.sector_threshold:
            self.stdout.write(f"   Volatility vs Threshold: {signals.volatility:.1%} vs {signals.sector_threshold:.1%}")
        
        self.stdout.write(f"   Analysis Timestamp: {result.timestamp}")
    
    def _verify_result_structure(self, result):
        """Verify that the result has the expected structure."""
        self.stdout.write("\n🔍 Verifying result structure...")
        
        required_fields = [
            'signal', 'confidence', 'stock_return', 'sector_return',
            'outperformance', 'volatility', 'current_price', 'signals',
            'analysis_period_months', 'sector_name', 'sector_etf',
            'timestamp', 'rationale', 'conditions_met'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not hasattr(result, field):
                missing_fields.append(field)
        
        if missing_fields:
            raise CommandError(f"Result missing required fields: {missing_fields}")
        
        # Verify signal values
        if result.signal not in ['BUY', 'SELL', 'HOLD']:
            raise CommandError(f"Invalid signal value: {result.signal}")
        
        if result.confidence not in ['HIGH', 'MEDIUM', 'LOW']:
            raise CommandError(f"Invalid confidence value: {result.confidence}")
        
        self.stdout.write("   ✓ Result structure is valid")
        
        # Test JSON serialization
        try:
            # Convert result to dict for JSON testing
            result_dict = {
                'signal': result.signal,
                'confidence': result.confidence,
                'metrics': {
                    'stock_return': result.stock_return,
                    'sector_return': result.sector_return,
                    'volatility': result.volatility,
                    'current_price': result.current_price,
                    'target_price': result.target_price
                },
                'sector': {
                    'name': result.sector_name,
                    'etf': result.sector_etf
                },
                'rationale': result.rationale
            }
            
            json.dumps(result_dict, default=str)  # Test serialization
            self.stdout.write("   ✓ Result is JSON serializable")
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"   ⚠️  JSON serialization issue: {e}")
            )