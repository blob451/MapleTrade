"""
Serializers for analytics API endpoints.

Provides serialization/deserialization for analytics models and
custom serializers for analysis requests and responses.
"""

from rest_framework import serializers
from decimal import Decimal

from core.serializers import StockSerializer, SectorSerializer
from users.serializers import UserSerializer
from .models import StockAnalysis, TechnicalIndicator, RecommendationHistory, SectorAnalysis


class StockAnalysisSerializer(serializers.ModelSerializer):
    """Detailed serializer for StockAnalysis model."""
    
    stock = StockSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    signal_display = serializers.CharField(source='get_signal_display', read_only=True)
    formatted_returns = serializers.SerializerMethodField()
    
    class Meta:
        model = StockAnalysis
        fields = [
            'id', 'stock', 'user', 'sector_etf', 'created_at',
            'analysis_period_months', 'analysis_end_date',
            'signal', 'signal_display', 'confidence_score',
            'stock_return', 'sector_return', 'relative_performance',
            'volatility', 'volatility_threshold', 'is_high_volatility',
            'current_price', 'analyst_target', 'target_upside',
            'outperformed_sector', 'positive_analyst_outlook',
            'rationale', 'rationale_details', 'formatted_returns',
            'analysis_duration_ms', 'data_quality_score'
        ]
        read_only_fields = ['id', 'created_at', 'relative_performance', 
                           'target_upside', 'is_high_volatility']
    
    def get_formatted_returns(self, obj):
        """Format returns as percentages."""
        return {
            'stock_return': f"{float(obj.stock_return) * 100:.2f}%",
            'sector_return': f"{float(obj.sector_return) * 100:.2f}%",
            'relative_performance': f"{float(obj.relative_performance) * 100:.2f}%",
            'volatility': f"{float(obj.volatility) * 100:.2f}%"
        }


class StockAnalysisListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing analyses."""
    
    stock_symbol = serializers.CharField(source='stock.symbol', read_only=True)
    stock_name = serializers.CharField(source='stock.name', read_only=True)
    
    class Meta:
        model = StockAnalysis
        fields = [
            'id', 'stock_symbol', 'stock_name', 'signal', 
            'confidence_score', 'created_at', 'relative_performance'
        ]


class AnalysisRequestSerializer(serializers.Serializer):
    """Serializer for analysis request parameters."""
    
    symbol = serializers.CharField(max_length=10, required=True)
    months = serializers.IntegerField(min_value=1, max_value=60, default=6)
    force_refresh = serializers.BooleanField(default=False, required=False)
    
    def validate_symbol(self, value):
        """Validate and clean symbol."""
        return value.upper().strip()


class TechnicalIndicatorSerializer(serializers.ModelSerializer):
    """Serializer for technical indicators."""
    
    stock_symbol = serializers.CharField(source='stock.symbol', read_only=True)
    signals = serializers.SerializerMethodField()
    
    class Meta:
        model = TechnicalIndicator
        fields = [
            'id', 'stock_symbol', 'date',
            'sma_20', 'sma_50', 'sma_200',
            'ema_12', 'ema_26',
            'rsi_14', 'macd', 'macd_signal', 'macd_histogram',
            'bollinger_upper', 'bollinger_middle', 'bollinger_lower',
            'volume_sma_20', 'signals'
        ]
    
    def get_signals(self, obj):
        """Generate trading signals from indicators."""
        signals = []
        
        # RSI signals
        if obj.rsi_14:
            if obj.rsi_14 > 70:
                signals.append({'indicator': 'RSI', 'signal': 'OVERBOUGHT'})
            elif obj.rsi_14 < 30:
                signals.append({'indicator': 'RSI', 'signal': 'OVERSOLD'})
        
        # MACD signals
        if obj.macd and obj.macd_signal:
            if obj.macd > obj.macd_signal:
                signals.append({'indicator': 'MACD', 'signal': 'BULLISH'})
            else:
                signals.append({'indicator': 'MACD', 'signal': 'BEARISH'})
        
        return signals


class RecommendationHistorySerializer(serializers.ModelSerializer):
    """Serializer for recommendation history."""
    
    stock = StockSerializer(read_only=True)
    analysis_result = StockAnalysisListSerializer(read_only=True)
    
    class Meta:
        model = RecommendationHistory
        fields = [
            'id', 'stock', 'previous_signal', 'new_signal',
            'change_reason', 'price_at_change', 'created_at',
            'analysis_result'
        ]


class SectorAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for sector analysis."""
    
    sector = SectorSerializer(read_only=True)
    signal_distribution = serializers.SerializerMethodField()
    
    class Meta:
        model = SectorAnalysis
        fields = [
            'id', 'sector', 'analysis_date',
            'avg_return', 'avg_volatility',
            'buy_count', 'hold_count', 'sell_count',
            'signal_distribution', 'top_performers'
        ]
    
    def get_signal_distribution(self, obj):
        """Calculate signal distribution percentages."""
        total = obj.buy_count + obj.hold_count + obj.sell_count
        if total == 0:
            return {'buy': 0, 'hold': 0, 'sell': 0}
        
        return {
            'buy': round((obj.buy_count / total) * 100, 1),
            'hold': round((obj.hold_count / total) * 100, 1),
            'sell': round((obj.sell_count / total) * 100, 1)
        }


class PortfolioAnalysisSerializer(serializers.Serializer):
    """Serializer for portfolio analysis results."""
    
    total_stocks = serializers.IntegerField()
    analyzed = serializers.IntegerField()
    recommendations = serializers.DictField()
    analyses = StockAnalysisListSerializer(many=True)
    
    portfolio_metrics = serializers.SerializerMethodField()
    
    def get_portfolio_metrics(self, obj):
        """Calculate portfolio-level metrics."""
        if not obj.get('analyses'):
            return {}
        
        analyses = obj['analyses']
        avg_confidence = sum(a.confidence_score for a in analyses) / len(analyses)
        
        # Calculate weighted average return
        total_return = sum(
            float(a.stock_return) for a in analyses
        ) / len(analyses)
        
        return {
            'average_confidence': float(avg_confidence),
            'average_return': f"{total_return * 100:.2f}%",
            'high_confidence_picks': sum(
                1 for a in analyses 
                if a.confidence_score >= Decimal('0.75')
            )
        }


class BatchAnalysisRequestSerializer(serializers.Serializer):
    """Serializer for batch analysis requests."""
    
    symbols = serializers.ListField(
        child=serializers.CharField(max_length=10),
        min_length=1,
        max_length=20
    )
    months = serializers.IntegerField(min_value=1, max_value=60, default=6)
    
    def validate_symbols(self, value):
        """Validate and clean symbols."""
        return [s.upper().strip() for s in value]