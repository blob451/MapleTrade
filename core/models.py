"""
Core models for MapleTrade application.
These models define the basic structure for financial data and analysis.
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
from decimal import Decimal

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


class AnalysisResult(BaseModel):
    """
    Model for storing analysis results from the three-factor model.
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
    
    # Performance Metrics
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
    outperformance = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Stock outperformance vs sector"
    )
    
    # Risk Metrics
    volatility = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Annualized volatility percentage"
    )
    
    # Price Information
    current_price = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Stock price at analysis time"
    )
    target_price = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Analyst target price at analysis time"
    )
    
    # Three-factor signals
    outperformed_sector = models.BooleanField(default=False, help_text="Stock outperformed sector ETF")
    target_above_price = models.BooleanField(default=False, help_text="Target price above current")
    volatility_below_threshold = models.BooleanField(default=False, help_text="Volatility below sector threshold")
    
    # Sector Information (cached for historical reference)
    sector_name = models.CharField(max_length=100, blank=True, help_text="Sector name at time of analysis")
    sector_etf = models.CharField(max_length=10, blank=True, help_text="Sector ETF used for comparison")
    sector_volatility_threshold = models.DecimalField(
        max_digits=5, 
        decimal_places=4, 
        null=True,
        blank=True,
        help_text="Sector volatility threshold at time of analysis"
    )
    
    # Analysis metadata
    rationale = models.TextField(blank=True, help_text="Explanation for the recommendation")
    engine_version = models.CharField(max_length=20, default='1.0.0', help_text="Analytics engine version")
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
    
    @property
    def target_upside(self):
        """Calculate target upside percentage."""
        if self.target_price and self.current_price and self.current_price > 0:
            return float((self.target_price - self.current_price) / self.current_price)
        return None
    
    @property
    def conditions_met_count(self):
        """Count how many of the three conditions are met."""
        return sum([self.outperformed_sector, self.target_above_price, self.volatility_below_threshold])
    
    @property
    def is_strong_signal(self):
        """Check if this is a strong signal (2+ conditions met)."""
        return self.conditions_met_count >= 2
    
    @property
    def conditions_summary(self):
        """Get summary of conditions met."""
        conditions = []
        if self.outperformed_sector:
            conditions.append("Outperformed sector")
        if self.target_above_price:
            conditions.append("Positive analyst outlook")
        if self.volatility_below_threshold:
            conditions.append("Low volatility")
        return ", ".join(conditions) if conditions else "No conditions met"
    
    def save(self, *args, **kwargs):
        """Calculate derived fields before saving."""
        # Calculate outperformance if we have the data
        if self.stock_return is not None and self.sector_return is not None:
            self.outperformance = self.stock_return - self.sector_return
        
        # Set sector information if not already set
        if self.stock.sector and not self.sector_name:
            self.sector_name = self.stock.sector.name
            self.sector_etf = self.stock.sector.etf_symbol
            self.sector_volatility_threshold = self.stock.sector.volatility_threshold
        
        super().save(*args, **kwargs)


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
    
    @property
    def current_value(self):
        """Calculate current value of position."""
        if self.shares and self.stock.current_price:
            return float(self.shares * self.stock.current_price)
        return None
    
    @property
    def unrealized_pnl(self):
        """Calculate unrealized profit/loss."""
        if self.shares and self.purchase_price and self.stock.current_price:
            cost_basis = float(self.shares * self.purchase_price)
            current_value = float(self.shares * self.stock.current_price)
            return current_value - cost_basis
        return None