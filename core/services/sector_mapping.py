"""
CORRECTED Sector classification and ETF mapping service.

Replace the content of core/services/sector_mapping.py with this file.
All sector codes are now 10 characters or less.
"""

import logging
from typing import Optional, Dict
from decimal import Decimal

from django.db import transaction
from core.models import Sector

logger = logging.getLogger(__name__)


class SectorMapper:
    """
    Service for mapping stocks to sectors and ETFs.
    
    Provides functionality to:
    - Map Yahoo Finance sector names to standardized sectors
    - Ensure proper ETF benchmarks for each sector
    - Handle sector classification edge cases
    """
    
    # Sector mapping based on common Yahoo Finance sector names
    # Maps Yahoo Finance sector → (Sector Code, ETF Symbol, Volatility Threshold)
    # ALL CODES ARE 10 CHARACTERS OR LESS
    SECTOR_MAPPINGS = {
        # Technology
        'Technology': ('TECH', 'XLK', 0.42),
        'Communication Services': ('COMM', 'XLC', 0.38),
        'Software': ('TECH', 'XLK', 0.42),
        'Semiconductors': ('TECH', 'XLK', 0.45),
        
        # Financial Services
        'Financial Services': ('FINANCIAL', 'XLF', 0.35),
        'Banks': ('FINANCIAL', 'XLF', 0.35),
        'Insurance': ('FINANCIAL', 'XLF', 0.32),
        'Investment Services': ('FINANCIAL', 'XLF', 0.38),
        
        # Healthcare
        'Healthcare': ('HEALTH', 'XLV', 0.28),
        'Biotechnology': ('HEALTH', 'XLV', 0.55),
        'Pharmaceuticals': ('HEALTH', 'XLV', 0.25),
        'Medical Devices': ('HEALTH', 'XLV', 0.30),
        
        # Consumer
        'Consumer Cyclical': ('CONS_DISC', 'XLY', 0.35),
        'Consumer Defensive': ('CONS_STPL', 'XLP', 0.22),
        'Retail': ('CONS_DISC', 'XLY', 0.38),
        'Automotive': ('CONS_DISC', 'XLY', 0.45),
        
        # Energy & Materials
        'Energy': ('ENERGY', 'XLE', 0.55),
        'Oil & Gas': ('ENERGY', 'XLE', 0.58),
        'Materials': ('MATERIALS', 'XLB', 0.45),
        'Metals & Mining': ('MATERIALS', 'XLB', 0.50),
        
        # Industrials
        'Industrials': ('INDUSTRIAL', 'XLI', 0.35),
        'Aerospace & Defense': ('INDUSTRIAL', 'XLI', 0.32),
        'Transportation': ('INDUSTRIAL', 'XLI', 0.40),
        'Manufacturing': ('INDUSTRIAL', 'XLI', 0.38),
        
        # Utilities & Real Estate
        'Utilities': ('UTILITIES', 'XLU', 0.20),
        'Real Estate': ('REAL_EST', 'XLRE', 0.35),
        'REITs': ('REAL_EST', 'XLRE', 0.35),
    }
    
    def __init__(self):
        """Initialize sector mapper and ensure base sectors exist."""
        self._ensure_base_sectors()
    
    def map_stock_to_sector(self, yahoo_sector: Optional[str]) -> Optional[Sector]:
        """
        Map a Yahoo Finance sector name to a Sector model instance.
        
        Args:
            yahoo_sector: Sector name from Yahoo Finance
            
        Returns:
            Sector instance or None if mapping fails
        """
        if not yahoo_sector:
            logger.warning("No sector provided for mapping")
            return None
            
        # Clean and normalize sector name
        clean_sector = yahoo_sector.strip()
        
        # Direct mapping lookup
        if clean_sector in self.SECTOR_MAPPINGS:
            code, etf_symbol, vol_threshold = self.SECTOR_MAPPINGS[clean_sector]
            return self._get_or_create_sector(code, clean_sector, etf_symbol, vol_threshold)
        
        # Partial matching for variations
        for sector_key, (code, etf_symbol, vol_threshold) in self.SECTOR_MAPPINGS.items():
            if self._is_sector_match(clean_sector, sector_key):
                logger.info(f"Mapped '{clean_sector}' to '{sector_key}' via partial match")
                return self._get_or_create_sector(code, sector_key, etf_symbol, vol_threshold)
        
        # No mapping found
        logger.warning(f"No sector mapping found for: {clean_sector}")
        return None
    
    def get_sector_by_code(self, sector_code: str) -> Optional[Sector]:
        """Get sector by code (e.g., 'TECH', 'FINANCIAL')."""
        try:
            return Sector.objects.get(code=sector_code)
        except Sector.DoesNotExist:
            return None
    
    def get_all_sectors(self) -> Dict[str, Sector]:
        """Get all available sectors as a dictionary."""
        sectors = Sector.objects.all()
        return {sector.code: sector for sector in sectors}
    
    def _ensure_base_sectors(self):
        """Ensure all base sectors from mappings exist in database."""
        unique_sectors = {}
        
        for yahoo_name, (code, etf_symbol, vol_threshold) in self.SECTOR_MAPPINGS.items():
            if code not in unique_sectors:
                unique_sectors[code] = {
                    'name': self._get_display_name(code),
                    'etf_symbol': etf_symbol,
                    'volatility_threshold': vol_threshold
                }
        
        # Create missing sectors
        for code, data in unique_sectors.items():
            self._get_or_create_sector(
                code, 
                data['name'], 
                data['etf_symbol'], 
                data['volatility_threshold']
            )
    
    def _get_or_create_sector(self, code: str, name: str, 
                             etf_symbol: str, vol_threshold: float) -> Sector:
        """Get existing sector or create new one."""
        try:
            return Sector.objects.get(code=code)
        except Sector.DoesNotExist:
            with transaction.atomic():
                sector, created = Sector.objects.get_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'etf_symbol': etf_symbol,
                        'volatility_threshold': Decimal(str(vol_threshold)),
                        'description': f'{name} sector with {etf_symbol} ETF benchmark'
                    }
                )
                if created:
                    logger.info(f"Created new sector: {code} ({name})")
                return sector
    
    def _is_sector_match(self, yahoo_sector: str, mapping_key: str) -> bool:
        """Check if Yahoo sector matches mapping key via partial matching."""
        yahoo_lower = yahoo_sector.lower()
        key_lower = mapping_key.lower()
        
        # Check if key words are contained in yahoo sector
        key_words = key_lower.split()
        yahoo_words = yahoo_lower.split()
        
        # If any significant word from mapping key is in yahoo sector
        significant_words = [w for w in key_words if len(w) > 3]  # Skip short words
        
        for word in significant_words:
            if any(word in yahoo_word for yahoo_word in yahoo_words):
                return True
                
        return False
    
    def _get_display_name(self, sector_code: str) -> str:
        """Get human-readable display name for sector code."""
        display_names = {
            'TECH': 'Technology',
            'COMM': 'Communication Services', 
            'FINANCIAL': 'Financial Services',
            'HEALTH': 'Healthcare',
            'CONS_DISC': 'Consumer Discretionary',
            'CONS_STPL': 'Consumer Staples',
            'ENERGY': 'Energy',
            'MATERIALS': 'Materials',
            'INDUSTRIAL': 'Industrials',
            'UTILITIES': 'Utilities',
            'REAL_EST': 'Real Estate'
        }
        
        return display_names.get(sector_code, sector_code.replace('_', ' ').title())


