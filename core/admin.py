"""
Django admin configuration for MapleTrade core models.

Provides a user-friendly interface for managing stocks, sectors,
and viewing analysis results.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import Sector, Stock, PriceData, AnalysisResult, UserPortfolio, PortfolioStock


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    """Admin interface for Sector model."""
    
    list_display = [
        'code', 'name', 'etf_symbol', 'volatility_threshold', 
        'risk_category', 'is_defensive', 'stock_count'
    ]
    list_filter = ['volatility_threshold', 'created_at']
    search_fields = ['name', 'code', 'etf_symbol']
    readonly_fields = ['created_at', 'updated_at', 'stock_count']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description')
        }),
        ('ETF Mapping', {
            'fields': ('etf_symbol', 'volatility_threshold')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'stock_count'),
            'classes': ('collapse',)
        })
    )
    
    def stock_count(self, obj):
        """Show number of stocks in this sector."""
        count = obj.stock_set.count()
        if count > 0:
            url = reverse('admin:core_stock_changelist') + f'?sector__id__exact={obj.id}'
            return format_html('<a href="{}">{} stocks</a>', url, count)
        return '0 stocks'
    stock_count.short_description = 'Stocks'
    
    def risk_category(self, obj):
        """Display risk category with color coding."""
        category = obj.risk_category
        colors = {
            'LOW_RISK': 'green',
            'MEDIUM_RISK': 'orange', 
            'HIGH_RISK': 'red'
        }
        color = colors.get(category, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, category.replace('_', ' ')
        )
    risk_category.short_description = 'Risk Level'


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    """Admin interface for Stock model."""
    
    list_display = [
        'symbol', 'name', 'sector', 'current_price', 'target_price',
        'target_upside_display', 'last_updated', 'is_active', 'latest_analysis'
    ]
    list_filter = ['sector', 'is_active', 'exchange', 'currency', 'last_updated']
    search_fields = ['symbol', 'name']
    readonly_fields = ['created_at', 'updated_at', 'target_upside', 'needs_update', 'latest_analysis']
    
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
        ('Analysis', {
            'fields': ('latest_analysis',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['mark_for_update', 'mark_inactive']
    
    def target_upside_display(self, obj):
        """Display target upside with color coding."""
        upside = obj.target_upside
        if upside is None:
            return '-'
        
        color = 'green' if upside > 0 else 'red' if upside < 0 else 'orange'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:+.1%}</span>',
            color, upside
        )
    target_upside_display.short_description = 'Target Upside'
    
    def latest_analysis(self, obj):
        """Show link to latest analysis result."""
        latest = obj.analysis_results.first()
        if latest:
            url = reverse('admin:core_analysisresult_change', args=[latest.id])
            return format_html(
                '<a href="{}">{} ({})</a>',
                url, latest.signal, latest.analysis_date.date()
            )
        return 'No analysis'
    latest_analysis.short_description = 'Latest Analysis'
    
    def mark_for_update(self, request, queryset):
        """Mark selected stocks for data update."""
        queryset.update(last_updated=None)
        self.message_user(request, f'{queryset.count()} stocks marked for update.')
    mark_for_update.short_description = 'Mark selected stocks for data update'
    
    def mark_inactive(self, request, queryset):
        """Mark selected stocks as inactive."""
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} stocks marked as inactive.')
    mark_inactive.short_description = 'Mark selected stocks as inactive'


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    """Admin interface for AnalysisResult model."""
    
    list_display = [
        'stock', 'signal_display', 'confidence', 'analysis_date',
        'outperformance_display', 'volatility_display', 'conditions_met_display',
        'sector_name'
    ]
    list_filter = [
        'signal', 'confidence', 'analysis_date', 'outperformed_sector',
        'target_above_price', 'volatility_below_threshold', 'sector_name'
    ]
    search_fields = ['stock__symbol', 'stock__name', 'sector_name']
    readonly_fields = [
        'created_at', 'updated_at', 'target_upside', 'conditions_met_count',
        'is_strong_signal', 'conditions_summary'
    ]
    date_hierarchy = 'analysis_date'
    
    fieldsets = (
        ('Analysis Summary', {
            'fields': (
                'stock', 'signal', 'confidence', 'analysis_date',
                'analysis_period_months', 'engine_version'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'stock_return', 'sector_return', 'outperformance', 
                'volatility', 'current_price', 'target_price', 'target_upside'
            )
        }),
        ('Signal Breakdown', {
            'fields': (
                'outperformed_sector', 'target_above_price', 'volatility_below_threshold',
                'conditions_met_count', 'is_strong_signal'
            )
        }),
        ('Sector Context', {
            'fields': (
                'sector_name', 'sector_etf', 'sector_volatility_threshold'
            )
        }),
        ('Analysis Details', {
            'fields': ('rationale', 'conditions_summary')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def signal_display(self, obj):
        """Display signal with color coding."""
        colors = {
            'BUY': 'green',
            'SELL': 'red', 
            'HOLD': 'orange'
        }
        color = colors.get(obj.signal, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold; font-size: 14px;">{}</span>',
            color, obj.signal
        )
    signal_display.short_description = 'Signal'
    
    def outperformance_display(self, obj):
        """Display outperformance with color coding."""
        value = float(obj.outperformance)
        color = 'green' if value > 0 else 'red' if value < 0 else 'gray'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:+.1%}</span>',
            color, value
        )
    outperformance_display.short_description = 'Outperformance'
    
    def volatility_display(self, obj):
        """Display volatility with threshold comparison."""
        vol = float(obj.volatility)
        threshold = float(obj.sector_volatility_threshold)
        
        if vol <= threshold:
            color = 'green'
            status = '✓'
        else:
            color = 'red'
            status = '✗'
            
        return format_html(
            '<span style="color: {};">{} {:.1%}</span>',
            color, status, vol
        )
    volatility_display.short_description = 'Volatility'
    
    def conditions_met_display(self, obj):
        """Display conditions met as visual indicators."""
        conditions = [
            ('🎯', obj.outperformed_sector, 'Outperformed'),
            ('📈', obj.target_above_price, 'Target'),
            ('📊', obj.volatility_below_threshold, 'Volatility')
        ]
        
        icons = []
        for icon, met, tooltip in conditions:
            color = 'green' if met else 'lightgray'
            icons.append(f'<span style="color: {color};" title="{tooltip}">{icon}</span>')
        
        count = obj.conditions_met_count
        return format_html(
            '{} <small>({}/3)</small>',
            ' '.join(icons), count
        )
    conditions_met_display.short_description = 'Conditions'
    
    def conditions_summary(self, obj):
        """Display detailed conditions summary."""
        summary = obj.get_conditions_summary()
        html_parts = []
        
        for condition, met in summary.items():
            if condition == 'total_met':
                continue
            icon = '✅' if met else '❌'
            label = condition.replace('_', ' ').title()
            html_parts.append(f'{icon} {label}')
        
        return format_html('<br>'.join(html_parts))
    conditions_summary.short_description = 'Conditions Summary'


@admin.register(PriceData)  
class PriceDataAdmin(admin.ModelAdmin):
    """Admin interface for PriceData model."""
    
    list_display = [
        'stock', 'date', 'close_price', 'volume', 'daily_return_display'
    ]
    list_filter = ['date', 'stock__sector']
    search_fields = ['stock__symbol', 'stock__name']
    readonly_fields = ['created_at', 'updated_at', 'daily_return']
    date_hierarchy = 'date'
    
    def daily_return_display(self, obj):
        """Display daily return with color coding."""
        ret = obj.daily_return
        if ret is None:
            return '-'
        
        color = 'green' if ret > 0 else 'red' if ret < 0 else 'gray'
        return format_html(
            '<span style="color: {};">{:+.2%}</span>',
            color, ret
        )
    daily_return_display.short_description = 'Daily Return'


class PortfolioStockInline(admin.TabularInline):
    """Inline editor for portfolio stocks."""
    model = PortfolioStock
    extra = 0
    readonly_fields = ['current_value', 'unrealized_pnl', 'latest_analysis_link']
    
    def latest_analysis_link(self, obj):
        """Link to latest analysis for this stock."""
        if obj.stock:
            latest = obj.stock.analysis_results.first()
            if latest:
                url = reverse('admin:core_analysisresult_change', args=[latest.id])
                return format_html('<a href="{}">{}</a>', url, latest.signal)
        return '-'
    latest_analysis_link.short_description = 'Latest Analysis'


@admin.register(UserPortfolio)
class UserPortfolioAdmin(admin.ModelAdmin):
    """Admin interface for UserPortfolio model."""
    
    list_display = ['name', 'user', 'stock_count', 'is_default', 'created_at']
    list_filter = ['is_default', 'created_at', 'user']
    search_fields = ['name', 'user__username', 'description']
    inlines = [PortfolioStockInline]
    
    def stock_count(self, obj):
        """Show number of stocks in portfolio."""
        return obj.stocks.count()
    stock_count.short_description = 'Stocks'


# Custom admin site configuration
admin.site.site_header = 'MapleTrade Analytics Platform'
admin.site.site_title = 'MapleTrade Admin'
admin.site.index_title = 'Financial Analytics Administration'