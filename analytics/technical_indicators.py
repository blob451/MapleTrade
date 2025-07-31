"""
Technical Indicators Foundation
Implements SMA, EMA, RSI, MACD, and Bollinger Bands with caching optimization
Optimized for high-RAM environments (192GB+)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Union
import logging
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
import hashlib
import json

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """
    Technical Indicators calculation class optimized for high-RAM environment.
    Implements caching for expensive operations and vectorized calculations.
    """
    
    def __init__(self, symbol: str, price_data: pd.DataFrame):
        """
        Initialize Technical Indicators calculator.
        
        Args:
            symbol: Stock symbol (e.g., 'NVDA')
            price_data: DataFrame with columns ['open', 'high', 'low', 'close', 'volume', 'date']
        """
        self.symbol = symbol.upper()
        self.price_data = self._validate_and_prepare_data(price_data)
        self.cache_prefix = f"tech_indicators:{self.symbol}"
        self.cache_ttl = getattr(settings, 'TECHNICAL_INDICATORS_CACHE_TTL', 3600)  # 1 hour default
        
    def _validate_and_prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Validate and prepare price data for calculations."""
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Ensure data is sorted by date
        if 'date' in data.columns:
            data = data.sort_values('date').reset_index(drop=True)
        else:
            data = data.sort_index().reset_index(drop=True)
            
        # Convert to float for calculations
        for col in required_columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')
            
        # Remove any rows with NaN in critical columns
        data = data.dropna(subset=['close']).reset_index(drop=True)
        
        if len(data) < 50:  # Minimum data points for reliable indicators
            raise ValueError(f"Insufficient data points: {len(data)}. Need at least 50.")
            
        return data
    
    def _generate_cache_key(self, indicator_name: str, **params) -> str:
        """Generate unique cache key for indicator with parameters."""
        params_str = json.dumps(params, sort_keys=True)
        data_hash = hashlib.md5(str(self.price_data['close'].iloc[-1]).encode()).hexdigest()[:8]
        return f"{self.cache_prefix}:{indicator_name}:{data_hash}:{hashlib.md5(params_str.encode()).hexdigest()[:8]}"
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict]:
        """Retrieve cached calculation result."""
        try:
            return cache.get(cache_key)
        except Exception as e:
            logger.warning(f"Cache retrieval failed for {cache_key}: {e}")
            return None
    
    def _set_cached_result(self, cache_key: str, result: Dict) -> None:
        """Store calculation result in cache."""
        try:
            cache.set(cache_key, result, self.cache_ttl)
        except Exception as e:
            logger.warning(f"Cache storage failed for {cache_key}: {e}")
    
    def calculate_sma(self, period: int = 20) -> Dict[str, Union[float, List[float]]]:
        """
        Calculate Simple Moving Average (SMA).
        
        Args:
            period: Number of periods for SMA calculation
            
        Returns:
            Dict with current SMA value and historical series
        """
        cache_key = self._generate_cache_key("sma", period=period)
        cached_result = self._get_cached_result(cache_key)
        
        if cached_result:
            logger.debug(f"Using cached SMA for {self.symbol}")
            return cached_result
            
        try:
            # Vectorized calculation using pandas rolling window
            sma_series = self.price_data['close'].rolling(window=period, min_periods=period).mean()
            
            result = {
                'indicator': 'SMA',
                'period': period,
                'current_value': float(sma_series.iloc[-1]) if not pd.isna(sma_series.iloc[-1]) else None,
                'series': sma_series.dropna().tolist(),
                'signal': self._generate_sma_signal(sma_series),
                'timestamp': datetime.now().isoformat()
            }
            
            self._set_cached_result(cache_key, result)
            logger.info(f"Calculated SMA({period}) for {self.symbol}: {result['current_value']:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"SMA calculation failed for {self.symbol}: {e}")
            raise
    
    def calculate_ema(self, period: int = 20) -> Dict[str, Union[float, List[float]]]:
        """
        Calculate Exponential Moving Average (EMA).
        
        Args:
            period: Number of periods for EMA calculation
            
        Returns:
            Dict with current EMA value and historical series
        """
        cache_key = self._generate_cache_key("ema", period=period)
        cached_result = self._get_cached_result(cache_key)
        
        if cached_result:
            logger.debug(f"Using cached EMA for {self.symbol}")
            return cached_result
            
        try:
            # Vectorized EMA calculation using pandas ewm
            ema_series = self.price_data['close'].ewm(span=period, adjust=False).mean()
            
            result = {
                'indicator': 'EMA',
                'period': period,
                'current_value': float(ema_series.iloc[-1]) if not pd.isna(ema_series.iloc[-1]) else None,
                'series': ema_series.tolist(),
                'signal': self._generate_ema_signal(ema_series),
                'timestamp': datetime.now().isoformat()
            }
            
            self._set_cached_result(cache_key, result)
            logger.info(f"Calculated EMA({period}) for {self.symbol}: {result['current_value']:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"EMA calculation failed for {self.symbol}: {e}")
            raise
    
    def calculate_rsi(self, period: int = 14) -> Dict[str, Union[float, List[float]]]:
        """
        Calculate Relative Strength Index (RSI).
        
        Args:
            period: Number of periods for RSI calculation
            
        Returns:
            Dict with current RSI value and historical series
        """
        cache_key = self._generate_cache_key("rsi", period=period)
        cached_result = self._get_cached_result(cache_key)
        
        if cached_result:
            logger.debug(f"Using cached RSI for {self.symbol}")
            return cached_result
            
        try:
            # Calculate price changes
            delta = self.price_data['close'].diff()
            
            # Separate gains and losses
            gains = delta.where(delta > 0, 0)
            losses = -delta.where(delta < 0, 0)
            
            # Calculate average gains and losses using EMA
            avg_gains = gains.ewm(span=period, adjust=False).mean()
            avg_losses = losses.ewm(span=period, adjust=False).mean()
            
            # Calculate RSI
            rs = avg_gains / avg_losses
            rsi_series = 100 - (100 / (1 + rs))
            
            result = {
                'indicator': 'RSI',
                'period': period,
                'current_value': float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else None,
                'series': rsi_series.dropna().tolist(),
                'signal': self._generate_rsi_signal(rsi_series.iloc[-1] if not pd.isna(rsi_series.iloc[-1]) else None),
                'timestamp': datetime.now().isoformat()
            }
            
            self._set_cached_result(cache_key, result)
            logger.info(f"Calculated RSI({period}) for {self.symbol}: {result['current_value']:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"RSI calculation failed for {self.symbol}: {e}")
            raise
    
    def calculate_macd(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict[str, Union[float, List[float]]]:
        """
        Calculate Moving Average Convergence Divergence (MACD).
        
        Args:
            fast_period: Fast EMA period
            slow_period: Slow EMA period  
            signal_period: Signal line EMA period
            
        Returns:
            Dict with MACD line, signal line, and histogram
        """
        cache_key = self._generate_cache_key("macd", fast=fast_period, slow=slow_period, signal=signal_period)
        cached_result = self._get_cached_result(cache_key)
        
        if cached_result:
            logger.debug(f"Using cached MACD for {self.symbol}")
            return cached_result
            
        try:
            # Calculate fast and slow EMAs
            fast_ema = self.price_data['close'].ewm(span=fast_period, adjust=False).mean()
            slow_ema = self.price_data['close'].ewm(span=slow_period, adjust=False).mean()
            
            # Calculate MACD line
            macd_line = fast_ema - slow_ema
            
            # Calculate signal line (EMA of MACD line)
            signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
            
            # Calculate histogram
            histogram = macd_line - signal_line
            
            result = {
                'indicator': 'MACD',
                'fast_period': fast_period,
                'slow_period': slow_period,
                'signal_period': signal_period,
                'macd_line': {
                    'current_value': float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else None,
                    'series': macd_line.dropna().tolist()
                },
                'signal_line': {
                    'current_value': float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else None,
                    'series': signal_line.dropna().tolist()
                },
                'histogram': {
                    'current_value': float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else None,
                    'series': histogram.dropna().tolist()
                },
                'signal': self._generate_macd_signal(macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]),
                'timestamp': datetime.now().isoformat()
            }
            
            self._set_cached_result(cache_key, result)
            logger.info(f"Calculated MACD for {self.symbol}: MACD={result['macd_line']['current_value']:.4f}")
            return result
            
        except Exception as e:
            logger.error(f"MACD calculation failed for {self.symbol}: {e}")
            raise
    
    def calculate_bollinger_bands(self, period: int = 20, std_dev: float = 2.0) -> Dict[str, Union[float, List[float]]]:
        """
        Calculate Bollinger Bands.
        
        Args:
            period: Period for moving average and standard deviation
            std_dev: Number of standard deviations for bands
            
        Returns:
            Dict with upper band, middle band (SMA), and lower band
        """
        cache_key = self._generate_cache_key("bollinger", period=period, std_dev=std_dev)
        cached_result = self._get_cached_result(cache_key)
        
        if cached_result:
            logger.debug(f"Using cached Bollinger Bands for {self.symbol}")
            return cached_result
            
        try:
            # Calculate middle band (SMA)
            middle_band = self.price_data['close'].rolling(window=period, min_periods=period).mean()
            
            # Calculate standard deviation
            rolling_std = self.price_data['close'].rolling(window=period, min_periods=period).std()
            
            # Calculate upper and lower bands
            upper_band = middle_band + (rolling_std * std_dev)
            lower_band = middle_band - (rolling_std * std_dev)
            
            current_price = self.price_data['close'].iloc[-1]
            
            result = {
                'indicator': 'Bollinger Bands',
                'period': period,
                'std_dev': std_dev,
                'upper_band': {
                    'current_value': float(upper_band.iloc[-1]) if not pd.isna(upper_band.iloc[-1]) else None,
                    'series': upper_band.dropna().tolist()
                },
                'middle_band': {
                    'current_value': float(middle_band.iloc[-1]) if not pd.isna(middle_band.iloc[-1]) else None,
                    'series': middle_band.dropna().tolist()
                },
                'lower_band': {
                    'current_value': float(lower_band.iloc[-1]) if not pd.isna(lower_band.iloc[-1]) else None,
                    'series': lower_band.dropna().tolist()
                },
                'bandwidth': float((upper_band.iloc[-1] - lower_band.iloc[-1]) / middle_band.iloc[-1] * 100),
                'position': self._calculate_bb_position(current_price, upper_band.iloc[-1], middle_band.iloc[-1], lower_band.iloc[-1]),
                'signal': self._generate_bollinger_signal(current_price, upper_band.iloc[-1], middle_band.iloc[-1], lower_band.iloc[-1]),
                'timestamp': datetime.now().isoformat()
            }
            
            self._set_cached_result(cache_key, result)
            logger.info(f"Calculated Bollinger Bands for {self.symbol}: Position={result['position']:.1f}%")
            return result
            
        except Exception as e:
            logger.error(f"Bollinger Bands calculation failed for {self.symbol}: {e}")
            raise
    
    def calculate_all_indicators(self) -> Dict[str, Dict]:
        """
        Calculate all technical indicators in a batch for optimal performance.
        
        Returns:
            Dict containing all calculated indicators
        """
        logger.info(f"Calculating all technical indicators for {self.symbol}")
        
        try:
            indicators = {
                'sma_20': self.calculate_sma(20),
                'sma_50': self.calculate_sma(50),
                'ema_12': self.calculate_ema(12),
                'ema_26': self.calculate_ema(26),
                'rsi_14': self.calculate_rsi(14),
                'macd': self.calculate_macd(),
                'bollinger_bands': self.calculate_bollinger_bands()
            }
            
            # Generate overall technical signal
            indicators['overall_signal'] = self._generate_overall_signal(indicators)
            
            logger.info(f"Successfully calculated all indicators for {self.symbol}")
            return indicators
            
        except Exception as e:
            logger.error(f"Failed to calculate all indicators for {self.symbol}: {e}")
            raise
    
    # Signal generation methods
    def _generate_sma_signal(self, sma_series: pd.Series) -> str:
        """Generate trading signal based on SMA."""
        current_price = self.price_data['close'].iloc[-1]
        current_sma = sma_series.iloc[-1]
        
        if pd.isna(current_sma):
            return "NEUTRAL"
            
        if current_price > current_sma * 1.02:  # 2% above SMA
            return "BULLISH"
        elif current_price < current_sma * 0.98:  # 2% below SMA
            return "BEARISH"
        else:
            return "NEUTRAL"
    
    def _generate_ema_signal(self, ema_series: pd.Series) -> str:
        """Generate trading signal based on EMA."""
        current_price = self.price_data['close'].iloc[-1]
        current_ema = ema_series.iloc[-1]
        
        if pd.isna(current_ema):
            return "NEUTRAL"
            
        if current_price > current_ema:
            return "BULLISH"
        elif current_price < current_ema:
            return "BEARISH"
        else:
            return "NEUTRAL"
    
    def _generate_rsi_signal(self, rsi_value: float) -> str:
        """Generate trading signal based on RSI."""
        if rsi_value is None or pd.isna(rsi_value):
            return "NEUTRAL"
            
        if rsi_value > 70:
            return "OVERBOUGHT"
        elif rsi_value < 30:
            return "OVERSOLD"
        elif rsi_value > 50:
            return "BULLISH"
        else:
            return "BEARISH"
    
    def _generate_macd_signal(self, macd_line: float, signal_line: float, histogram: float) -> str:
        """Generate trading signal based on MACD."""
        if any(pd.isna(val) for val in [macd_line, signal_line, histogram]):
            return "NEUTRAL"
            
        if macd_line > signal_line and histogram > 0:
            return "BULLISH"
        elif macd_line < signal_line and histogram < 0:
            return "BEARISH"
        else:
            return "NEUTRAL"
    
    def _calculate_bb_position(self, price: float, upper: float, middle: float, lower: float) -> float:
        """Calculate position within Bollinger Bands (0-100%)."""
        if pd.isna(upper) or pd.isna(lower):
            return 50.0
        return ((price - lower) / (upper - lower)) * 100
    
    def _generate_bollinger_signal(self, price: float, upper: float, middle: float, lower: float) -> str:
        """Generate trading signal based on Bollinger Bands."""
        position = self._calculate_bb_position(price, upper, middle, lower)
        
        if position > 80:
            return "OVERBOUGHT"
        elif position < 20:
            return "OVERSOLD"
        elif position > 50:
            return "BULLISH"
        else:
            return "BEARISH"
    
    def _generate_overall_signal(self, indicators: Dict) -> Dict[str, Union[str, int]]:
        """Generate overall technical signal from all indicators."""
        signals = []
        
        # Collect all signals
        if 'sma_20' in indicators and indicators['sma_20'].get('signal'):
            signals.append(indicators['sma_20']['signal'])
        if 'ema_12' in indicators and indicators['ema_12'].get('signal'):
            signals.append(indicators['ema_12']['signal'])
        if 'rsi_14' in indicators and indicators['rsi_14'].get('signal'):
            signals.append(indicators['rsi_14']['signal'])
        if 'macd' in indicators and indicators['macd'].get('signal'):
            signals.append(indicators['macd']['signal'])
        if 'bollinger_bands' in indicators and indicators['bollinger_bands'].get('signal'):
            signals.append(indicators['bollinger_bands']['signal'])
        
        # Count signal types
        bullish_count = signals.count('BULLISH')
        bearish_count = signals.count('BEARISH')
        overbought_count = signals.count('OVERBOUGHT')
        oversold_count = signals.count('OVERSOLD')
        
        # Determine overall signal
        total_signals = len(signals)
        if total_signals == 0:
            overall = "NEUTRAL"
        elif overbought_count >= 2:
            overall = "STRONG_SELL"
        elif oversold_count >= 2:
            overall = "STRONG_BUY"
        elif bullish_count > bearish_count and bullish_count >= total_signals * 0.6:
            overall = "BUY"
        elif bearish_count > bullish_count and bearish_count >= total_signals * 0.6:
            overall = "SELL"
        else:
            overall = "HOLD"
        
        return {
            'signal': overall,
            'confidence': max(bullish_count, bearish_count) / total_signals if total_signals > 0 else 0,
            'bullish_signals': bullish_count,
            'bearish_signals': bearish_count,
            'total_signals': total_signals
        }
    
    def clear_cache(self) -> None:
        """Clear all cached indicators for this symbol."""
        cache_pattern = f"{self.cache_prefix}:*"
        # Note: Django's cache doesn't support pattern deletion by default
        # This would need to be implemented based on your cache backend
        logger.info(f"Cache clear requested for {self.symbol}")