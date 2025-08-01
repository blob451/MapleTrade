"""
Analytics models for MapleTrade application.

These models store analysis results, technical indicators, and recommendation history
for stock analysis and machine learning predictions.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import json

from core.models import BaseModel, Stock, Sector
from users.models import User


class StockAnalysis(BaseModel):
    """
    Stores comprehensive analysis results for a stock.
    
    This model captures the output of the three-factor analysis model
    and provides a historical record of all analyses performed.
    """
    
    SIGNAL_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('HOLD', 'Hold'),
    ]
    
    # Relationships
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='analyses',
        help_text="User who requested this analysis"
    )
    stock = models.ForeignKey(
        Stock, 
        on_delete=models.CASCADE, 
        related_name='analyses',
        help_text="Stock being analyzed"
    )
    sector_etf = models.CharField(
        max_length=10, 
        help_text="Sector ETF used for comparison"
    )
    
    # Analysis Parameters
    analysis_period_months = models.IntegerField(
        default=6,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Analysis lookback period in months"
    )
    analysis_end_date = models.DateTimeField(
        default=timezone.now,
        help_text="End date of the analysis period"
    )
    
    # Core Results
    signal = models.CharField(
        max_length=4, 
        choices=SIGNAL_CHOICES,
        db_index=True,
        help_text="Buy/Sell/Hold recommendation"
    )
    confidence_score = models.DecimalField(
        max_digits=3, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Confidence in the recommendation (0-1)"
    )
    
    # Performance Metrics
    stock_return = models.DecimalField(
        max_digits=10, 
        decimal_places=4,
        help_text="Stock return over analysis period"
    )
    sector_return = models.DecimalField(
        max_digits=10, 
        decimal_places=4,
        help_text="Sector ETF return over analysis period"
    )
    relative_performance = models.DecimalField(
        max_digits=10, 
        decimal_places=4,
        help_text="Stock return minus sector return"
    )
    
    # Risk Metrics
    volatility = models.DecimalField(
        max_digits=10, 
        decimal_places=4,
        validators=[MinValueValidator(0)],
        help_text="Annualized volatility"
    )
    volatility_threshold = models.DecimalField(
        max_digits=5, 
        decimal_places=4,
        help_text="Sector-specific volatility threshold used"
    )
    is_high_volatility = models.BooleanField(
        default=False,
        help_text="Whether volatility exceeds sector threshold"
    )
    
    # Price Targets
    current_price = models.DecimalField(
        max_digits=12, 
        decimal_places=4,
        help_text="Stock price at analysis time"
    )
    analyst_target = models.DecimalField(
        max_digits=12, 
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Consensus analyst target price"
    )
    target_upside = models.DecimalField(
        max_digits=10, 
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Percentage upside to target price"
    )
    
    # Signal Components (for explainability)
    outperformed_sector = models.BooleanField(
        default=False,
        help_text="Whether stock outperformed its sector"
    )
    positive_analyst_outlook = models.BooleanField(
        default=False,
        help_text="Whether analyst target > current price"
    )
    
    # Analysis Details (flexible JSON storage)
    analysis_data = models.JSONField(
        default=dict,
        help_text="Detailed analysis data and intermediate calculations"
    )
    
    # Explanation
    rationale = models.TextField(
        help_text="Human-readable explanation of the recommendation"
    )
    rationale_details = models.JSONField(
        default=dict,
        help_text="Structured rationale with contributing factors"
    )
    
    # Execution Details
    analysis_duration_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time taken to perform analysis in milliseconds"
    )
    data_quality_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Quality score of underlying data (0-1)"
    )
    
    class Meta:
        db_table = 'mapletrade_stock_analysis'
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['stock', '-created_at']),
            models.Index(fields=['signal', '-created_at']),
            models.Index(fields=['created_at']),
            models.Index(fields=['analysis_end_date']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.stock.symbol} - {self.signal} ({self.created_at.date()})"
    
    def save(self, *args, **kwargs):
        """Calculate derived fields before saving."""
        # Calculate relative performance
        if self.stock_return is not None and self.sector_return is not None:
            self.relative_performance = self.stock_return - self.sector_return
        
        # Calculate target upside
        if self.analyst_target and self.current_price and self.current_price > 0:
            self.target_upside = ((self.analyst_target - self.current_price) / self.current_price) * 100
        
        # Determine if high volatility
        if self.volatility and self.volatility_threshold:
            self.is_high_volatility = self.volatility > self.volatility_threshold
        
        super().save(*args, **kwargs)
    
    @property
    def signal_strength(self):
        """Calculate signal strength based on component alignment."""
        components = [self.outperformed_sector, self.positive_analyst_outlook]
        if not self.is_high_volatility:
            components.append(True)
        return sum(components) / 3


class TechnicalIndicator(BaseModel):
    """
    Stores calculated technical indicators for a stock at a specific time.
    
    This model supports future ML features and technical analysis.
    """
    
    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name='technical_indicators'
    )
    
    date = models.DateField(
        help_text="Date of the indicator calculation"
    )
    
    # Moving Averages
    sma_20 = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="20-day Simple Moving Average"
    )
    sma_50 = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="50-day Simple Moving Average"
    )
    sma_200 = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="200-day Simple Moving Average"
    )
    ema_12 = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="12-day Exponential Moving Average"
    )
    ema_26 = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="26-day Exponential Moving Average"
    )
    
    # Momentum Indicators
    rsi_14 = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="14-day Relative Strength Index"
    )
    macd = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="MACD Line"
    )
    macd_signal = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="MACD Signal Line"
    )
    macd_histogram = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="MACD Histogram"
    )
    
    # Volatility Indicators
    bollinger_upper = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Bollinger Upper Band"
    )
    bollinger_middle = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Bollinger Middle Band (20-day SMA)"
    )
    bollinger_lower = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Bollinger Lower Band"
    )
    
    # Volume Indicators
    volume_sma_20 = models.BigIntegerField(
        null=True, blank=True,
        help_text="20-day average volume"
    )
    
    class Meta:
        db_table = 'mapletrade_technical_indicators'
        unique_together = ['stock', 'date']
        indexes = [
            models.Index(fields=['stock', '-date']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.stock.symbol} - {self.date}"


class RecommendationHistory(BaseModel):
    """
    Tracks the history of recommendation changes for a stock.
    
    This model helps identify when recommendations change and why.
    """
    
    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name='recommendation_history'
    )
    
    previous_signal = models.CharField(
        max_length=4,
        choices=StockAnalysis.SIGNAL_CHOICES,
        null=True,
        blank=True,
        help_text="Previous recommendation signal"
    )
    
    new_signal = models.CharField(
        max_length=4,
        choices=StockAnalysis.SIGNAL_CHOICES,
        help_text="New recommendation signal"
    )
    
    change_reason = models.TextField(
        help_text="Explanation for the recommendation change"
    )
    
    analysis_result = models.ForeignKey(
        StockAnalysis,
        on_delete=models.CASCADE,
        related_name='recommendation_changes',
        help_text="Analysis that triggered this change"
    )
    
    # Metrics at time of change
    price_at_change = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        help_text="Stock price when recommendation changed"
    )
    
    class Meta:
        db_table = 'mapletrade_recommendation_history'
        indexes = [
            models.Index(fields=['stock', '-created_at']),
            models.Index(fields=['new_signal', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.stock.symbol}: {self.previous_signal} → {self.new_signal}"


class SectorAnalysis(BaseModel):
    """
    Aggregated analysis data for entire sectors.
    
    This model supports sector-level insights and comparisons.
    """
    
    sector = models.ForeignKey(
        Sector,
        on_delete=models.CASCADE,
        related_name='sector_analyses'
    )
    
    analysis_date = models.DateField(
        help_text="Date of sector analysis"
    )
    
    # Aggregate metrics
    avg_return = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Average return of stocks in sector"
    )
    
    avg_volatility = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Average volatility of stocks in sector"
    )
    
    buy_count = models.IntegerField(
        default=0,
        help_text="Number of BUY recommendations in sector"
    )
    
    hold_count = models.IntegerField(
        default=0,
        help_text="Number of HOLD recommendations in sector"
    )
    
    sell_count = models.IntegerField(
        default=0,
        help_text="Number of SELL recommendations in sector"
    )
    
    top_performers = models.JSONField(
        default=list,
        help_text="List of top performing stocks in sector"
    )
    
    class Meta:
        db_table = 'mapletrade_sector_analysis'
        unique_together = ['sector', 'analysis_date']
        indexes = [
            models.Index(fields=['sector', '-analysis_date']),
        ]
    
    def __str__(self):
        return f"{self.sector.name} - {self.analysis_date}"