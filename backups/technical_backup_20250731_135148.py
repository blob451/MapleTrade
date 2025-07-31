"""
Technical indicators and calculations service.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from django.db.models import Q
from core.models import Stock, PriceData as PriceDataModel
from data.providers import YahooFinanceProvider, DataProviderError
from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class TechnicalIndicators(BaseAnalyzer):
    """
    Service for calculating technical indicators and metrics.
    """
    
    def __init__(self, data_provider: Optional[YahooFinanceProvider] = None):
        super().__init__()
        self.data_provider = data_provider or YahooFinanceProvider()
    
    def analyze(self, symbol: str, start_date: datetime, end_date: datetime) -> Dict[str, any]:
        """
        Calculate technical indicators for a stock.
        
        Returns dict with indicators like SMA, EMA, RSI, MACD, etc.
        """
        # First try to get data from database
        price_data = self._get_price_data_from_db(symbol, start_date, end_date)
        
        # If not enough data in DB and we have a provider, try API
        if (not price_data or len(price_data) < 20) and self.data_provider:
            logger.info(f"Insufficient DB data for {symbol} ({len(price_data) if price_data else 0} records), trying API...")
            try:
                api_price_data = self.data_provider.get_price_history(symbol, start_date, end_date)
                if api_price_data:
                    # Save to database for future use
                    self._save_price_data_to_db(symbol, api_price_data)
                    price_data = api_price_data
            except (DataProviderError, Exception) as e:
                logger.warning(f"Failed to get price data from API for {symbol}: {e}")
                # Continue with whatever data we have
        
        if not price_data:
            logger.error(f"No price data available for {symbol}")
            return {'error': 'No price data available'}
        
        logger.info(f"Using {len(price_data)} price records for {symbol}")
        
        # Convert to DataFrame for easier calculation
        df = self._create_dataframe(price_data)
        
        # Calculate indicators
        results = {
            'symbol': symbol,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'data_points': len(df)
        }
        
        # Add all indicators
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
        
        return results
    
    def _get_price_data_from_db(self, symbol: str, start_date: datetime, end_date: datetime):
        """Get price data from database."""
        try:
            stock = Stock.objects.filter(symbol__iexact=symbol).first()
            if not stock:
                logger.warning(f"Stock {symbol} not found in database")
                return []
            
            price_records = PriceDataModel.objects.filter(
                stock=stock,
                date__gte=start_date.date(),
                date__lte=end_date.date()
            ).order_by('date')
            
            logger.info(f"Found {price_records.count()} price records for {symbol} in database")
            
            # Convert to PriceData objects
            from data.providers.base import PriceData
            
            price_data = []
            for record in price_records:
                price_data.append(PriceData(
                    symbol=symbol,
                    date=datetime.combine(record.date, datetime.min.time()),
                    open_price=record.open_price,
                    high_price=record.high_price,
                    low_price=record.low_price,
                    close_price=record.close_price,
                    adjusted_close=record.adjusted_close or record.close_price,
                    volume=record.volume
                ))
            
            return price_data
            
        except Exception as e:
            logger.error(f"Error getting price data from DB for {symbol}: {e}")
            return []
    
    def _save_price_data_to_db(self, symbol: str, price_data: List):
        """Save price data to database."""
        try:
            stock = Stock.objects.filter(symbol__iexact=symbol).first()
            if not stock:
                logger.warning(f"Cannot save price data - stock {symbol} not found")
                return
            
            saved_count = 0
            for data in price_data:
                try:
                    PriceDataModel.objects.update_or_create(
                        stock=stock,
                        date=data.date.date() if hasattr(data.date, 'date') else data.date,
                        defaults={
                            'open_price': data.open_price,
                            'high_price': data.high_price,
                            'low_price': data.low_price,
                            'close_price': data.close_price,
                            'adjusted_close': data.adjusted_close,
                            'volume': data.volume
                        }
                    )
                    saved_count += 1
                except Exception as e:
                    logger.warning(f"Failed to save price record for {symbol} on {data.date}: {e}")
            
            logger.info(f"Saved {saved_count} price records for {symbol}")
            
        except Exception as e:
            logger.error(f"Error saving price data to DB for {symbol}: {e}")
    
    def _create_dataframe(self, price_data) -> pd.DataFrame:
        """Convert price data to pandas DataFrame."""
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
    
    def calculate_sma(self, df: pd.DataFrame, period: int) -> float:
        """Calculate Simple Moving Average."""
        if len(df) < period:
            return None
        try:
            return float(df['close'].rolling(window=period).mean().iloc[-1])
        except:
            return None
    
    def calculate_ema(self, df: pd.DataFrame, period: int) -> float:
        """Calculate Exponential Moving Average."""
        if len(df) < period:
            return None
        try:
            return float(df['close'].ewm(span=period, adjust=False).mean().iloc[-1])
        except:
            return None
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
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
    
    def calculate_macd(self, df: pd.DataFrame) -> Dict[str, float]:
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
    
    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20) -> Dict[str, float]:
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
            
            return {
                'upper': float(upper_band.iloc[-1]),
                'middle': float(sma.iloc[-1]),
                'lower': float(lower_band.iloc[-1]),
                'width': float((upper_band - lower_band).iloc[-1])
            }
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return None
    
    def calculate_volatility(self, df: pd.DataFrame, period: int = None) -> float:
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
    
    def calculate_returns(self, df: pd.DataFrame) -> Dict[str, float]:
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
    
    def get_price_at_date(self, symbol: str, date: datetime) -> Optional[Decimal]:
        """Get closing price for a specific date."""
        try:
            # First try database
            stock = Stock.objects.filter(symbol__iexact=symbol).first()
            if stock:
                price_record = PriceDataModel.objects.filter(
                    stock=stock,
                    date__lte=date.date()
                ).order_by('-date').first()
                
                if price_record:
                    return price_record.close_price
            
            # If not in DB and we have provider, try API
            if self.data_provider:
                try:
                    start = date - timedelta(days=5)
                    price_data = self.data_provider.get_price_history(symbol, start, date)
                    
                    if price_data:
                        # Return the most recent price
                        return price_data[-1].close_price
                except:
                    pass
            
            return None
        except Exception as e:
            self.logger.error(f"Error getting price for {symbol} at {date}: {e}")
            return None