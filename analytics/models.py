"""
Analytics models for stock analysis application.
Updated for Task 3.2 - Removed duplicate User model to avoid conflicts.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
import json

# Get the existing User model
User = get_user_model()


class Sector(models.Model):
    """Stock market sectors with ETF mappings."""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    etf_symbol = models.CharField(max_length=10, help_text="ETF symbol for sector benchmark")
    volatility_threshold = models.FloatField(
        default=0.25,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Volatility threshold for risk assessment"
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Stock(models.Model):
    """Stock information and metadata."""
    symbol = models.CharField(max_length=10, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    sector = models.ForeignKey(
        Sector, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='stocks'
    )
    exchange = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=3, default='USD')
    market_cap = models.BigIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['symbol']
        indexes = [
            models.Index(fields=['symbol', 'is_active']),
            models.Index(fields=['sector', 'is_active']),
        ]

    def __str__(self):
        return f"{self.symbol} - {self.name}"


class PriceData(models.Model):
    """Historical price data for stocks."""
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='price_data')
    date = models.DateField(db_index=True)
    open_price = models.DecimalField(max_digits=10, decimal_places=4)
    high_price = models.DecimalField(max_digits=10, decimal_places=4)
    low_price = models.DecimalField(max_digits=10, decimal_places=4)
    close_price = models.DecimalField(max_digits=10, decimal_places=4)
    volume = models.BigIntegerField()
    adjusted_close = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['stock', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['stock', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.stock.symbol} - {self.date} - ${self.close_price}"


class TechnicalIndicator(models.Model):
    """
    Technical indicator calculations and results.
    Stores calculated technical indicators for stocks.
    """
    INDICATOR_CHOICES = [
        ('SMA', 'Simple Moving Average'),
        ('EMA', 'Exponential Moving Average'),
        ('RSI', 'Relative Strength Index'),
        ('MACD', 'Moving Average Convergence Divergence'),
        ('BOLLINGER', 'Bollinger Bands'),
        ('STOCHASTIC', 'Stochastic Oscillator'),
        ('ATR', 'Average True Range'),
        ('WILLIAMS_R', 'Williams %R'),
    ]
    
    SIGNAL_CHOICES = [
        ('BULLISH', 'Bullish'),
        ('BEARISH', 'Bearish'),
        ('NEUTRAL', 'Neutral'),
        ('OVERBOUGHT', 'Overbought'),
        ('OVERSOLD', 'Oversold'),
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('HOLD', 'Hold'),
        ('STRONG_BUY', 'Strong Buy'),
        ('STRONG_SELL', 'Strong Sell'),
    ]

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='technical_indicators')
    indicator_type = models.CharField(max_length=20, choices=INDICATOR_CHOICES, db_index=True)
    calculation_date = models.DateTimeField(db_index=True)
    
    # Parameters for the indicator calculation
    period = models.IntegerField(null=True, blank=True, help_text="Period used for calculation (e.g., 14 for RSI)")
    fast_period = models.IntegerField(null=True, blank=True, help_text="Fast period for MACD")
    slow_period = models.IntegerField(null=True, blank=True, help_text="Slow period for MACD")
    signal_period = models.IntegerField(null=True, blank=True, help_text="Signal period for MACD")
    std_dev = models.FloatField(null=True, blank=True, help_text="Standard deviation multiplier for Bollinger Bands")
    
    # Current values
    current_value = models.FloatField(null=True, blank=True, help_text="Current indicator value")
    signal = models.CharField(max_length=20, choices=SIGNAL_CHOICES, default='NEUTRAL')
    confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence level of the signal (0-1)"
    )
    
    # JSON field for storing complex indicator data (series, additional values, etc.)
    data = models.JSONField(
        default=dict,
        help_text="Additional indicator data in JSON format"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-calculation_date', 'indicator_type']
        indexes = [
            models.Index(fields=['stock', 'indicator_type', 'calculation_date']),
            models.Index(fields=['indicator_type', 'calculation_date']),
            models.Index(fields=['stock', 'calculation_date']),
            models.Index(fields=['signal', 'calculation_date']),
        ]
        # Ensure we don't have duplicate indicators for the same stock/date/parameters
        unique_together = ['stock', 'indicator_type', 'calculation_date', 'period', 'fast_period', 'slow_period']

    def __str__(self):
        period_info = f"({self.period})" if self.period else ""
        return f"{self.stock.symbol} - {self.indicator_type}{period_info} - {self.calculation_date.date()}"
    
    def get_series_data(self):
        """Get time series data from JSON field."""
        return self.data.get('series', [])
    
    def set_series_data(self, series_data):
        """Set time series data in JSON field."""
        if not self.data:
            self.data = {}
        self.data['series'] = series_data
    
    def get_additional_values(self):
        """Get additional indicator values (e.g., MACD components)."""
        return {k: v for k, v in self.data.items() if k != 'series'}
    
    def set_additional_value(self, key, value):
        """Set additional indicator value."""
        if not self.data:
            self.data = {}
        self.data[key] = value


class AnalysisResult(models.Model):
    """
    Stock analysis results from the analytics engine.
    Updated to include technical analysis integration.
    """
    SIGNAL_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('HOLD', 'Hold'),
        ('STRONG_BUY', 'Strong Buy'),
        ('STRONG_SELL', 'Strong Sell'),
    ]

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='analysis_results')
    analysis_date = models.DateTimeField(db_index=True)
    analysis_period_months = models.IntegerField(default=6)
    
    # Three-factor model results (from prototype)
    sector_outperformance = models.BooleanField(null=True, blank=True)
    analyst_target_positive = models.BooleanField(null=True, blank=True)
    volatility_acceptable = models.BooleanField(null=True, blank=True)
    
    # Financial metrics
    stock_return = models.FloatField(null=True, blank=True)
    sector_return = models.FloatField(null=True, blank=True)
    volatility = models.FloatField(null=True, blank=True)
    current_price = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    target_price = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    
    # Analysis results
    fundamental_signal = models.CharField(max_length=20, choices=SIGNAL_CHOICES, default='HOLD')
    technical_signal = models.CharField(max_length=20, choices=SIGNAL_CHOICES, default='HOLD')
    overall_signal = models.CharField(max_length=20, choices=SIGNAL_CHOICES, default='HOLD')
    
    # Confidence and scoring
    confidence_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    risk_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    # Rationale and explanation
    rationale = models.TextField(blank=True)
    technical_summary = models.TextField(blank=True, help_text="Summary of technical analysis")
    
    # Related technical indicators (for this analysis)
    technical_indicators = models.ManyToManyField(
        TechnicalIndicator,
        blank=True,
        help_text="Technical indicators used in this analysis"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-analysis_date']
        indexes = [
            models.Index(fields=['stock', 'analysis_date']),
            models.Index(fields=['overall_signal', 'analysis_date']),
            models.Index(fields=['analysis_date']),
        ]

    def __str__(self):
        return f"{self.stock.symbol} - {self.overall_signal} - {self.analysis_date.date()}"
    
    def get_signal_display_color(self):
        """Get color for displaying signal in UI."""
        color_map = {
            'BUY': 'green',
            'STRONG_BUY': 'darkgreen',
            'SELL': 'red',
            'STRONG_SELL': 'darkred',
            'HOLD': 'orange',
        }
        return color_map.get(self.overall_signal, 'gray')


class UserPortfolio(models.Model):
    """User portfolio tracking."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analytics_portfolios')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['user', 'name']

    def __str__(self):
        return f"{self.user.username} - {self.name}"


class PortfolioHolding(models.Model):
    """Individual stock holdings in a portfolio."""
    portfolio = models.ForeignKey(UserPortfolio, on_delete=models.CASCADE, related_name='holdings')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=4)
    average_cost = models.DecimalField(max_digits=10, decimal_places=4)
    purchase_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-purchase_date']
        unique_together = ['portfolio', 'stock']

    def __str__(self):
        return f"{self.portfolio.name} - {self.stock.symbol} ({self.quantity} shares)"
    
    @property
    def total_cost(self):
        """Calculate total cost of holding."""
        return self.quantity * self.average_cost