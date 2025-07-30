"""
Django management command to populate sector data.

This command creates the standard market sectors with their
corresponding ETF symbols and volatility thresholds.
"""

from django.core.management.base import BaseCommand
from core.models import Sector


class Command(BaseCommand):
    help = 'Populate market sectors with ETF mappings and volatility thresholds'
    
    def handle(self, *args, **options):
        """Create standard market sectors."""
        sectors_data = [
            {
                'name': 'Technology',
                'code': 'TECH',
                'etf_symbol': 'XLK',
                'volatility_threshold': 0.50,
                'description': 'Technology hardware, software, and services'
            },
            {
                'name': 'Financials',
                'code': 'FIN',
                'etf_symbol': 'XLF',
                'volatility_threshold': 0.38,
                'description': 'Banks, insurance, real estate, and financial services'
            },
            {
                'name': 'Healthcare',
                'code': 'HEALTH',
                'etf_symbol': 'XLV',
                'volatility_threshold': 0.38,
                'description': 'Healthcare equipment, services, and biotechnology'
            },
            {
                'name': 'Energy',
                'code': 'ENERGY',
                'etf_symbol': 'XLE',
                'volatility_threshold': 0.46,
                'description': 'Oil, gas, and renewable energy companies'
            },
            {
                'name': 'Consumer Discretionary',
                'code': 'DISC',
                'etf_symbol': 'XLY',
                'volatility_threshold': 0.46,
                'description': 'Non-essential consumer goods and services'
            },
            {
                'name': 'Industrials',
                'code': 'IND',
                'etf_symbol': 'XLI',
                'volatility_threshold': 0.42,
                'description': 'Manufacturing, transportation, and aerospace'
            },
            {
                'name': 'Utilities',
                'code': 'UTIL',
                'etf_symbol': 'XLU',
                'volatility_threshold': 0.32,
                'description': 'Electric, gas, and water utilities'
            },
            {
                'name': 'Materials',
                'code': 'MAT',
                'etf_symbol': 'XLB',
                'volatility_threshold': 0.42,
                'description': 'Chemicals, metals, mining, and forestry'
            },
            {
                'name': 'Real Estate',
                'code': 'REIT',
                'etf_symbol': 'XLRE',
                'volatility_threshold': 0.38,
                'description': 'Real estate investment trusts and development'
            },
            {
                'name': 'Communication Services',
                'code': 'COMM',
                'etf_symbol': 'XLC',
                'volatility_threshold': 0.42,
                'description': 'Telecommunications and media companies'
            },
            {
                'name': 'Consumer Staples',
                'code': 'STAPLES',
                'etf_symbol': 'XLP',
                'volatility_threshold': 0.38,
                'description': 'Essential consumer goods and food products'
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for sector_data in sectors_data:
            sector, created = Sector.objects.update_or_create(
                name=sector_data['name'],
                defaults={
                    'code': sector_data['code'],
                    'etf_symbol': sector_data['etf_symbol'],
                    'volatility_threshold': sector_data['volatility_threshold'],
                    'description': sector_data['description'],
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'✓ Created sector: {sector.name}')
            else:
                updated_count += 1
                self.stdout.write(f'↻ Updated sector: {sector.name}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSector population complete: '
                f'{created_count} created, {updated_count} updated'
            )
        )