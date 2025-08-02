"""
Admin configuration for users app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, UserPortfolio, PortfolioStock


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Enhanced admin for custom User model."""
    
    # Add custom fields to the user edit form
    fieldsets = BaseUserAdmin.fieldsets + (
        ('MapleTrade Settings', {
            'fields': (
                'phone_number',
                'date_of_birth',
                'risk_tolerance',
                'default_analysis_period',
                'is_premium',
                'last_analysis_date',
                'total_analyses_count',
            )
        }),
    )
    
    # Add custom fields to the user creation form
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('MapleTrade Settings', {
            'fields': (
                'phone_number',
                'risk_tolerance',
                'default_analysis_period',
            )
        }),
    )
    
    # Customize the list display
    list_display = [
        'username',
        'email',
        'first_name',
        'last_name',
        'is_premium',
        'risk_tolerance',
        'is_active_user',
        'is_staff',
        'date_joined',  # Use date_joined instead of created_at
    ]
    
    list_filter = [
        'is_staff',
        'is_superuser',
        'is_active',
        'is_premium',
        'risk_tolerance',
        'date_joined',  # Use date_joined instead of created_at
    ]
    
    search_fields = ['username', 'first_name', 'last_name', 'email']
    
    ordering = ['-date_joined']  # Use date_joined instead of created_at
    
    readonly_fields = ['last_login', 'date_joined', 'last_analysis_date', 'total_analyses_count']
    
    def is_active_user(self, obj):
        """Display if user is active (within 30 days)."""
        if obj.is_active_user:
            return format_html(
                '<span style="color: green;">✓ Active</span>'
            )
        return format_html(
            '<span style="color: red;">✗ Inactive</span>'
        )
    is_active_user.short_description = 'Active Status'
    is_active_user.admin_order_field = 'last_analysis_date'


@admin.register(UserPortfolio)
class UserPortfolioAdmin(admin.ModelAdmin):
    """Admin for user portfolios."""
    
    list_display = ['name', 'user', 'is_default', 'stock_count', 'created_at']
    list_filter = ['is_default', 'created_at']
    search_fields = ['name', 'user__username', 'description']
    raw_id_fields = ['user']
    ordering = ['user', 'name']
    
    def stock_count(self, obj):
        """Display number of stocks in portfolio."""
        return obj.stocks.count()
    stock_count.short_description = 'Stocks'
    
    actions = ['make_default']
    
    def make_default(self, request, queryset):
        """Make selected portfolios default for their users."""
        for portfolio in queryset:
            portfolio.is_default = True
            portfolio.save()
        self.message_user(request, f"{queryset.count()} portfolios set as default.")
    make_default.short_description = "Set as default portfolio"


class PortfolioStockInline(admin.TabularInline):
    """Inline admin for portfolio stocks."""
    model = PortfolioStock
    extra = 1
    raw_id_fields = ['stock']
    readonly_fields = ['current_value', 'unrealized_pnl', 'pnl_percentage']


@admin.register(PortfolioStock)
class PortfolioStockAdmin(admin.ModelAdmin):
    """Admin for portfolio stocks."""
    
    list_display = [
        'portfolio',
        'stock',
        'shares',
        'purchase_price',
        'current_value_display',
        'pnl_display',
        'added_date'
    ]
    
    list_filter = ['added_date', 'portfolio__user']
    search_fields = ['stock__symbol', 'stock__name', 'portfolio__name']
    raw_id_fields = ['portfolio', 'stock']
    ordering = ['-added_date']
    date_hierarchy = 'added_date'
    
    readonly_fields = ['current_value', 'unrealized_pnl', 'pnl_percentage']
    
    fieldsets = (
        ('Portfolio & Stock', {
            'fields': ('portfolio', 'stock', 'added_date')
        }),
        ('Position Details', {
            'fields': ('shares', 'purchase_price', 'current_value', 'unrealized_pnl', 'pnl_percentage')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('wide',)
        })
    )
    
    def current_value_display(self, obj):
        """Display current value with formatting."""
        val = obj.current_value
        if val is not None:
            return format_html(
                '<span>${:,.2f}</span>',
                val
            )
        return '-'
    current_value_display.short_description = 'Current Value'
    
    def pnl_display(self, obj):
        """Display P&L with color coding."""
        pnl = obj.unrealized_pnl
        pnl_pct = obj.pnl_percentage
        
        if pnl is not None and pnl_pct is not None:
            color = 'green' if pnl >= 0 else 'red'
            return format_html(
                '<span style="color: {};">${:,.2f} ({:.1%})</span>',
                color,
                pnl,
                pnl_pct
            )
        return '-'
    pnl_display.short_description = 'P&L'


# Add inline to UserPortfolioAdmin
UserPortfolioAdmin.inlines = [PortfolioStockInline]