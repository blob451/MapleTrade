"""
Serializers for MapleTrade core models.

This module provides Django REST Framework serializers for API endpoints.
"""

from rest_framework import serializers
from .models import Stock, Sector, AnalysisResult, PriceData, UserPortfolio, PortfolioStock


class SectorSerializer(serializers.ModelSerializer):
    """Serializer for Sector model."""
    
    risk_category = serializers.ReadOnlyField()
    is_defensive = serializers.ReadOnlyField()
    
    class Meta:
        model = Sector
        fields = [
            'id', 'name', 'code', 'description', 'etf_symbol',
            'volatility_threshold', 'risk_category', 'is_defensive',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class StockSerializer(serializers.ModelSerializer):
    """Serializer for Stock model."""
    
    sector = SectorSerializer(read_only=True)
    target_upside = serializers.ReadOnlyField()
    has_target_upside = serializers.ReadOnlyField()
    needs_update = serializers.ReadOnlyField()
    
    class Meta:
        model = Stock
        fields = [
            'id', 'symbol', 'name', 'sector', 'exchange', 'currency',
            'market_cap', 'current_price', 'target_price', 'target_upside',
            'has_target_upside', 'is_active', 'last_updated', 'needs_update',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'last_updated']


class AnalysisResultSerializer(serializers.ModelSerializer):
    """Serializer for AnalysisResult model."""
    
    stock = StockSerializer(read_only=True)
    target_upside = serializers.ReadOnlyField()
    conditions_met_count = serializers.ReadOnlyField()
    is_strong_signal = serializers.ReadOnlyField()
    conditions_summary = serializers.ReadOnlyField()
    
    class Meta:
        model = AnalysisResult
        fields = [
            'id', 'stock', 'analysis_date', 'analysis_period_months',
            'signal', 'confidence', 'stock_return', 'sector_return',
            'outperformance', 'volatility', 'current_price', 'target_price',
            'target_upside', 'outperformed_sector', 'target_above_price',
            'volatility_below_threshold', 'sector_name', 'sector_etf',
            'sector_volatility_threshold', 'rationale', 'engine_version',
            'conditions_met_count', 'is_strong_signal', 'conditions_summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PriceDataSerializer(serializers.ModelSerializer):
    """Serializer for PriceData model."""
    
    stock_symbol = serializers.CharField(source='stock.symbol', read_only=True)
    daily_return = serializers.ReadOnlyField()
    
    class Meta:
        model = PriceData
        fields = [
            'id', 'stock_symbol', 'date', 'open_price', 'high_price',
            'low_price', 'close_price', 'volume', 'adjusted_close',
            'daily_return', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PortfolioStockSerializer(serializers.ModelSerializer):
    """Serializer for PortfolioStock model."""
    
    stock = StockSerializer(read_only=True)
    current_value = serializers.ReadOnlyField()
    unrealized_pnl = serializers.ReadOnlyField()
    
    class Meta:
        model = PortfolioStock
        fields = [
            'id', 'stock', 'added_date', 'notes', 'shares',
            'purchase_price', 'current_value', 'unrealized_pnl',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class UserPortfolioSerializer(serializers.ModelSerializer):
    """Serializer for UserPortfolio model."""
    
    stocks_count = serializers.IntegerField(
        source='stocks.count', 
        read_only=True
    )
    
    class Meta:
        model = UserPortfolio
        fields = [
            'id', 'name', 'description', 'is_default',
            'created_at', 'stocks_count'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_stock_count(self, obj):
        """Get count of stocks in portfolio."""
        return obj.stocks.count()


# Simplified serializers for API responses
class SimpleStockSerializer(serializers.ModelSerializer):
    """Simplified stock serializer for list views."""
    
    sector_name = serializers.CharField(source='sector.name', read_only=True)
    sector_code = serializers.CharField(source='sector.code', read_only=True)
    
    class Meta:
        model = Stock
        fields = [
            'symbol', 'name', 'sector_name', 'sector_code',
            'current_price', 'target_price', 'is_active'
        ]


class SimpleAnalysisSerializer(serializers.ModelSerializer):
    """Simplified analysis serializer for list views."""
    
    stock_symbol = serializers.CharField(source='stock.symbol', read_only=True)
    
    class Meta:
        model = AnalysisResult
        fields = [
            'stock_symbol', 'signal', 'confidence', 'analysis_date',
            'stock_return', 'outperformance', 'volatility'
        ]


# Request/Response serializers for API endpoints
class AnalysisRequestSerializer(serializers.Serializer):
    """Serializer for analysis request data."""
    
    symbol = serializers.CharField(max_length=10, help_text="Stock ticker symbol")
    analysis_months = serializers.IntegerField(
        min_value=1, 
        max_value=60, 
        default=12,
        help_text="Analysis period in months"
    )
    
    def validate_symbol(self, value):
        """Validate and clean symbol."""
        return value.strip().upper()


class AnalysisResponseSerializer(serializers.Serializer):
    """Serializer for analysis response data."""
    
    success = serializers.BooleanField()
    cached = serializers.BooleanField()
    timestamp = serializers.DateTimeField()
    analysis = serializers.DictField()
    error = serializers.CharField(required=False)


class HealthCheckResponseSerializer(serializers.Serializer):
    """Serializer for health check response."""
    
    status = serializers.ChoiceField(choices=[('healthy', 'Healthy'), ('unhealthy', 'Unhealthy')])
    timestamp = serializers.DateTimeField()
    system = serializers.DictField()
    services = serializers.DictField()
    error = serializers.CharField(required=False)