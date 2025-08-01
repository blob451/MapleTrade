"""
Serializers for users app.

Provides serialization for User model and related functionality.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer."""
    
    full_name = serializers.SerializerMethodField()
    analysis_count = serializers.IntegerField(
        source='total_analyses_count', 
        read_only=True
    )
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'full_name', 'created_at', 'last_analysis_date',
            'analysis_count', 'is_premium', 'risk_tolerance',
            'default_analysis_period'
        ]
        read_only_fields = [
            'id', 'created_at', 'last_analysis_date', 
            'analysis_count'
        ]
    
    def get_full_name(self, obj):
        """Get user's full name."""
        if obj.first_name and obj.last_name:
            return f"{obj.first_name} {obj.last_name}"
        return obj.username


class UserProfileSerializer(serializers.ModelSerializer):
    """Detailed user profile serializer."""
    
    portfolios = serializers.SerializerMethodField()
    recent_analyses = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'created_at', 'updated_at', 'last_analysis_date',
            'total_analyses_count', 'is_premium', 'risk_tolerance',
            'default_analysis_period', 'is_active_user',
            'portfolios', 'recent_analyses'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_active_user']
    
    def get_portfolios(self, obj):
        """Get user's portfolios."""
        from core.serializers import UserPortfolioSerializer
        portfolios = obj.portfolios.all()
        return UserPortfolioSerializer(portfolios, many=True).data
    
    def get_recent_analyses(self, obj):
        """Get user's recent analyses."""
        # Avoid circular import
        from analytics.serializers import StockAnalysisListSerializer
        recent = obj.analyses.order_by('-created_at')[:5]
        return StockAnalysisListSerializer(recent, many=True).data


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'risk_tolerance',
            'default_analysis_period'
        ]
    
    def validate(self, attrs):
        """Validate passwords match."""
        password = attrs.get('password')
        password_confirm = attrs.pop('password_confirm', None)
        
        if password != password_confirm:
            raise serializers.ValidationError("Passwords don't match")
        
        return attrs
    
    def create(self, validated_data):
        """Create user with encrypted password."""
        password = validated_data.pop('password')
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        return user


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change."""
    
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True)
    
    def validate(self, attrs):
        """Validate password change."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match")
        
        return attrs
    
    def validate_old_password(self, value):
        """Validate old password is correct."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value


class UserPreferencesSerializer(serializers.ModelSerializer):
    """Serializer for user preferences."""
    
    class Meta:
        model = User
        fields = [
            'risk_tolerance', 'default_analysis_period', 'is_premium'
        ]