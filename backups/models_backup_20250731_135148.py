"""
Core models for MapleTrade application.
These models define the basic structure for financial data and analysis.
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

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
        ]
    
    def __str__(self):
        return f"{self.stock.symbol} - {self.date}: ${self.close_price}"


class AnalysisResult(BaseModel):
    """
    Model for storing analysis results.
    """
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='analysis_results')
    analysis_date = models.DateTimeField(default=timezone.now, help_text="When analysis was performed")
    analysis_period_months = models.IntegerField(default=6, help_text="Analysis period in months")
    
    # Recommendation
    SIGNAL_CHOICES = [
        ('BUY', 'Buy'),
        ('HOLD', 'Hold'),
        ('SELL', 'Sell'),
    ]
    signal = models.CharField(max_length=4, choices=SIGNAL_CHOICES, help_text="Investment recommendation")
    confidence = models.DecimalField(
        max_digits=5, 
        decimal_places=4, 
        default=0,
        help_text="Confidence score (0-1)"
    )
    
    # Three-factor signals
    outperformed_sector = models.BooleanField(default=False, help_text="Stock outperformed sector ETF")
    target_above_current = models.BooleanField(default=False, help_text="Target price above current")
    low_volatility = models.BooleanField(default=False, help_text="Volatility below threshold")
    
    # Metrics
    stock_return = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Stock return percentage"
    )
    sector_return = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Sector ETF return percentage"
    )
    volatility = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Annualized volatility percentage"
    )
    
    # Analysis metadata
    rationale = models.TextField(blank=True, help_text="Explanation for the recommendation")
    errors = models.JSONField(default=list, blank=True, help_text="Any errors during analysis")
    raw_data = models.JSONField(default=dict, blank=True, help_text="Complete analysis data")
    
    # Cache control
    is_valid = models.BooleanField(default=True, help_text="Whether this analysis is still valid")
    
    class Meta:
        db_table = 'mapletrade_analysis_results'
        indexes = [
            models.Index(fields=['stock', 'analysis_date']),
            models.Index(fields=['analysis_date']),
            models.Index(fields=['signal']),
            models.Index(fields=['stock', 'signal']),
        ]
        ordering = ['-analysis_date']
    
    def __str__(self):
        return f"{self.stock.symbol} - {self.signal} ({self.analysis_date.date()})"
    
    @property
    def is_recent(self):
        """Check if analysis is recent (within 24 hours)."""
        return (timezone.now() - self.analysis_date).total_seconds() < 86400


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
            models.Index(fields=['stock']),
            models.Index(fields=['added_date']),
        ]
    
    def __str__(self):
        return f"{self.portfolio.name} - {self.stock.symbol}"