"""
User models for MapleTrade application.

This module extends Django's User model and adds portfolio-related models.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from decimal import Decimal


class User(AbstractUser):
    """
    Custom User model for MapleTrade.
    
    Extends Django's AbstractUser to add additional fields specific
    to our financial analytics platform.
    """
    
    # Profile fields
    phone_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    # Trading preferences
    risk_tolerance = models.CharField(
        max_length=20,
        choices=[
            ('conservative', 'Conservative'),
            ('moderate', 'Moderate'),
            ('aggressive', 'Aggressive'),
        ],
        default='moderate'
    )
    
    # Analytics preferences
    default_analysis_period = models.IntegerField(
        default=6,
        help_text="Default analysis period in months"
    )
    
    # Subscription/tier (for future use)
    is_premium = models.BooleanField(
        default=False,
        help_text="Whether user has premium access"
    )
    
    # Activity tracking
    last_analysis_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time user ran an analysis"
    )
    total_analyses_count = models.IntegerField(
        default=0,
        help_text="Total number of analyses performed"
    )
    
    class Meta:
        db_table = 'mapletrade_users'
    
    def __str__(self):
        return self.username
    
    @property
    def is_active_user(self):
        """Check if user has been active in the last 30 days."""
        if not self.last_analysis_date:
            return False
        days_inactive = (timezone.now() - self.last_analysis_date).days
        return days_inactive <= 30


# Import BaseModel after User is defined to avoid circular import
from data.models import BaseModel


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
    
    def save(self, *args, **kwargs):
        """Ensure only one default portfolio per user."""
        if self.is_default:
            # Set all other portfolios as non-default
            UserPortfolio.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class PortfolioStock(BaseModel):
    """
    Model linking stocks to user portfolios.
    """
    portfolio = models.ForeignKey(UserPortfolio, on_delete=models.CASCADE, related_name='stocks')
    # Use string reference to avoid circular import
    stock = models.ForeignKey('data.Stock', on_delete=models.CASCADE)
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
    
    @property
    def pnl_percentage(self):
        """Calculate P&L as percentage."""
        if self.purchase_price and self.stock.current_price and self.purchase_price > 0:
            return float((self.stock.current_price - self.purchase_price) / self.purchase_price)
        return None