"""
Admin configuration for analytics models.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import AnalysisResult, StockAnalysis, TechnicalIndicator, RecommendationHistory, SectorAnalysis


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    """Admin for analysis results."""
    
    list_display = [
        'stock',
        'analysis_date',
        'signal_display',
        'confidence',
        'outperformed_sector',
        'target_above_price',
        'volatility_below_threshold',
        'is_recent'
    ]
    
    list_filter = [
        'signal',
        'outperformed_sector',
        'target_above_price',
        'volatility_below_threshold',
        'analysis_date'
    ]
    
    search_fields = ['stock__symbol', 'stock__name', 'rationale']
    raw_id_fields = ['stock']
    ordering = ['-analysis_date']
    date_hierarchy = 'analysis_date'
    
    readonly_fields = [
        'is_recent',
        'target_upside',
        'conditions_met_count',
        'is_strong_signal',
        'conditions_summary',
        'outperformance'
    ]
    
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
            'fields': (
                'outperformed_sector',
                'target_above_price',
                'volatility_below_threshold',
                'conditions_met_count',
                'is_strong_signal',
                'conditions_summary'
            )
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


# Register other analytics models with basic admin
admin.site.register(StockAnalysis)
admin.site.register(TechnicalIndicator)
admin.site.register(RecommendationHistory)
admin.site.register(SectorAnalysis)