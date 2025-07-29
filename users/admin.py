"""
Admin configuration for User model.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin interface for MapleTrade User model.
    """
    
    # Fields to display in the user list
    list_display = (
        'username', 
        'email', 
        'first_name', 
        'last_name', 
        'is_active', 
        'is_premium',
        'total_analyses_count',
        'last_analysis_date',
        'created_at'
    )
    
    # Fields that can be used for filtering
    list_filter = (
        'is_active', 
        'is_staff', 
        'is_superuser', 
        'is_premium',
        'risk_tolerance',
        'created_at',
        'last_analysis_date'
    )
    
    # Fields that can be searched
    search_fields = ('username', 'email', 'first_name', 'last_name')
    
    # Default ordering
    ordering = ('-created_at',)
    
    # Fields to display when editing a user
    fieldsets = BaseUserAdmin.fieldsets + (
        ('MapleTrade Settings', {
            'fields': (
                'default_analysis_period',
                'risk_tolerance',
                'is_premium',
            )
        }),
        ('Activity Information', {
            'fields': (
                'total_analyses_count',
                'last_analysis_date',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    # Fields to display when adding a new user
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Information', {
            'fields': (
                'email',
                'first_name',
                'last_name',
                'default_analysis_period',
                'risk_tolerance',
            )
        }),
    )
    
    # Read-only fields
    readonly_fields = ('created_at', 'updated_at', 'total_analyses_count', 'last_analysis_date')