class SectorAnalyzer:
    """
    Analyzer for sector-level metrics and comparisons.
    
    Provides functionality for analyzing sector performance,
    volatility characteristics, and relative metrics.
    """
    
    def __init__(self):
        self.sector_mapper = SectorMapper()
    
    def get_sector_volatility_ranking(self) -> Dict[str, float]:
        """Get sectors ranked by volatility threshold."""
        sectors = Sector.objects.all().order_by('volatility_threshold')
        
        return {
            sector.name: float(sector.volatility_threshold) 
            for sector in sectors
        }
    
    def get_sector_etf_mapping(self) -> Dict[str, str]:
        """Get mapping of sector names to ETF symbols."""
        sectors = Sector.objects.all()
        
        return {
            sector.name: sector.etf_symbol 
            for sector in sectors
        }
    
    def is_defensive_sector(self, sector: Sector) -> bool:
        """Check if sector is considered defensive (low volatility)."""
        defensive_codes = ['UTILITIES', 'CONS_STPL', 'HEALTH']
        return sector.code in defensive_codes
    
    def is_cyclical_sector(self, sector: Sector) -> bool:
        """Check if sector is considered cyclical."""
        cyclical_codes = ['TECH', 'CONS_DISC', 'INDUSTRIAL', 'MATERIALS', 'ENERGY']
        return sector.code in cyclical_codes
    
    def get_sector_risk_category(self, sector: Sector) -> str:
        """Categorize sector by risk level based on volatility."""
        vol_threshold = float(sector.volatility_threshold)
        
        if vol_threshold <= 0.25:
            return "LOW_RISK"
        elif vol_threshold <= 0.40:
            return "MEDIUM_RISK"
        else:
            return "HIGH_RISK"


# Utility functions for sector operations
def initialize_default_sectors():
    """
    Management command helper to initialize all default sectors.
    
    This function can be called from Django management commands
    to ensure all sectors are properly set up.
    """
    mapper = SectorMapper()
    mapper._ensure_base_sectors()
    
    logger.info("Default sectors initialized successfully")
    
    # Log summary
    sectors = Sector.objects.all().order_by('code')
    for sector in sectors:
        logger.info(f"  {sector.code}: {sector.name} ({sector.etf_symbol}) "
                   f"- Vol threshold: {sector.volatility_threshold}")


def validate_sector_mappings() -> Dict[str, any]:
    """
    Validate that all sector mappings are properly configured.
    
    Returns:
        Dictionary with validation results
    """
    results = {
        'total_sectors': 0,
        'valid_etfs': 0,
        'missing_etfs': [],
        'validation_errors': []
    }
    
    try:
        sectors = Sector.objects.all()
        results['total_sectors'] = len(sectors)
        
        for sector in sectors:
            if sector.etf_symbol:
                results['valid_etfs'] += 1
            else:
                results['missing_etfs'].append(sector.code)
                
            # Validate volatility threshold
            if not (0.1 <= float(sector.volatility_threshold) <= 1.0):
                results['validation_errors'].append(
                    f"Invalid volatility threshold for {sector.code}: "
                    f"{sector.volatility_threshold}"
                )
                
    except Exception as e:
        results['validation_errors'].append(f"Validation failed: {e}")
    
    return results