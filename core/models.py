"""
Core models for MapleTrade application.
These models define the basic structure for financial data and analysis.
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import json
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
    def is_defensive(self):
        """Check if this is a defensive sector (low volatility)."""
        defensive_codes = ['UTILITIES', 'CONSUMER_STAPLES', 'HEALTHCARE']
        return self.code in defensive_codes
    
    @property 
    def risk_category(self):
        """Get risk category based on volatility threshold."""
        vol = float(self.volatility_threshold)
        if vol <= 0.25:
            return "LOW_RISK"
        elif vol <= 0.40:
            return "MEDIUM_RISK"
        else:
            return "HIGH_RISK"


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
        """Calculate upside potential from target price."""
        if self.target_price and self.current_price and self.current_price > 0:
            return float((self.target_price - self.current_price) / self.current_price)
        return None
    
    @property
    def has_target_upside(self):
        """Check if analyst target is above current price."""
        return self.target_price and self.current_price and self.target_price > self.current_price


class PriceData(BaseModel):
    """
    Model for storing historical price data.
    """
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='price_history')
    date = models.DateField(help_text="Trading date")
    
    # OHLCV data
    open_price = models.DecimalField(max_digits=12, decimal_places=4, help_text="Opening price")
    high_price = models.DecimalField(max_digits=12, decimal_places=4, help_text="Day's high price")
    low_price = models.DecimalField(max_digits=12, decimal_places=4, help_text="Day's low price")
    close_price = models.DecimalField(max_digits=12, decimal_places=4, help_text="Closing price")
    volume = models.BigIntegerField(help_text="Trading volume")
    
    # Calculated fields
    adjusted_close = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Dividend/split adjusted close"
    )
    
    class Meta:
        db_table = 'mapletrade_price_data'
        unique_together = ['stock', 'date']
        indexes = [
            models.Index(fields=['stock', 'date']),
            models.Index(fields=['date']),
        ]
        ordering = ['-date']  # Most recent first
    
    def __str__(self):
        return f"{self.stock.symbol} - {self.date}: ${self.close_price}"
    
    @property
    def daily_return(self):
        """Calculate daily return vs previous close."""
        prev_data = PriceData.objects.filter(
            stock=self.stock, 
            date__lt=self.date
        ).first()
        
        if prev_data and prev_data.close_price > 0:
            return float((self.close_price - prev_data.close_price) / prev_data.close_price)
        return None


class AnalysisResult(BaseModel):
    """
    Model for storing analytics engine results.
    """
    # Analysis metadata
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='analysis_results')
    analysis_date = models.DateTimeField(default=timezone.now, help_text="When analysis was performed")
    analysis_period_months = models.IntegerField(help_text="Analysis lookback period in months")
    
    # Core recommendation
    signal = models.CharField(
        max_length=4,
        choices=[('BUY', 'Buy'), ('SELL', 'Sell'), ('HOLD', 'Hold')],
        help_text="Investment recommendation"
    )
    confidence = models.CharField(
        max_length=6,
        choices=[('HIGH', 'High'), ('MEDIUM', 'Medium'), ('LOW', 'Low')],
        help_text="Confidence level in recommendation"
    )
    
    # Performance metrics
    stock_return = models.DecimalField(
        max_digits=8, 
        decimal_places=4, 
        help_text="Stock total return over analysis period"
    )
    sector_return = models.DecimalField(
        max_digits=8, 
        decimal_places=4, 
        help_text="Sector ETF return over analysis period"
    )
    outperformance = models.DecimalField(
        max_digits=8, 
        decimal_places=4, 
        help_text="Stock outperformance vs sector"
    )
    volatility = models.DecimalField(
        max_digits=6, 
        decimal_places=4, 
        help_text="Annualized volatility"
    )
    
    # Price data
    current_price = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        help_text="Price at time of analysis"
    )
    target_price = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Analyst target price"
    )
    
    # Signal breakdown
    outperformed_sector = models.BooleanField(help_text="Stock outperformed its sector ETF")
    target_above_price = models.BooleanField(help_text="Analyst target above current price")
    volatility_below_threshold = models.BooleanField(help_text="Volatility below sector threshold")
    
    # Sector context
    sector_name = models.CharField(max_length=100, help_text="Sector name at time of analysis")
    sector_etf = models.CharField(max_length=10, help_text="Sector ETF symbol used")
    sector_volatility_threshold = models.DecimalField(
        max_digits=5, 
        decimal_places=4, 
        help_text="Volatility threshold used"
    )
    
    # Analysis details
    rationale = models.TextField(help_text="Human-readable explanation of recommendation")
    
    # Technical metadata
    engine_version = models.CharField(
        max_length=20, 
        default='1.0.0', 
        help_text="Analytics engine version used"
    )
    
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
    def target_upside(self):
        """Calculate target upside percentage."""
        if self.target_price and self.current_price > 0:
            return float((self.target_price - self.current_price) / self.current_price)
        return None
    
    @property
    def conditions_met_count(self):
        """Count how many of the three conditions were met."""
        return sum([
            self.outperformed_sector,
            self.target_above_price, 
            self.volatility_below_threshold
        ])
    
    @property
    def is_strong_signal(self):
        """Check if this is a strong signal (2+ conditions met)."""
        return self.conditions_met_count >= 2
    
    def get_conditions_summary(self):
        """Get a dictionary summary of conditions met."""
        return {
            'outperformed_sector': self.outperformed_sector,
            'target_above_price': self.target_above_price,
            'volatility_below_threshold': self.volatility_below_threshold,
            'total_met': self.conditions_met_count
        }


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
    
    def get_latest_analyses(self):
        """Get latest analysis for each stock in portfolio."""
        latest_analyses = []
        
        for portfolio_stock in self.stocks.all():
            latest = portfolio_stock.stock.analysis_results.first()
            if latest:
                latest_analyses.append(latest)
                
        return latest_analyses


class PortfolioStock(BaseModel):
    """
    Model linking stocks to user portfolios.
    """
    portfolio = models.ForeignKey(UserPortfolio, on_delete=models.CASCADE, related_name='stocks')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    
    # Portfolio-specific data
    added_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, help_text="User notes about this stock")
    
    # Optional position tracking
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
            models.Index(fields=['stock']),
        ]
    
    def __str__(self):
        return f"{self.portfolio.name} - {self.stock.symbol}"
    
    @property
    def current_value(self):
        """Calculate current position value if shares and price available."""
        if self.shares and self.stock.current_price:
            return float(self.shares * self.stock.current_price)
        return None
    
    @property
    def unrealized_pnl(self):
        """Calculate unrealized P&L if position data available."""
        if self.shares and self.purchase_price and self.stock.current_price:
            cost_basis = float(self.shares * self.purchase_price)
            current_value = float(self.shares * self.stock.current_price)
            return current_value - cost_basis
        return None
    
    def get_latest_analysis(self):
        """Get the most recent analysis for this stock."""
        return self.stock.analysis_results.first()