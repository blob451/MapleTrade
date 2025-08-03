"""
Technical indicators and calculations service.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from data.services import StockService, PriceService
from data.models import Stock, PriceData
from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class TechnicalIndicators(BaseAnalyzer):
    """
    Service for calculating technical indicators and metrics.
    """
    
    def __init__(self, stock_service: Optional[StockService] = None, 
                 price_service: Optional[PriceService] = None):
        super().__init__()
        self.stock_service = stock_service or StockService()
        self.price_service = price_service or PriceService()
    
    def analyze(self, symbol: str, start_date: datetime, end_date: datetime) -> Dict[str, any]:
        """
        Calculate technical indicators for a stock.
        
        Returns dict with indicators like SMA, EMA, RSI, MACD, etc.
        """
        # Get or create stock
        try:
            stock = self.stock_service.get_or_create_stock(symbol, update_if_stale=False)
        except Exception as e:
            logger.error(f"Failed to get stock {symbol}: {e}")
            return {'error': f'Failed to get stock: {str(e)}'}
        
        # Get price history using the price service
        price_data = self.price_service.get_price_history(
            stock, 
            start_date.date() if hasattr(start_date, 'date') else start_date,
            end_date.date() if hasattr(end_date, 'date') else end_date
        )
        
        if not price_data:
            logger.error(f"No price data available for {symbol}")
            return {'error': 'No price data available'}
        
        logger.info(f"Using {len(price_data)} price records for {symbol}")
        
        # Convert to DataFrame for easier calculation
        df = self._create_dataframe(price_data)
        
        # Calculate indicators
        results = {
            'symbol': symbol,
            'start_date': start_date.isoformat() if hasattr(start_date, 'isoformat') else str(start_date),
            'end_date': end_date.isoformat() if hasattr(end_date, 'isoformat') else str(end_date),
            'data_points': len(df)
        }
        
        # Add all indicators based on available data
        if len(df) >= 2:  # Need at least 2 points for returns
            results['returns'] = self.calculate_returns(df)
            results['volatility'] = self.calculate_volatility(df)
        
        if len(df) >= 14:  # Need minimum for RSI
            results['rsi_14'] = self.calculate_rsi(df, 14)
        
        if len(df) >= 20:  # Need minimum for other indicators
            results['sma_20'] = self.calculate_sma(df, 20)
            results['bollinger_bands'] = self.calculate_bollinger_bands(df, 20)
        
        if len(df) >= 26:  # Need minimum for MACD
            results['ema_12'] = self.calculate_ema(df, 12)
            results['ema_26'] = self.calculate_ema(df, 26)
            results['macd'] = self.calculate_macd(df)
        
        if len(df) >= 50:
            results['sma_50'] = self.calculate_sma(df, 50)
        
        if len(df) >= 200:
            results['sma_200'] = self.calculate_sma(df, 200)
        
        # Add trend analysis
        results['trend'] = self.analyze_trend(df)
        
        # Add support/resistance levels
        results['support_resistance'] = self.calculate_support_resistance(df)
        
        return results
    
    def _create_dataframe(self, price_data: List[PriceData]) -> pd.DataFrame:
        """Convert PriceData objects to pandas DataFrame."""
        if not price_data:
            return pd.DataFrame()
        
        data = {
            'date': [p.date for p in price_data],
            'open': [float(p.open_price) for p in price_data],
            'high': [float(p.high_price) for p in price_data],
            'low': [float(p.low_price) for p in price_data],
            'close': [float(p.close_price) for p in price_data],
            'volume': [p.volume for p in price_data]
        }
        
        df = pd.DataFrame(data)
        if not df.empty:
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
        return df
    
    def calculate_sma(self, df: pd.DataFrame, period: int) -> Optional[float]:
        """Calculate Simple Moving Average."""
        if len(df) < period:
            return None
        try:
            return float(df['close'].rolling(window=period).mean().iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating SMA: {e}")
            return None
    
    def calculate_ema(self, df: pd.DataFrame, period: int) -> Optional[float]:
        """Calculate Exponential Moving Average."""
        if len(df) < period:
            return None
        try:
            return float(df['close'].ewm(span=period, adjust=False).mean().iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            return None
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Optional[float]:
        """Calculate Relative Strength Index."""
        if len(df) < period + 1:
            return None
        
        try:
            # Calculate price changes
            delta = df['close'].diff()
            
            # Separate gains and losses
            gains = delta.where(delta > 0, 0)
            losses = -delta.where(delta < 0, 0)
            
            # Calculate average gains and losses
            avg_gains = gains.rolling(window=period).mean()
            avg_losses = losses.rolling(window=period).mean()
            
            # Avoid division by zero
            avg_losses = avg_losses.replace(0, 0.0001)
            
            # Calculate RS and RSI
            rs = avg_gains / avg_losses
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return None
    
    def calculate_macd(self, df: pd.DataFrame) -> Optional[Dict[str, float]]:
        """Calculate MACD (Moving Average Convergence Divergence)."""
        if len(df) < 26:
            return None
        
        try:
            # Calculate EMAs
            ema_12 = df['close'].ewm(span=12, adjust=False).mean()
            ema_26 = df['close'].ewm(span=26, adjust=False).mean()
            
            # MACD line
            macd_line = ema_12 - ema_26
            
            # Signal line (9-day EMA of MACD)
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            
            # MACD histogram
            histogram = macd_line - signal_line
            
            return {
                'macd': float(macd_line.iloc[-1]),
                'signal': float(signal_line.iloc[-1]),
                'histogram': float(histogram.iloc[-1])
            }
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return None
    
    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20) -> Optional[Dict[str, float]]:
        """Calculate Bollinger Bands."""
        if len(df) < period:
            return None
        
        try:
            # Calculate SMA and standard deviation
            sma = df['close'].rolling(window=period).mean()
            std = df['close'].rolling(window=period).std()
            
            # Calculate bands
            upper_band = sma + (2 * std)
            lower_band = sma - (2 * std)
            
            current_price = float(df['close'].iloc[-1])
            middle = float(sma.iloc[-1])
            
            # Calculate position within bands (0 = lower band, 1 = upper band)
            band_width = float((upper_band - lower_band).iloc[-1])
            position = (current_price - float(lower_band.iloc[-1])) / band_width if band_width > 0 else 0.5
            
            return {
                'upper': float(upper_band.iloc[-1]),
                'middle': middle,
                'lower': float(lower_band.iloc[-1]),
                'width': band_width,
                'position': position
            }
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return None
    
    def calculate_volatility(self, df: pd.DataFrame, period: int = None) -> Optional[float]:
        """
        Calculate annualized volatility.
        
        Args:
            df: DataFrame with price data
            period: Period for calculation (None = use all data)
            
        Returns:
            Annualized volatility as a percentage
        """
        if len(df) < 2:
            return None
        
        try:
            # Calculate daily returns
            returns = df['close'].pct_change().dropna()
            
            if len(returns) == 0:
                return None
            
            if period and len(returns) > period:
                returns = returns.tail(period)
            
            # Calculate standard deviation of returns
            daily_vol = returns.std()
            
            if pd.isna(daily_vol) or daily_vol == 0:
                return None
            
            # Annualize (assuming 252 trading days)
            annual_vol = daily_vol * np.sqrt(252)
            
            return float(annual_vol * 100)  # Return as percentage
        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return None
    
    def calculate_returns(self, df: pd.DataFrame) -> Optional[Dict[str, float]]:
        """Calculate various return metrics."""
        if len(df) < 2:
            return None
        
        try:
            # Total return
            first_price = df['close'].iloc[0]
            last_price = df['close'].iloc[-1]
            
            if first_price == 0:
                return None
            
            total_return = (last_price - first_price) / first_price
            
            # Daily returns
            daily_returns = df['close'].pct_change().dropna()
            
            if len(daily_returns) == 0:
                return {
                    'total_return': float(total_return * 100),
                    'avg_daily_return': 0.0,
                    'sharpe_ratio': 0.0
                }
            
            # Average daily return
            avg_daily_return = daily_returns.mean()
            
            # Sharpe ratio (simplified - using 0% risk-free rate)
            daily_std = daily_returns.std()
            if daily_std > 0:
                sharpe = avg_daily_return / daily_std * np.sqrt(252)
            else:
                sharpe = 0
            
            return {
                'total_return': float(total_return * 100),  # As percentage
                'avg_daily_return': float(avg_daily_return * 100),
                'sharpe_ratio': float(sharpe)
            }
        except Exception as e:
            logger.error(f"Error calculating returns: {e}")
            return None
    
    def analyze_trend(self, df: pd.DataFrame) -> Optional[Dict[str, any]]:
        """Analyze price trend using moving averages."""
        if len(df) < 50:
            return None
        
        try:
            current_price = float(df['close'].iloc[-1])
            sma_20 = self.calculate_sma(df, 20)
            sma_50 = self.calculate_sma(df, 50)
            
            trend_info = {
                'current_price': current_price,
                'short_term': 'bullish' if current_price > sma_20 else 'bearish',
                'medium_term': 'bullish' if current_price > sma_50 else 'bearish'
            }
            
            # Golden/Death cross detection
            if len(df) >= 200:
                sma_200 = self.calculate_sma(df, 200)
                trend_info['long_term'] = 'bullish' if current_price > sma_200 else 'bearish'
                
                # Check for crossovers in last 5 days
                recent_50 = df['close'].rolling(window=50).mean().tail(5)
                recent_200 = df['close'].rolling(window=200).mean().tail(5)
                
                if len(recent_50) >= 2 and len(recent_200) >= 2:
                    if recent_50.iloc[-2] < recent_200.iloc[-2] and recent_50.iloc[-1] > recent_200.iloc[-1]:
                        trend_info['signal'] = 'golden_cross'
                    elif recent_50.iloc[-2] > recent_200.iloc[-2] and recent_50.iloc[-1] < recent_200.iloc[-1]:
                        trend_info['signal'] = 'death_cross'
            
            return trend_info
            
        except Exception as e:
            logger.error(f"Error analyzing trend: {e}")
            return None
    
    def calculate_support_resistance(self, df: pd.DataFrame, lookback: int = 20) -> Optional[Dict[str, float]]:
        """Calculate support and resistance levels."""
        if len(df) < lookback:
            return None
        
        try:
            recent_data = df.tail(lookback)
            current_price = float(df['close'].iloc[-1])
            
            # Find local highs and lows
            highs = recent_data['high'].values
            lows = recent_data['low'].values
            
            # Simple approach: use recent high/low
            resistance = float(recent_data['high'].max())
            support = float(recent_data['low'].min())
            
            # Find intermediate levels
            pivot = (resistance + support + current_price) / 3
            
            return {
                'support': support,
                'resistance': resistance,
                'pivot': float(pivot),
                'support_strength': self._calculate_level_strength(df, support),
                'resistance_strength': self._calculate_level_strength(df, resistance)
            }
            
        except Exception as e:
            logger.error(f"Error calculating support/resistance: {e}")
            return None
    
    def _calculate_level_strength(self, df: pd.DataFrame, level: float, tolerance: float = 0.02) -> int:
        """Calculate how many times price has bounced off a level."""
        if len(df) < 10:
            return 0
        
        try:
            # Count touches within tolerance
            touches = 0
            for i in range(len(df)):
                low = float(df['low'].iloc[i])
                high = float(df['high'].iloc[i])
                
                # Check if price touched the level
                if (abs(low - level) / level <= tolerance or 
                    abs(high - level) / level <= tolerance):
                    touches += 1
            
            return touches
            
        except Exception:
            return 0
    
    def get_price_at_date(self, symbol: str, date: datetime) -> Optional[Decimal]:
        """Get closing price for a specific date."""
        try:
            stock = self.stock_service.get_or_create_stock(symbol, update_if_stale=False)
            latest_price = self.price_service.get_latest_price(stock)
            
            if latest_price and latest_price.date <= date.date():
                return latest_price.close_price
            
            # Get historical price
            price_data = self.price_service.get_price_history(
                stock,
                (date - timedelta(days=5)).date(),
                date.date()
            )
            
            if price_data:
                # Return the most recent price up to the requested date
                for price in reversed(price_data):
                    if price.date <= date.date():
                        return price.close_price
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting price for {symbol} at {date}: {e}")
            return None