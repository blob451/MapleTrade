"""
Financial calculation services for MapleTrade analytics engine.

This module provides calculation utilities for volatility, returns, and other
financial metrics used in the three-factor model.
"""

import math
import logging
from typing import List, Optional
from datetime import datetime
import pandas as pd
import numpy as np

from data.providers.base import PriceData

logger = logging.getLogger(__name__)


class CalculationError(Exception):
    """Custom exception for calculation errors."""
    pass


class ReturnCalculator:
    """
    Calculator for various return metrics.
    
    Provides methods for calculating total returns, period returns,
    and other return-based metrics used in the analytics engine.
    """
    
    def calculate_total_return(self, price_data: List[PriceData]) -> float:
        """
        Calculate total return over the price data period.
        
        Args:
            price_data: List of PriceData objects sorted by date
            
        Returns:
            Total return as decimal (e.g., 0.15 for 15% return)
            
        Raises:
            CalculationError: If insufficient data or calculation fails
        """
        if not price_data or len(price_data) < 2:
            raise CalculationError("Insufficient price data for return calculation")
            
        try:
            # Sort by date to ensure proper order
            sorted_data = sorted(price_data, key=lambda x: x.date)
            
            start_price = float(sorted_data[0].close_price)
            end_price = float(sorted_data[-1].close_price)
            
            if start_price <= 0:
                raise CalculationError("Invalid start price for return calculation")
                
            total_return = (end_price - start_price) / start_price
            
            logger.debug(f"Calculated return: {total_return:.4f} "
                        f"(${start_price:.2f} → ${end_price:.2f})")
            
            return total_return
            
        except (ValueError, IndexError, AttributeError) as e:
            raise CalculationError(f"Return calculation failed: {e}")
    
    def calculate_period_returns(self, price_data: List[PriceData]) -> List[float]:
        """
        Calculate period-over-period returns (daily returns).
        
        Args:
            price_data: List of PriceData objects sorted by date
            
        Returns:
            List of daily returns as decimals
        """
        if len(price_data) < 2:
            return []
            
        try:
            sorted_data = sorted(price_data, key=lambda x: x.date)
            returns = []
            
            for i in range(1, len(sorted_data)):
                prev_price = float(sorted_data[i-1].close_price)
                curr_price = float(sorted_data[i].close_price)
                
                if prev_price > 0:
                    daily_return = (curr_price - prev_price) / prev_price
                    returns.append(daily_return)
                    
            return returns
            
        except (ValueError, AttributeError) as e:
            raise CalculationError(f"Period returns calculation failed: {e}")


class VolatilityCalculator:
    """
    Calculator for volatility metrics.
    
    Provides methods for calculating annualized volatility, rolling volatility,
    and other risk metrics used in the analytics engine.
    """
    
    def calculate_annualized_volatility(self, price_data: List[PriceData], 
                                      trading_days_per_year: int = 252) -> float:
        """
        Calculate annualized volatility from historical price data.
        
        This method replicates the volatility calculation from the prototype:
        1. Calculate daily returns
        2. Calculate standard deviation of returns  
        3. Annualize using sqrt(trading_days)
        
        Args:
            price_data: List of PriceData objects
            trading_days_per_year: Number of trading days per year (default: 252)
            
        Returns:
            Annualized volatility as decimal (e.g., 0.25 for 25% volatility)
            
        Raises:
            CalculationError: If insufficient data or calculation fails
        """
        if not price_data or len(price_data) < 10:
            raise CalculationError("Insufficient data for volatility calculation (minimum 10 points)")
            
        try:
            return_calc = ReturnCalculator()
            daily_returns = return_calc.calculate_period_returns(price_data)
            
            if len(daily_returns) < 5:
                raise CalculationError("Insufficient returns for volatility calculation")
                
            # Calculate standard deviation of returns
            returns_array = np.array(daily_returns)
            daily_volatility = np.std(returns_array, ddof=1)  # Sample standard deviation
            
            # Annualize volatility
            annualized_vol = daily_volatility * math.sqrt(trading_days_per_year)
            
            logger.debug(f"Calculated annualized volatility: {annualized_vol:.4f} "
                        f"from {len(daily_returns)} daily returns")
            
            return float(annualized_vol)
            
        except (ValueError, TypeError) as e:
            raise CalculationError(f"Volatility calculation failed: {e}")
    
    def calculate_rolling_volatility(self, price_data: List[PriceData], 
                                   window_days: int = 30) -> List[float]:
        """
        Calculate rolling volatility over specified window.
        
        Args:
            price_data: List of PriceData objects sorted by date
            window_days: Rolling window size in days
            
        Returns:
            List of rolling volatility values
        """
        if len(price_data) < window_days + 5:
            return []
            
        try:
            return_calc = ReturnCalculator()
            daily_returns = return_calc.calculate_period_returns(price_data)
            
            rolling_vols = []
            
            for i in range(window_days - 1, len(daily_returns)):
                window_returns = daily_returns[i - window_days + 1:i + 1]
                
                if len(window_returns) == window_days:
                    window_vol = np.std(window_returns, ddof=1) * math.sqrt(252)
                    rolling_vols.append(float(window_vol))
                    
            return rolling_vols
            
        except Exception as e:
            logger.warning(f"Rolling volatility calculation failed: {e}")
            return []


