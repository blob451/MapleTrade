"""
Sector mapping service for MapleTrade.
"""

from typing import Optional
from data.models import Sector


class SectorMapper:
    """Maps stocks to their appropriate sectors."""
    
    # Yahoo Finance sector to our sector code mapping
    SECTOR_MAPPING = {
        'Technology': 'TECH',
        'Financials': 'FIN',
        'Healthcare': 'HEALTH',
        'Consumer Discretionary': 'CONS_DISC',
        'Consumer Staples': 'CONS_STAP',
        'Energy': 'ENERGY',
        'Materials': 'MAT',
        'Industrials': 'IND',
        'Utilities': 'UTIL',
        'Real Estate': 'REAL',
        'Communication Services': 'COMM',
    }
    
    def map_stock_to_sector(self, yahoo_sector: str) -> Optional[Sector]:
        """Map Yahoo Finance sector to our Sector model."""
        sector_code = self.SECTOR_MAPPING.get(yahoo_sector)
        
        if sector_code:
            try:
                return Sector.objects.get(code=sector_code)
            except Sector.DoesNotExist:
                pass
        
        return None


def validate_sector_mappings():
    """Validate that all sectors are properly configured."""
    validation_results = {
        'missing_sectors': [],
        'validation_errors': []
    }
    
    # Check if all expected sectors exist
    for sector_name, sector_code in SectorMapper.SECTOR_MAPPING.items():
        try:
            Sector.objects.get(code=sector_code)
        except Sector.DoesNotExist:
            validation_results['missing_sectors'].append({
                'name': sector_name,
                'code': sector_code
            })
    
    return validation_results