"""
Admin configuration for core models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from django.utils import timezone

from .models import Sector, Stock, PriceData, AnalysisResult, UserPortfolio, PortfolioStock


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'etf_symbol', 'volatility_threshold', 'stock_count']
    list_filter = ['created_at']
    search_fields = ['name', 'code', 'etf_symbol']
    ordering = ['name']
    
    def stock_count(self, obj):
        return obj.stock_set.count()
    stock_count.short_description = 'Stocks'


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'sector', 'current_price', 'target_price', 
                    'price_change_indicator', 'is_active', 'last_updated']
    list_filter = ['sector', 'is_active', 'last_updated']
    search_fields = ['symbol', 'name']
    readonly_fields = ['last_updated', 'created_at', 'updated_at']
    autocomplete_fields = ['sector']
    ordering = ['symbol']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('symbol', 'name', 'sector', 'exchange', 'currency')
        }),
        ('Price Data', {
            'fields': ('current_price', 'target_price', 'market_cap')
        }),
        ('Status', {
            'fields': ('is_active', 'last_updated', 'created_at', 'updated_at')
        }),
    )
    
    def price_change_indicator(self, obj):
        if obj.current_price and obj.target_price:
            diff = obj.target_price - obj.current_price
            percent = (diff / obj.current_price) * 100
            color = 'green' if diff > 0 else 'red' if diff < 0 else 'gray'
            return format_html(
                '<span style="color: {};">{:+.2f}%</span>',
                color, percent
            )
        return '-'
    price_change_indicator.short_description = 'Target vs Current'


@admin.register(PriceData)
class PriceDataAdmin(admin.ModelAdmin):
    list_display = ['stock', 'date', 'open_price', 'close_price', 'volume']
    list_filter = ['date', 'stock__sector']
    search_fields = ['stock__symbol', 'stock__name']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-date', 'stock__symbol']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('stock', 'stock__sector')


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ['stock', 'signal', 'confidence', 'analysis_date', 
                    'outperformed_sector', 'target_above_current', 'low_volatility']
    list_filter = ['signal', 'analysis_date', 'outperformed_sector', 
                   'target_above_current', 'low_volatility']
    search_fields = ['stock__symbol', 'stock__name', 'rationale']
    readonly_fields = ['analysis_date', 'created_at', 'updated_at']
    date_hierarchy = 'analysis_date'
    ordering = ['-analysis_date']
    
    fieldsets = (
        ('Analysis Info', {
            'fields': ('stock', 'analysis_date', 'analysis_period_months')
        }),
        ('Recommendation', {
            'fields': ('signal', 'confidence', 'rationale')
        }),
        ('Three-Factor Signals', {
            'fields': ('outperformed_sector', 'target_above_current', 'low_volatility')
        }),
        ('Metrics', {
            'fields': ('stock_return', 'sector_return', 'volatility')
        }),
        ('Metadata', {
            'fields': ('is_valid', 'errors', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('stock', 'stock__sector')


class PortfolioStockInline(admin.TabularInline):
    model = PortfolioStock
    extra = 1
    fields = ['stock', 'shares', 'purchase_price', 'added_date', 'notes']
    readonly_fields = ['added_date']
    autocomplete_fields = ['stock']


@admin.register(UserPortfolio)
class UserPortfolioAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'is_default', 'stock_count', 'created_at']
    list_filter = ['is_default', 'created_at']
    search_fields = ['name', 'user__username', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [PortfolioStockInline]
    
    fieldsets = (
        ('Portfolio Info', {
            'fields': ('user', 'name', 'description', 'is_default')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def stock_count(self, obj):
        return obj.stocks.count()
    stock_count.short_description = 'Stocks'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user').annotate(
            stock_count_annotation=Count('stocks')
        )


@admin.register(PortfolioStock)
class PortfolioStockAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'stock', 'shares', 'purchase_price', 'added_date']
    list_filter = ['added_date', 'portfolio']
    search_fields = ['stock__symbol', 'stock__name', 'portfolio__name']
    readonly_fields = ['added_date', 'created_at', 'updated_at']
    autocomplete_fields = ['portfolio', 'stock']
    ordering = ['-added_date']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('portfolio', 'portfolio__user', 'stock', 'stock__sector')