from django.contrib import admin

# Register your models here.
"""
Admin configuration for Analytics models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg
from .models import StockAnalysis, TechnicalIndicator, RecommendationHistory, SectorAnalysis


@admin.register(StockAnalysis)
class StockAnalysisAdmin(admin.ModelAdmin):
    """Admin interface for StockAnalysis model."""
    
    list_display = [
        'stock_symbol', 
        'signal_badge', 
        'confidence_score', 
        'relative_performance_display',
        'created_at', 
        'user'
    ]
    list_filter = [
        'signal', 
        'created_at', 
        'is_high_volatility',
        'analysis_period_months'
    ]
    search_fields = [
        'stock__symbol', 
        'stock__name', 
        'user__username',
        'user__email'
    ]
    date_hierarchy = 'created_at'
    readonly_fields = [
        'created_at', 
        'updated_at', 
        'relative_performance', 
        'target_upside',
        'is_high_volatility',
        'signal_strength_display'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'user', 
                'stock', 
                'sector_etf', 
                'analysis_period_months', 
                'analysis_end_date'
            )
        }),
        ('Analysis Results', {
            'fields': (
                'signal', 
                'confidence_score', 
                'signal_strength_display',
                'rationale'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'stock_return', 
                'sector_return', 
                'relative_performance', 
                'current_price', 
                'analyst_target', 
                'target_upside'
            )
        }),
        ('Risk Analysis', {
            'fields': (
                'volatility', 
                'volatility_threshold', 
                'is_high_volatility'
            )
        }),
        ('Signal Components', {
            'fields': (
                'outperformed_sector', 
                'positive_analyst_outlook'
            ),
            'classes': ('collapse',)
        }),
        ('Technical Details', {
            'fields': (
                'analysis_data',
                'rationale_details',
                'analysis_duration_ms', 
                'data_quality_score'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def stock_symbol(self, obj):
        """Display stock symbol as link to stock admin."""
        url = reverse('admin:core_stock_change', args=[obj.stock.pk])
        return format_html('<a href="{}">{}</a>', url, obj.stock.symbol)
    stock_symbol.short_description = 'Stock'
    stock_symbol.admin_order_field = 'stock__symbol'
    
    def signal_badge(self, obj):
        """Display signal with color coding."""
        colors = {
            'BUY': 'green',
            'SELL': 'red',
            'HOLD': 'orange'
        }
        color = colors.get(obj.signal, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.signal
        )
    signal_badge.short_description = 'Signal'
    signal_badge.admin_order_field = 'signal'
    
    def relative_performance_display(self, obj):
        """Display relative performance with color."""
        if obj.relative_performance is None:
            return '-'
        
        value = float(obj.relative_performance) * 100
        color = 'green' if value > 0 else 'red' if value < 0 else 'gray'
        return format_html(
            '<span style="color: {};">{:+.2f}%</span>',
            color, value
        )
    relative_performance_display.short_description = 'Rel. Performance'
    relative_performance_display.admin_order_field = 'relative_performance'
    
    def signal_strength_display(self, obj):
        """Display signal strength as percentage."""
        return f"{obj.signal_strength * 100:.0f}%"
    signal_strength_display.short_description = 'Signal Strength'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('stock', 'user')


@admin.register(TechnicalIndicator)
class TechnicalIndicatorAdmin(admin.ModelAdmin):
    """Admin interface for TechnicalIndicator model."""
    
    list_display = [
        'stock_symbol', 
        'date', 
        'rsi_display', 
        'macd_display',
        'moving_average_status'
    ]
    list_filter = ['date', 'stock__sector']
    search_fields = ['stock__symbol', 'stock__name']
    date_hierarchy = 'date'
    ordering = ['-date', 'stock__symbol']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('stock', 'date')
        }),
        ('Moving Averages', {
            'fields': ('sma_20', 'sma_50', 'sma_200', 'ema_12', 'ema_26')
        }),
        ('Momentum Indicators', {
            'fields': ('rsi_14', 'macd', 'macd_signal', 'macd_histogram')
        }),
        ('Volatility Indicators', {
            'fields': ('bollinger_upper', 'bollinger_middle', 'bollinger_lower')
        }),
        ('Volume', {
            'fields': ('volume_sma_20',)
        }),
    )
    
    def stock_symbol(self, obj):
        """Display stock symbol."""
        return obj.stock.symbol
    stock_symbol.short_description = 'Symbol'
    stock_symbol.admin_order_field = 'stock__symbol'
    
    def rsi_display(self, obj):
        """Display RSI with color coding."""
        if obj.rsi_14 is None:
            return '-'
        
        rsi = float(obj.rsi_14)
        if rsi > 70:
            color = 'red'
            status = 'OB'  # Overbought
        elif rsi < 30:
            color = 'green'
            status = 'OS'  # Oversold
        else:
            color = 'gray'
            status = ''
        
        return format_html(
            '<span style="color: {};">{:.1f} {}</span>',
            color, rsi, status
        )
    rsi_display.short_description = 'RSI'
    rsi_display.admin_order_field = 'rsi_14'
    
    def macd_display(self, obj):
        """Display MACD histogram with color."""
        if obj.macd_histogram is None:
            return '-'
        
        value = float(obj.macd_histogram)
        color = 'green' if value > 0 else 'red'
        return format_html(
            '<span style="color: {};">{:+.3f}</span>',
            color, value
        )
    macd_display.short_description = 'MACD Hist'
    macd_display.admin_order_field = 'macd_histogram'
    
    def moving_average_status(self, obj):
        """Show position relative to moving averages."""
        # This would need current price data to be meaningful
        # For now, just show if data exists
        if obj.sma_50 and obj.sma_200:
            return '✓ Data'
        return '- Partial'
    moving_average_status.short_description = 'MA Status'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related('stock')


@admin.register(RecommendationHistory)
class RecommendationHistoryAdmin(admin.ModelAdmin):
    """Admin interface for RecommendationHistory model."""
    
    list_display = [
        'stock_symbol', 
        'signal_change_display', 
        'price_at_change',
        'created_at'
    ]
    list_filter = [
        'new_signal', 
        'previous_signal',
        'created_at'
    ]
    search_fields = [
        'stock__symbol', 
        'stock__name',
        'change_reason'
    ]
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Signal Change', {
            'fields': (
                'stock',
                'previous_signal', 
                'new_signal',
                'price_at_change'
            )
        }),
        ('Details', {
            'fields': (
                'change_reason',
                'analysis_result'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def stock_symbol(self, obj):
        """Display stock symbol."""
        return obj.stock.symbol
    stock_symbol.short_description = 'Stock'
    stock_symbol.admin_order_field = 'stock__symbol'
    
    def signal_change_display(self, obj):
        """Display signal change with arrows and colors."""
        colors = {
            'BUY': 'green',
            'SELL': 'red',
            'HOLD': 'orange'
        }
        
        prev_color = colors.get(obj.previous_signal, 'gray')
        new_color = colors.get(obj.new_signal, 'gray')
        
        return format_html(
            '<span style="color: {};">{}</span> → <span style="color: {};">{}</span>',
            prev_color, obj.previous_signal or 'None',
            new_color, obj.new_signal
        )
    signal_change_display.short_description = 'Signal Change'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related(
            'stock', 
            'analysis_result'
        )


@admin.register(SectorAnalysis)
class SectorAnalysisAdmin(admin.ModelAdmin):
    """Admin interface for SectorAnalysis model."""
    
    list_display = [
        'sector_name',
        'analysis_date',
        'signal_distribution',
        'avg_return_display',
        'avg_volatility_display'
    ]
    list_filter = ['sector', 'analysis_date']
    date_hierarchy = 'analysis_date'
    search_fields = ['sector__name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('sector', 'analysis_date')
        }),
        ('Aggregate Metrics', {
            'fields': (
                'avg_return',
                'avg_volatility'
            )
        }),
        ('Signal Distribution', {
            'fields': (
                'buy_count',
                'hold_count',
                'sell_count'
            )
        }),
        ('Top Performers', {
            'fields': ('top_performers',),
            'classes': ('collapse',)
        }),
    )
    
    def sector_name(self, obj):
        """Display sector name."""
        return obj.sector.name
    sector_name.short_description = 'Sector'
    sector_name.admin_order_field = 'sector__name'
    
    def signal_distribution(self, obj):
        """Display signal distribution as a bar chart."""
        total = obj.buy_count + obj.hold_count + obj.sell_count
        if total == 0:
            return 'No data'
        
        buy_pct = (obj.buy_count / total) * 100
        hold_pct = (obj.hold_count / total) * 100
        sell_pct = (obj.sell_count / total) * 100
        
        return format_html(
            '<span style="color: green;">B:{}</span> | '
            '<span style="color: orange;">H:{}</span> | '
            '<span style="color: red;">S:{}</span>',
            obj.buy_count, obj.hold_count, obj.sell_count
        )
    signal_distribution.short_description = 'Signals (B/H/S)'
    
    def avg_return_display(self, obj):
        """Display average return with color."""
        if obj.avg_return is None:
            return '-'
        
        value = float(obj.avg_return) * 100
        color = 'green' if value > 0 else 'red' if value < 0 else 'gray'
        return format_html(
            '<span style="color: {};">{:+.2f}%</span>',
            color, value
        )
    avg_return_display.short_description = 'Avg Return'
    avg_return_display.admin_order_field = 'avg_return'
    
    def avg_volatility_display(self, obj):
        """Display average volatility."""
        if obj.avg_volatility is None:
            return '-'
        
        return f"{float(obj.avg_volatility) * 100:.1f}%"
    avg_volatility_display.short_description = 'Avg Volatility'
    avg_volatility_display.admin_order_field = 'avg_volatility'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related('sector')


# Customize admin site header
admin.site.site_header = "MapleTrade Analytics Admin"
admin.site.site_title = "MapleTrade Analytics"
admin.site.index_title = "Analytics Dashboard"