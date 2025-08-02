"""
Admin configuration for MapleTrade core models.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Sector, Stock, PriceData, AnalysisResult, UserPortfolio, PortfolioStock


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'etf_symbol', 'volatility_threshold', 'risk_category')
    list_filter = ('code',)
    search_fields = ('name', 'code', 'etf_symbol')
    ordering = ('name',)
    
    def risk_category(self, obj):
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
    risk_category.short_description = 'Risk Level'


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name', 'sector', 'current_price', 'target_price', 
                   'target_upside_display', 'is_active', 'last_updated')
    list_filter = ('is_active', 'sector', 'exchange')
    search_fields = ('symbol', 'name')
    raw_id_fields = ('sector',)
    ordering = ('symbol',)
    date_hierarchy = 'last_updated'
    
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
    
    actions = ['mark_active', 'mark_inactive']
    
    def mark_active(self, request, queryset):
        queryset.update(is_active=True)
    mark_active.short_description = "Mark selected stocks as active"
    
    def mark_inactive(self, request, queryset):
        queryset.update(is_active=False)
    mark_inactive.short_description = "Mark selected stocks as inactive"


@admin.register(PriceData)
class PriceDataAdmin(admin.ModelAdmin):
    list_display = ('stock', 'date', 'open_price', 'close_price', 'volume', 'daily_return_display')
    list_filter = ('date', 'stock__sector')
    search_fields = ('stock__symbol', 'stock__name')
    raw_id_fields = ('stock',)
    ordering = ('-date', 'stock')
    date_hierarchy = 'date'
    
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


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ('stock', 'analysis_date', 'signal', 'confidence', 'outperformed_sector', 
                   'target_above_price', 'volatility_below_threshold', 'is_recent')
    list_filter = ('signal', 'outperformed_sector', 'target_above_price', 
                  'volatility_below_threshold', 'analysis_date')
    search_fields = ('stock__symbol', 'stock__name', 'rationale')
    raw_id_fields = ('stock',)
    ordering = ('-analysis_date',)
    date_hierarchy = 'analysis_date'
    
    readonly_fields = ('is_recent', 'target_upside', 'conditions_met_count', 
                      'is_strong_signal', 'conditions_summary')
    
    fieldsets = (
        ('Analysis Info', {
            'fields': ('stock', 'analysis_date', 'analysis_period_months')
        }),
        ('Recommendation', {
            'fields': ('signal', 'confidence', 'rationale')
        }),
        ('Performance Metrics', {
            'fields': ('stock_return', 'sector_return', 'outperformance', 'volatility')
        }),
        ('Price Information', {
            'fields': ('current_price', 'target_price', 'target_upside')
        }),
        ('Three-Factor Signals', {
            'fields': ('outperformed_sector', 'target_above_price', 'volatility_below_threshold',
                      'conditions_met_count', 'is_strong_signal', 'conditions_summary')
        }),
        ('Sector Information', {
            'fields': ('sector_name', 'sector_etf', 'sector_volatility_threshold')
        }),
        ('Metadata', {
            'fields': ('engine_version', 'is_valid', 'is_recent', 'errors', 'raw_data'),
            'classes': ('collapse',)
        })
    )
    
    def signal_display(self, obj):
        """Display signal with color coding."""
        colors = {
            'BUY': 'green',
            'HOLD': 'orange',
            'SELL': 'red'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.signal, 'black'),
            obj.signal
        )
    signal_display.short_description = 'Signal'


@admin.register(UserPortfolio)
class UserPortfolioAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_default', 'stock_count', 'created_at')
    list_filter = ('is_default', 'created_at')
    search_fields = ('name', 'user__username', 'description')
    raw_id_fields = ('user',)
    ordering = ('user', 'name')
    
    def stock_count(self, obj):
        """Display number of stocks in portfolio."""
        return obj.stocks.count()
    stock_count.short_description = 'Stocks'


class PortfolioStockInline(admin.TabularInline):
    model = PortfolioStock
    extra = 1
    raw_id_fields = ('stock',)
    readonly_fields = ('current_value', 'unrealized_pnl')


@admin.register(PortfolioStock)
class PortfolioStockAdmin(admin.ModelAdmin):
    list_display = ('portfolio', 'stock', 'shares', 'purchase_price', 
                   'current_value', 'unrealized_pnl', 'added_date')
    list_filter = ('added_date', 'portfolio')
    search_fields = ('stock__symbol', 'stock__name', 'portfolio__name')
    raw_id_fields = ('portfolio', 'stock')
    ordering = ('-added_date',)
    date_hierarchy = 'added_date'
    
    readonly_fields = ('current_value', 'unrealized_pnl')
    
    fieldsets = (
        ('Portfolio & Stock', {
            'fields': ('portfolio', 'stock', 'added_date')
        }),
        ('Position Details', {
            'fields': ('shares', 'purchase_price', 'current_value', 'unrealized_pnl')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('wide',)
        })
    )


# Customize admin site header
admin.site.site_header = 'MapleTrade Administration'
admin.site.site_title = 'MapleTrade Admin'
admin.site.index_title = 'Welcome to MapleTrade Administration'