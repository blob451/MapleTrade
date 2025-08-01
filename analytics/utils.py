"""
Utility functions for analytics module.

Provides helper functions for financial calculations, data formatting,
and common operations used throughout the analytics module.
"""

import hashlib
from typing import Optional, Union
from decimal import Decimal
import pandas as pd
import numpy as np


def calculate_returns(prices: pd.Series) -> float:
    """
    Calculate total return from a price series.
    
    Args:
        prices: Pandas Series of prices
        
    Returns:
        Total return as a decimal (0.1 = 10%)
    """
    if len(prices) < 2:
        return 0.0
    
    return (prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0]


def calculate_annualized_volatility(prices: pd.Series, periods: int = 252) -> float:
    """
    Calculate annualized volatility from price series.
    
    Args:
        prices: Pandas Series of prices
        periods: Number of periods per year (252 for daily data)
        
    Returns:
        Annualized volatility as a decimal
    """
    if len(prices) < 2:
        return 0.0
    
    # Calculate daily returns
    returns = prices.pct_change().dropna()
    
    # Calculate standard deviation and annualize
    daily_vol = returns.std()
    annual_vol = daily_vol * np.sqrt(periods)
    
    return annual_vol


def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate all technical indicators for a price DataFrame.
    
    Args:
        df: DataFrame with columns: open, high, low, close, volume
        
    Returns:
        DataFrame with additional indicator columns
    """
    # Simple Moving Averages
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['sma_200'] = df['close'].rolling(window=200).mean()
    
    # Exponential Moving Averages
    df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
    
    # MACD
    df['macd'] = df['ema_12'] - df['ema_26']
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    # RSI
    df['rsi_14'] = calculate_rsi(df['close'], 14)
    
    # Bollinger Bands
    df['bb_middle'] = df['sma_20']
    bb_std = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    
    # Volume indicators
    df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
    
    return df


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index.
    
    Args:
        prices: Price series
        period: RSI period (typically 14)
        
    Returns:
        RSI series
    """
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """
    Calculate Sharpe ratio for a returns series.
    
    Args:
        returns: Series of returns
        risk_free_rate: Annual risk-free rate
        
    Returns:
        Sharpe ratio
    """
    if len(returns) < 2:
        return 0.0
    
    # Convert risk-free rate to daily
    daily_rf = risk_free_rate / 252
    
    # Calculate excess returns
    excess_returns = returns - daily_rf
    
    # Calculate Sharpe ratio
    if excess_returns.std() == 0:
        return 0.0
    
    return np.sqrt(252) * (excess_returns.mean() / excess_returns.std())


def format_percentage(value: Union[Decimal, float], decimals: int = 2) -> str:
    """
    Format a decimal as a percentage string.
    
    Args:
        value: Decimal value (0.1 = 10%)
        decimals: Number of decimal places
        
    Returns:
        Formatted percentage string
    """
    if value is None:
        return "N/A"
    
    percentage = float(value) * 100
    return f"{percentage:.{decimals}f}%"


def format_currency(value: Union[Decimal, float], symbol: str = "$") -> str:
    """
    Format a value as currency.
    
    Args:
        value: Numeric value
        symbol: Currency symbol
        
    Returns:
        Formatted currency string
    """
    if value is None:
        return "N/A"
    
    return f"{symbol}{float(value):,.2f}"


def get_analysis_cache_key(symbol: str, months: int) -> str:
    """
    Generate cache key for analysis results.
    
    Args:
        symbol: Stock symbol
        months: Analysis period in months
        
    Returns:
        Cache key string
    """
    return f"analysis:{symbol.upper()}:{months}m"


def get_indicator_cache_key(symbol: str, date: str) -> str:
    """
    Generate cache key for technical indicators.
    
    Args:
        symbol: Stock symbol
        date: Date string
        
    Returns:
        Cache key string
    """
    return f"indicators:{symbol.upper()}:{date}"


def validate_analysis_period(months: int) -> int:
    """
    Validate and constrain analysis period.
    
    Args:
        months: Requested analysis period
        
    Returns:
        Valid analysis period in months
    """
    MIN_MONTHS = 1
    MAX_MONTHS = 60
    
    return max(MIN_MONTHS, min(months, MAX_MONTHS))


def calculate_position_size(
    portfolio_value: Decimal,
    risk_percentage: Decimal,
    stop_loss_percentage: Decimal
) -> Decimal:
    """
    Calculate position size based on Kelly Criterion.
    
    Args:
        portfolio_value: Total portfolio value
        risk_percentage: Risk per trade (e.g., 0.02 for 2%)
        stop_loss_percentage: Stop loss percentage (e.g., 0.05 for 5%)
        
    Returns:
        Recommended position size
    """
    if stop_loss_percentage == 0:
        return Decimal('0')
    
    risk_amount = portfolio_value * risk_percentage
    position_size = risk_amount / stop_loss_percentage
    
    # Cap at 25% of portfolio
    max_position = portfolio_value * Decimal('0.25')
    
    return min(position_size, max_position)


def identify_support_resistance(prices: pd.Series, window: int = 20) -> dict:
    """
    Identify support and resistance levels.
    
    Args:
        prices: Price series
        window: Window for identifying levels
        
    Returns:
        Dictionary with support and resistance levels
    """
    if len(prices) < window * 2:
        return {'support': [], 'resistance': []}
    
    # Find local minima and maxima
    rolling_min = prices.rolling(window=window, center=True).min()
    rolling_max = prices.rolling(window=window, center=True).max()
    
    support_levels = prices[prices == rolling_min].unique()
    resistance_levels = prices[prices == rolling_max].unique()
    
    return {
        'support': sorted(support_levels)[-3:],  # Top 3 support levels
        'resistance': sorted(resistance_levels)[:3]  # Bottom 3 resistance levels
    }