class TechnicalCalculator:
    """
    Calculator for basic technical indicators.
    
    This is a foundation for future technical analysis expansion.
    Currently provides simple moving averages and basic indicators.
    """
    
    def calculate_sma(self, price_data: List[PriceData], period: int) -> List[float]:
        """Calculate Simple Moving Average."""
        if len(price_data) < period:
            return []
            
        sorted_data = sorted(price_data, key=lambda x: x.date)
        prices = [float(p.close_price) for p in sorted_data]        
        sma_values = []
        for i in range(period - 1, len(prices)):
            window_avg = sum(prices[i - period + 1:i + 1]) / period
            sma_values.append(window_avg)
            
        return sma_values
    
    def calculate_price_momentum(self, price_data: List[PriceData], 
                               lookback_days: int = 20) -> Optional[float]:
        """
        Calculate price momentum over lookback period.
        
        Returns the percentage change over the specified period.
        """
        if len(price_data) < lookback_days + 1:
            return None
            
        try:
            sorted_data = sorted(price_data, key=lambda x: x.date)
            
            current_price = float(sorted_data[-1].close)
            past_price = float(sorted_data[-lookback_days - 1].close)
            
            if past_price > 0:
                momentum = (current_price - past_price) / past_price
                return float(momentum)
                
        except (ValueError, IndexError):
            pass
            
        return None


class PerformanceMetrics:
    """
    Calculator for performance and risk metrics.
    
    Provides utilities for calculating Sharpe ratios, drawdowns,
    and other performance metrics for future use.
    """
    
    def calculate_sharpe_ratio(self, returns: List[float], 
                             risk_free_rate: float = 0.02) -> Optional[float]:
        """
        Calculate Sharpe ratio from returns.
        
        Args:
            returns: List of period returns
            risk_free_rate: Annual risk-free rate (default: 2%)
            
        Returns:
            Sharpe ratio or None if calculation fails
        """
        if not returns or len(returns) < 10:
            return None
            
        try:
            returns_array = np.array(returns)
            
            # Annualize returns (assuming daily returns)
            annual_return = np.mean(returns_array) * 252
            annual_volatility = np.std(returns_array, ddof=1) * math.sqrt(252)
            
            if annual_volatility == 0:
                return None
                
            sharpe = (annual_return - risk_free_rate) / annual_volatility
            return float(sharpe)
            
        except Exception:
            return None
    
    def calculate_max_drawdown(self, price_data: List[PriceData]) -> Optional[float]:
        """
        Calculate maximum drawdown from peak to trough.
        
        Returns:
            Maximum drawdown as negative decimal (e.g., -0.15 for 15% drawdown)
        """
        if len(price_data) < 2:
            return None
            
        try:
            sorted_data = sorted(price_data, key=lambda x: x.date)
            prices = [float(p.close_price) for p in sorted_data]            
            peak = prices[0]
            max_drawdown = 0.0
            
            for price in prices[1:]:
                if price > peak:
                    peak = price
                else:
                    drawdown = (price - peak) / peak
                    max_drawdown = min(max_drawdown, drawdown)
                    
            return float(max_drawdown)
            
        except Exception:
            return None