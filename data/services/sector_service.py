"""
Sector service for managing sector data and mappings.

This service handles sector classification and ETF mappings.
"""

import logging
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import models  
from django.db import transaction
from django.core.cache import cache

from data.models import Sector, Stock

logger = logging.getLogger(__name__)


class SectorService:
    """
    Service for managing sector data.
    
    Provides methods for:
    - Creating and updating sectors
    - Mapping Yahoo Finance sectors to internal sectors
    - Managing sector ETFs
    - Sector analysis
    """
    
    # Yahoo Finance sector to internal code mapping
    SECTOR_MAPPING = {
        'Technology': 'TECH',
        'Financials': 'FIN',
        'Financial Services': 'FIN',
        'Healthcare': 'HEALTH',
        'Consumer Discretionary': 'CONS_DISC',
        'Consumer Cyclical': 'CONS_DISC',
        'Consumer Staples': 'CONS_STAP',
        'Consumer Defensive': 'CONS_STAP',
        'Energy': 'ENERGY',
        'Materials': 'MAT',
        'Basic Materials': 'MAT',
        'Industrials': 'IND',
        'Utilities': 'UTIL',
        'Real Estate': 'REAL',
        'Communication Services': 'COMM',
        'Communication': 'COMM',
    }
    
    # Default sector ETFs
    SECTOR_ETFS = {
        'TECH': {'symbol': 'XLK', 'name': 'Technology Select Sector SPDR'},
        'FIN': {'symbol': 'XLF', 'name': 'Financial Select Sector SPDR'},
        'HEALTH': {'symbol': 'XLV', 'name': 'Health Care Select Sector SPDR'},
        'CONS_DISC': {'symbol': 'XLY', 'name': 'Consumer Discretionary Select SPDR'},
        'CONS_STAP': {'symbol': 'XLP', 'name': 'Consumer Staples Select Sector SPDR'},
        'ENERGY': {'symbol': 'XLE', 'name': 'Energy Select Sector SPDR'},
        'MAT': {'symbol': 'XLB', 'name': 'Materials Select Sector SPDR'},
        'IND': {'symbol': 'XLI', 'name': 'Industrial Select Sector SPDR'},
        'UTIL': {'symbol': 'XLU', 'name': 'Utilities Select Sector SPDR'},
        'REAL': {'symbol': 'XLRE', 'name': 'Real Estate Select Sector SPDR'},
        'COMM': {'symbol': 'XLC', 'name': 'Communication Services Select SPDR'},
    }
    
    # Default volatility thresholds by sector
    VOLATILITY_THRESHOLDS = {
        'TECH': Decimal('0.42'),
        'FIN': Decimal('0.35'),
        'HEALTH': Decimal('0.30'),
        'CONS_DISC': Decimal('0.38'),
        'CONS_STAP': Decimal('0.25'),
        'ENERGY': Decimal('0.45'),
        'MAT': Decimal('0.40'),
        'IND': Decimal('0.35'),
        'UTIL': Decimal('0.20'),
        'REAL': Decimal('0.32'),
        'COMM': Decimal('0.38'),
    }
    
    def get_all_sectors(self) -> List[Sector]:
        """
        Get all sectors ordered by name.
        
        Returns:
            List of Sector instances
        """
        return list(Sector.objects.all().order_by('name'))
    
    def get_or_create_by_name(self, sector_name: str) -> Optional[Sector]:
        """
        Get or create sector by Yahoo Finance name.
        
        Args:
            sector_name: Sector name from Yahoo Finance
            
        Returns:
            Sector instance or None if not mappable
        """
        if not sector_name:
            return None
        
        # Map to internal code
        code = self.SECTOR_MAPPING.get(sector_name)
        if not code:
            logger.warning(f"Unknown sector name: {sector_name}")
            return None
        
        # Get or create sector
        sector, created = Sector.objects.get_or_create(
            code=code,
            defaults=self._get_sector_defaults(code, sector_name)
        )
        
        if created:
            logger.info(f"Created new sector: {sector}")
        
        return sector
    
    def get_by_code(self, code: str) -> Optional[Sector]:
        """
        Get sector by internal code.
        
        Args:
            code: Internal sector code (e.g., 'TECH')
            
        Returns:
            Sector instance or None
        """
        try:
            return Sector.objects.get(code=code.upper())
        except Sector.DoesNotExist:
            return None
    
    def initialize_default_sectors(self) -> Dict[str, Any]:
        """
        Initialize all default sectors in database.
        
        Returns:
            Dictionary with results
        """
        results = {
            'created': [],
            'updated': [],
            'total': len(self.SECTOR_ETFS)
        }
        
        with transaction.atomic():
            for code, etf_info in self.SECTOR_ETFS.items():
                # Find a good display name
                display_name = None
                for yahoo_name, mapped_code in self.SECTOR_MAPPING.items():
                    if mapped_code == code:
                        display_name = yahoo_name
                        break
                
                if not display_name:
                    display_name = code.replace('_', ' ').title()
                
                sector, created = Sector.objects.update_or_create(
                    code=code,
                    defaults={
                        'name': display_name,
                        'etf_symbol': etf_info['symbol'],
                        'description': etf_info['name'],
                        'volatility_threshold': self.VOLATILITY_THRESHOLDS.get(
                            code, 
                            Decimal('0.35')
                        )
                    }
                )
                
                if created:
                    results['created'].append(code)
                else:
                    results['updated'].append(code)
        
        logger.info(f"Initialized sectors: {results}")
        return results
    
    def update_sector_threshold(
        self, 
        sector: Sector, 
        new_threshold: Decimal
    ) -> Sector:
        """
        Update volatility threshold for a sector.
        
        Args:
            sector: Sector instance
            new_threshold: New volatility threshold
            
        Returns:
            Updated Sector instance
        """
        sector.volatility_threshold = new_threshold
        sector.save()
        
        logger.info(f"Updated {sector.code} threshold to {new_threshold}")
        return sector
    
    def get_sector_statistics(self, sector: Sector) -> Dict[str, Any]:
        """
        Get statistics for a sector.
        
        Args:
            sector: Sector instance
            
        Returns:
            Dictionary with statistics
        """
        stock_count = Stock.objects.filter(
            sector=sector,
            is_active=True
        ).count()
        
        # Get stocks with price data
        stocks_with_prices = Stock.objects.filter(
            sector=sector,
            is_active=True,
            current_price__isnull=False
        )
        
        # Calculate market cap distribution
        market_cap_stats = stocks_with_prices.aggregate(
            total_market_cap=models.Sum('market_cap'),
            avg_market_cap=models.Avg('market_cap'),
            min_market_cap=models.Min('market_cap'),
            max_market_cap=models.Max('market_cap')
        )
        
        # Calculate price statistics
        price_stats = stocks_with_prices.aggregate(
            avg_price=models.Avg('current_price'),
            avg_target_upside=models.Avg(
                models.F('target_price') - models.F('current_price'),
                filter=models.Q(target_price__isnull=False)
            )
        )
        
        return {
            'sector': {
                'code': sector.code,
                'name': sector.name,
                'etf_symbol': sector.etf_symbol,
                'volatility_threshold': float(sector.volatility_threshold),
                'risk_category': sector.risk_category,
                'is_defensive': sector.is_defensive
            },
            'stocks': {
                'total': stock_count,
                'with_prices': stocks_with_prices.count()
            },
            'market_cap': market_cap_stats,
            'prices': price_stats
        }
    
    def validate_sector_mappings(self) -> Dict[str, Any]:
        """
        Validate that all sectors are properly configured.
        
        Returns:
            Dictionary with validation results
        """
        results = {
            'missing_sectors': [],
            'missing_etfs': [],
            'validation_errors': []
        }
        
        # Check if all expected sectors exist
        for code in self.SECTOR_ETFS.keys():
            try:
                sector = Sector.objects.get(code=code)
                
                # Check ETF symbol
                if not sector.etf_symbol:
                    results['missing_etfs'].append(code)
                
            except Sector.DoesNotExist:
                results['missing_sectors'].append(code)
        
        # Check for unmapped sectors in database
        db_sectors = Sector.objects.values_list('code', flat=True)
        for code in db_sectors:
            if code not in self.SECTOR_ETFS:
                results['validation_errors'].append(
                    f"Sector {code} exists in DB but not in configuration"
                )
        
        return results
    
    def _get_sector_defaults(self, code: str, name: str) -> Dict[str, Any]:
        """
        Get default values for creating a sector.
        
        Args:
            code: Internal sector code
            name: Display name
            
        Returns:
            Dictionary of default values
        """
        etf_info = self.SECTOR_ETFS.get(code, {})
        
        return {
            'name': name,
            'etf_symbol': etf_info.get('symbol', 'SPY'),  # Default to SPY
            'description': etf_info.get('name', f'{name} Sector'),
            'volatility_threshold': self.VOLATILITY_THRESHOLDS.get(
                code,
                Decimal('0.35')  # Default threshold
            )
        }


# Convenience function
_default_service = None

def get_sector_service() -> SectorService:
    """Get singleton instance of SectorService."""
    global _default_service
    if _default_service is None:
        _default_service = SectorService()
    return _default_service