"""
User forms for registration, profile, and portfolio management.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from users.models import User, UserPortfolio, PortfolioStock


class UserRegistrationForm(UserCreationForm):
    """User registration form."""
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    """User profile form."""
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone_number', 
                 'date_of_birth', 'risk_tolerance', 'default_analysis_period')
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }


class PortfolioForm(forms.ModelForm):
    """Portfolio creation/edit form."""
    class Meta:
        model = UserPortfolio
        fields = ('name', 'description')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class PortfolioStockForm(forms.ModelForm):
    """Form for adding stocks to portfolio."""
    symbol = forms.CharField(
        max_length=10,
        help_text='Stock ticker symbol (e.g., AAPL)'
    )
    
    class Meta:
        model = PortfolioStock
        fields = ('symbol', 'shares', 'purchase_price', 'added_date')
        widgets = {
            'added_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
        labels = {
            'shares': 'Quantity',
            'added_date': 'Purchase Date',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.stock:
            self.fields['symbol'].initial = self.instance.stock.symbol