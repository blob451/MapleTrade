"""
Core models for MapleTrade application.
These models define the basic structure for financial data and analysis.
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


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


class UserPortfolio(BaseModel):
    """
    Model for tracking user's stock watchlist/portfolio.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolios')
    name = models.CharField(max_length=100, help_text="Portfolio name")
    description = models.TextField(blank=True, help_text="Portfolio description")
    is_default = models.BooleanField(default=False, help_text="Default portfolio for user")
    
    class Meta:
        db_table = 'mapletrade_portfolios'
        unique_together = ['user', 'name']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_default']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.name}"


class PortfolioStock(BaseModel):
    """
    Model linking stocks to user portfolios.
    """
    portfolio = models.ForeignKey(UserPortfolio, on_delete=models.CASCADE, related_name='stocks')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    added_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, help_text="User notes about this stock")
    
    # Optional position tracking (for future use)
    shares = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Number of shares owned"
    )
    purchase_price = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Average purchase price"
    )
    
    class Meta:
        db_table = 'mapletrade_portfolio_stocks'
        unique_together = ['portfolio', 'stock']
        indexes = [
            models.Index(fields=['portfolio']),
            models.Index(fields=['added_date']),
        ]
    
    def __str__(self):
        return f"{self.portfolio.name} - {self.stock.symbol}"