"""
Data models for MapleTrade application.

This module contains all database models related to market data,
including stocks, sectors, and price history.
"""

from django.db import models
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

class BaseModel(models.Model):
    """
    Abstract base model with common fields for all MapleTrade models.
    """
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class Sector(BaseModel):
    """
    Model representing stock market sectors.
    """
    name = models.CharField(max_length=100, unique=True, help_text="Sector name (e.g., Technology)")
    code = models.CharField(max_length=10, unique=True, help_text="Sector code (e.g., TECH)")
    description = models.TextField(blank=True, help_text="Sector description")
    etf_symbol = models.CharField(max_length=10, help_text="Representative ETF symbol (e.g., XLK)")
    volatility_threshold = models.DecimalField(
        max_digits=5, 
        decimal_places=4, 
        default=0.42,
        help_text="Volatility threshold for this sector"
    )
    
    class Meta:
        db_table = 'mapletrade_sectors'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['code']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    @property
    def risk_category(self):
        """Categorize sector by risk based on volatility threshold."""
        if self.volatility_threshold < Decimal('0.30'):
            return 'Low Risk'
        elif self.volatility_threshold < Decimal('0.45'):
            return 'Medium Risk'
        else:
            return 'High Risk'
    
    @property
    def is_defensive(self):
        """Check if sector is considered defensive."""
        defensive_codes = ['UTIL', 'CONS', 'HLTH', 'REAL']
        return self.code in defensive_codes


class Stock(BaseModel):
    """
    Model representing individual stocks.
    """
    symbol = models.CharField(max_length=10, unique=True, help_text="Stock ticker symbol")
    name = models.CharField(max_length=200, help_text="Company name")
    sector = models.ForeignKey(
        Sector, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='stocks',
        help_text="Stock's sector classification"
    )
    exchange = models.CharField(max_length=50, blank=True, help_text="Stock exchange")
    currency = models.CharField(max_length=3, default='USD', help_text="Trading currency")
    market_cap = models.BigIntegerField(null=True, blank=True, help_text="Market capitalization")
    
    # Cached fundamental data (updated periodically)
    current_price = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Current/last traded price"
    )
    target_price = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Analyst target price"
    )
    
    # Status fields
    is_active = models.BooleanField(default=True, help_text="Whether stock is actively tracked")
    last_updated = models.DateTimeField(null=True, blank=True, help_text="Last data update")
    
    class Meta:
        db_table = 'mapletrade_stocks'
        indexes = [
            models.Index(fields=['symbol']),
            models.Index(fields=['sector']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.symbol} - {self.name}"
    
    @property
    def needs_update(self):
        """Check if stock data needs updating (older than 1 hour)."""
        if not self.last_updated:
            return True
        return (timezone.now() - self.last_updated).total_seconds() > 3600
    
    @property
    def target_upside(self):
        """Calculate percentage upside to target price."""
        if self.target_price and self.current_price and self.current_price > 0:
            return float((self.target_price - self.current_price) / self.current_price)
        return None
    
    @property
    def has_target_upside(self):
        """Check if stock has positive target upside."""
        upside = self.target_upside
        return upside is not None and upside > 0


class PriceData(BaseModel):
    """
    Model for storing historical price data.
    """
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='price_history')
    date = models.DateField(help_text="Price date")
    open_price = models.DecimalField(max_digits=12, decimal_places=4, help_text="Opening price")
    high_price = models.DecimalField(max_digits=12, decimal_places=4, help_text="High price")
    low_price = models.DecimalField(max_digits=12, decimal_places=4, help_text="Low price")
    close_price = models.DecimalField(max_digits=12, decimal_places=4, help_text="Closing price")
    adjusted_close = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Adjusted closing price"
    )
    volume = models.BigIntegerField(help_text="Trading volume")
    
    class Meta:
        db_table = 'mapletrade_price_data'
        unique_together = ['stock', 'date']
        indexes = [
            models.Index(fields=['stock', 'date']),
            models.Index(fields=['date']),
            models.Index(fields=['stock', '-date']),  # For latest price queries
        ]
    
    def __str__(self):
        return f"{self.stock.symbol} - {self.date}: ${self.close_price}"
    
    @property
    def daily_return(self):
        """Calculate daily return if previous day exists."""
        try:
            previous = PriceData.objects.filter(
                stock=self.stock,
                date__lt=self.date
            ).order_by('-date').first()
            
            if previous and previous.close_price > 0:
                return float((self.close_price - previous.close_price) / previous.close_price)
        except:
            pass
        return None