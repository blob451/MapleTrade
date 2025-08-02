"""
Admin configuration for data models.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Sector, Stock, PriceData


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    """Admin for sectors."""
    
    list_display = ['name', 'code', 'etf_symbol', 'volatility_threshold', 'risk_category_display']
    list_filter = ['code']
    search_fields = ['name', 'code', 'etf_symbol']
    ordering = ['name']
    
    def risk_category_display(self, obj):
        """Display risk category with color coding."""
        category = obj.risk_category
        if category == 'Low Risk':
            color = 'green'
        elif category == 'Medium Risk':
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            category
        )
    risk_category_display.short_description = 'Risk Level'


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    """Admin for stocks."""
    
    list_display = [
        'symbol',
        'name',
        'sector',
        'current_price_display',
        'target_price_display',
        'target_upside_display',
        'is_active',
        'last_updated'
    ]
    
    list_filter = ['is_active', 'sector', 'exchange']
    search_fields = ['symbol', 'name']
    raw_id_fields = ['sector']
    ordering = ['symbol']
    date_hierarchy = 'last_updated'
    
    readonly_fields = ['target_upside', 'has_target_upside', 'needs_update', 'last_updated']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('symbol', 'name', 'sector', 'exchange', 'currency')
        }),
        ('Market Data', {
            'fields': ('current_price', 'target_price', 'target_upside', 'market_cap')
        }),
        ('Status', {
            'fields': ('is_active', 'last_updated', 'needs_update')
        }),
    )
    
    def current_price_display(self, obj):
        """Display current price."""
        if obj.current_price:
            return format_html('${:,.2f}', obj.current_price)
        return '-'
    current_price_display.short_description = 'Current Price'
    
    def target_price_display(self, obj):
        """Display target price."""
        if obj.target_price:
            return format_html('${:,.2f}', obj.target_price)
        return '-'
    target_price_display.short_description = 'Target Price'
    
    def target_upside_display(self, obj):
        """Display target upside as percentage."""
        upside = obj.target_upside
        if upside is not None:
            color = 'green' if upside > 0 else 'red'
            return format_html(
                '<span style="color: {};">{:.1%}</span>',
                color,
                upside
            )
        return '-'
    target_upside_display.short_description = 'Target Upside'
    
    actions = ['mark_active', 'mark_inactive', 'update_prices']
    
    def mark_active(self, request, queryset):
        """Mark selected stocks as active."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} stocks marked as active.")
    mark_active.short_description = "Mark selected stocks as active"
    
    def mark_inactive(self, request, queryset):
        """Mark selected stocks as inactive."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} stocks marked as inactive.")
    mark_inactive.short_description = "Mark selected stocks as inactive"
    
    def update_prices(self, request, queryset):
        """Update prices for selected stocks."""
        # This would trigger a price update task
        self.message_user(request, f"Price update queued for {queryset.count()} stocks.")
    update_prices.short_description = "Update prices for selected stocks"


@admin.register(PriceData)
class PriceDataAdmin(admin.ModelAdmin):
    """Admin for price data."""
    
    list_display = [
        'stock',
        'date',
        'open_price',
        'close_price',
        'volume_display',
        'daily_return_display'
    ]
    
    list_filter = ['date', 'stock__sector']
    search_fields = ['stock__symbol', 'stock__name']
    raw_id_fields = ['stock']
    ordering = ['-date', 'stock']
    date_hierarchy = 'date'
    
    def volume_display(self, obj):
        """Display volume with formatting."""
        return format_html('{:,}', obj.volume)
    volume_display.short_description = 'Volume'
    
    def daily_return_display(self, obj):
        """Display daily return as percentage."""
        ret = obj.daily_return
        if ret is not None:
            color = 'green' if ret > 0 else 'red'
            return format_html(
                '<span style="color: {};">{:.2%}</span>',
                color,
                ret
            )
        return '-'
    daily_return_display.short_description = 'Daily Return'