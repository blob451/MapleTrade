"""
Management command to initialize default sectors and ETF mappings.

This command sets up the base sector configuration required for the
analytics engine to function properly.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.services.sector_mapping import initialize_default_sectors, validate_sector_mappings
from core.models import Sector


class Command(BaseCommand):
    help = 'Initialize default sectors and ETF mappings for the analytics engine'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of sectors (deletes existing data)'
        )
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Only validate existing sectors without creating new ones'
        )
        parser.add_argument(
            '--list-sectors',
            action='store_true',
            help='List all current sectors and exit'
        )
    
    def handle(self, *args, **options):
        """Main command handler."""
        
        self.stdout.write(
            self.style.SUCCESS('\n🏗️  MapleTrade Sector Initialization')
        )
        
        try:
            # List sectors if requested
            if options['list_sectors']:
                self._list_current_sectors()
                return
            
            # Validate only if requested
            if options['validate_only']:
                self._validate_only()
                return
            
            # Force recreation if requested
            if options['force']:
                self._force_recreation()
            
            # Initialize sectors
            self._initialize_sectors()
            
            # Validate results
            self._validate_results()
            
            self.stdout.write(
                self.style.SUCCESS('\n✅ Sector initialization completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Initialization failed: {e}')
            )
            raise CommandError(f'Sector initialization failed: {e}')
    
    def _list_current_sectors(self):
        """List all current sectors in the database."""
        sectors = Sector.objects.all().order_by('code')
        
        if not sectors:
            self.stdout.write('No sectors found in database.')
            return
        
        self.stdout.write(f'\n📋 Current Sectors ({len(sectors)} total):')
        self.stdout.write('-' * 70)
        
        for sector in sectors:
            self.stdout.write(
                f'{sector.code:<15} {sector.name:<25} '
                f'{sector.etf_symbol:<6} {sector.volatility_threshold:>6.1%}'
            )
        
        self.stdout.write('-' * 70)
    
    def _validate_only(self):
        """Run validation on existing sectors."""
        self.stdout.write('🔍 Validating existing sectors...\n')
        
        validation = validate_sector_mappings()
        
        self.stdout.write(f'Total sectors: {validation["total_sectors"]}')
        self.stdout.write(f'Valid ETFs: {validation["valid_etfs"]}')
        
        if validation['missing_etfs']:
            self.stdout.write(
                self.style.WARNING(
                    f'Missing ETFs: {", ".join(validation["missing_etfs"])}'
                )
            )
        
        if validation['validation_errors']:
            self.stdout.write(self.style.ERROR('\nValidation Errors:'))
            for error in validation['validation_errors']:
                self.stdout.write(f'  ❌ {error}')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ All sectors valid!'))
    
    def _force_recreation(self):
        """Force recreation of all sectors (destructive operation)."""
        self.stdout.write(
            self.style.WARNING(
                '⚠️  Force recreation requested - this will delete existing sectors!'
            )
        )
        
        # Confirm deletion
        confirm = input('Type "yes" to confirm deletion of existing sectors: ')
        if confirm.lower() != 'yes':
            raise CommandError('Operation cancelled by user')
        
        # Delete existing sectors
        with transaction.atomic():
            deleted_count = Sector.objects.count()
            Sector.objects.all().delete()
            
        self.stdout.write(
            self.style.SUCCESS(f'🗑️  Deleted {deleted_count} existing sectors')
        )
    
    def _initialize_sectors(self):
        """Initialize default sectors."""
        self.stdout.write('🚀 Initializing default sectors...')
        
        initial_count = Sector.objects.count()
        
        try:
            initialize_default_sectors()
        except Exception as e:
            raise CommandError(f'Sector initialization failed: {e}')
        
        final_count = Sector.objects.count()
        created_count = final_count - initial_count
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Initialization complete: {created_count} new sectors created'
            )
        )
        
        # Show created sectors
        if created_count > 0:
            self.stdout.write('\n📦 Sectors created/updated:')
            sectors = Sector.objects.all().order_by('code')
            
            for sector in sectors:
                self.stdout.write(
                    f'   {sector.code}: {sector.name} '
                    f'({sector.etf_symbol}, {sector.volatility_threshold:.1%} vol)'
                )
    
    def _validate_results(self):
        """Validate the initialization results."""
        self.stdout.write('\n🔍 Validating initialization results...')
        
        validation = validate_sector_mappings()
        
        if validation['validation_errors']:
            self.stdout.write(self.style.ERROR('❌ Validation issues found:'))
            for error in validation['validation_errors']:
                self.stdout.write(f'  • {error}')
            raise CommandError('Sector validation failed after initialization')
        
        # Check minimum required sectors
        required_sectors = ['TECH', 'FINANCIAL', 'HEALTH', 'ENERGY']
        missing_required = []
        
        for req_sector in required_sectors:
            try:
                Sector.objects.get(code=req_sector)
            except Sector.DoesNotExist:
                missing_required.append(req_sector)
        
        if missing_required:
            raise CommandError(
                f'Missing required sectors: {", ".join(missing_required)}'
            )
        
        self.stdout.write('✅ Validation passed!')
        
        # Summary stats
        total_sectors = Sector.objects.count()
        etf_count = Sector.objects.exclude(etf_symbol='').count()
        
        self.stdout.write(f'\n📊 Summary:')
        self.stdout.write(f'   Total sectors: {total_sectors}')
        self.stdout.write(f'   With ETF mappings: {etf_count}')
        self.stdout.write(f'   Coverage: {etf_count/total_sectors:.1%}')


# Helper function for other management commands
def ensure_sectors_initialized():
    """
    Utility function to ensure sectors are initialized.
    
    This can be called by other management commands that depend on sectors.
    """
    sector_count = Sector.objects.count()
    
    if sector_count == 0:
        from django.core.management import call_command
        call_command('init_sectors')
        return True  # Sectors were created
    
    return False  # Sectors already existed