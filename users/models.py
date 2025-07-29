"""
Custom User model for MapleTrade application.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    
    This model is designed to be extensible for future multi-user features
    while maintaining compatibility with Django's built-in authentication system.
    """
    
    # Additional fields for MapleTrade
    email = models.EmailField(unique=True, help_text="User's email address")
    created_at = models.DateTimeField(default=timezone.now, help_text="Account creation timestamp")
    updated_at = models.DateTimeField(auto_now=True, help_text="Last profile update timestamp")
    
    # User preferences for analysis
    default_analysis_period = models.IntegerField(
        default=6, 
        help_text="Default analysis period in months"
    )
    risk_tolerance = models.CharField(
        max_length=20,
        choices=[
            ('conservative', 'Conservative'),
            ('moderate', 'Moderate'),
            ('aggressive', 'Aggressive'),
        ],
        default='moderate',
        help_text="User's risk tolerance level"
    )
    
    # User activity tracking
    last_analysis_date = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Timestamp of user's last analysis"
    )
    total_analyses_count = models.PositiveIntegerField(
        default=0, 
        help_text="Total number of analyses performed by user"
    )
    
    # Account status
    is_premium = models.BooleanField(
        default=False, 
        help_text="Premium account status (for future use)"
    )
    
    class Meta:
        db_table = 'mapletrade_users'
        verbose_name = 'MapleTrade User'
        verbose_name_plural = 'MapleTrade Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['created_at']),
            models.Index(fields=['last_analysis_date']),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.email})"
    
    def update_analysis_count(self):
        """Update the total analysis count and last analysis date."""
        self.total_analyses_count += 1
        self.last_analysis_date = timezone.now()
        self.save(update_fields=['total_analyses_count', 'last_analysis_date'])
    
    @property
    def is_active_user(self):
        """Check if user has performed analysis in the last 30 days."""
        if not self.last_analysis_date:
            return False
        return (timezone.now() - self.last_analysis_date).days <= 30