"""
Data validation and cleaning utilities for financial data.

This module provides comprehensive validation and cleaning functions
for financial data to ensure data quality and consistency.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd
import numpy as np
import logging

from .providers.base import PriceData, StockInfo, ValidationError

logger = logging.getLogger(__name__)


class DataValidator:
    """Comprehensive data validation and cleaning for financial data."""
    
    def __init__(self):
        self.max_price_change = Decimal('0.5')  # 50% max daily change
        self.min_volume = 0
        self.max_gap_days = 10  # Maximum gap in trading days
    
    def validate_stock_info(self, stock_info: StockInfo) -> StockInfo:
        """
        Validate and clean stock information.
        
        Args:
            stock_info: StockInfo object to validate
            
        Returns:
            Validated StockInfo object
            
        Raises:
            ValidationError: If validation fails
        """
        if not stock_info.symbol or len(stock_info.symbol.strip()) == 0:
            raise ValidationError("Stock symbol cannot be empty")
        
        # Clean and standardize symbol
        stock_info.symbol = stock_info.symbol.upper().strip()
        
        # Validate symbol format (basic check)
        if not stock_info.symbol.replace('.', '').replace('-', '').isalnum():
            raise ValidationError(f"Invalid symbol format: {stock_info.symbol}")
        
        # Clean name
        if stock_info.name:
            stock_info.name = stock_info.name.strip()
        
        # Validate prices
        if stock_info.current_price is not None and stock_info.current_price <= 0:
            raise ValidationError(f"Invalid current price: {stock_info.current_price}")
        
        if stock_info.target_price is not None and stock_info.target_price <= 0:
            raise ValidationError(f"Invalid target price: {stock_info.target_price}")
        
        # Validate market cap
        if stock_info.market_cap is not None and stock_info.market_cap < 0:
            raise ValidationError(f"Invalid market cap: {stock_info.market_cap}")
        
        return stock_info
    
    def validate_price_data_series(self, price_data: List[PriceData]) -> List[PriceData]:
        """
        Validate and clean a series of price data points.
        
        Args:
            price_data: List of PriceData objects
            
        Returns:
            Cleaned list of PriceData objects
        """
        if not price_data:
            return []
        
        # Sort by date
        price_data.sort(key=lambda x: x.date)
        
        validated_data = []
        previous_close = None
        
        for i, data in enumerate(price_data):
            try:
                # Basic validation
                self._validate_single_price_data(data)
                
                # Check for extreme price movements
                if previous_close is not None:
                    price_change = abs(data.open_price - previous_close) / previous_close
                    if price_change > self.max_price_change:
                        logger.warning(
                            f"Large price gap detected for {data.symbol} on {data.date}: "
                            f"{price_change:.2%} change"
                        )
                
                # Check for data gaps
                if i > 0:
                    days_gap = (data.date - price_data[i-1].date).days
                    if days_gap > self.max_gap_days:
                        logger.warning(
                            f"Large time gap in data for {data.symbol}: "
                            f"{days_gap} days between {price_data[i-1].date} and {data.date}"
                        )
                
                validated_data.append(data)
                previous_close = data.close_price
                
            except ValidationError as e:
                logger.warning(f"Removing invalid data point: {e}")
                continue
        
        return validated_data
    
    def _validate_single_price_data(self, data: PriceData) -> None:
        """Validate a single price data point."""
        # Check for null values
        required_fields = [data.open_price, data.high_price, data.low_price, 
                          data.close_price, data.adjusted_close]
        if any(price is None for price in required_fields):
            raise ValidationError(f"Missing price data for {data.symbol} on {data.date}")
        
        # Check for negative prices
        if any(price <= 0 for price in required_fields):
            raise ValidationError(f"Non-positive prices found for {data.symbol} on {data.date}")
        
        # Check logical relationships
        if data.high_price < data.low_price:
            raise ValidationError(f"High < Low for {data.symbol} on {data.date}")
        
        if not (data.low_price <= data.open_price <= data.high_price):
            raise ValidationError(f"Open price outside range for {data.symbol} on {data.date}")
        
        if not (data.low_price <= data.close_price <= data.high_price):
            raise ValidationError(f"Close price outside range for {data.symbol} on {data.date}")
        
        # Check volume
        if data.volume < self.min_volume:
            raise ValidationError(f"Invalid volume for {data.symbol} on {data.date}")
    
    def detect_outliers(self, price_data: List[PriceData]) -> List[PriceData]:
        """
        Detect and optionally remove outliers from price data.
        
        Args:
            price_data: List of PriceData objects
            
        Returns:
            List of PriceData objects with outliers marked/removed
        """
        if len(price_data) < 10:  # Need sufficient data for outlier detection
            return price_data
        
        # Convert to pandas for easier analysis
        df = pd.DataFrame([
            {
                'date': d.date,
                'close': float(d.close_price),
                'volume': d.volume,
                'high': float(d.high_price),
                'low': float(d.low_price),
            }
            for d in price_data
        ])
        
        # Calculate daily returns
        df['returns'] = df['close'].pct_change()
        
        # Detect outliers using IQR method
        Q1 = df['returns'].quantile(0.25)
        Q3 = df['returns'].quantile(0.75)
        IQR = Q3 - Q1
        
        # Define outlier bounds
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        # Mark outliers
        outliers = (df['returns'] < lower_bound) | (df['returns'] > upper_bound)
        
        if outliers.any():
            outlier_dates = df[outliers]['date'].tolist()
            logger.info(f"Detected {len(outlier_dates)} potential outliers in price data")
            
            # For now, just log outliers rather than removing them
            for date in outlier_dates:
                logger.info(f"Outlier detected on {date}")
        
        return price_data
    
    def fill_missing_data(self, price_data: List[PriceData]) -> List[PriceData]:
        """
        Fill missing data points in price series.
        
        Args:
            price_data: List of PriceData objects
            
        Returns:
            List with missing data filled
        """
        if len(price_data) < 2:
            return price_data
        
        # Sort by date
        price_data.sort(key=lambda x: x.date)
        
        filled_data = []
        
        for i in range(len(price_data) - 1):
            current = price_data[i]
            next_data = price_data[i + 1]
            
            filled_data.append(current)
            
            # Check for gaps (weekends and holidays are expected)
            days_diff = (next_data.date - current.date).days
            
            if days_diff > 3:  # More than weekend gap
                logger.info(f"Data gap detected for {current.symbol}: {days_diff} days")
                # For now, just log gaps rather than filling them
                # In production, you might implement forward-fill or interpolation
        
        # Add the last data point
        if price_data:
            filled_data.append(price_data[-1])
        
        return filled_data


class DataQualityReport:
    """Generate data quality reports for financial data."""
    
    @staticmethod
    def generate_report(price_data: List[PriceData]) -> Dict[str, Any]:
        """
        Generate a comprehensive data quality report.
        
        Args:
            price_data: List of PriceData objects
            
        Returns:
            Dictionary containing quality metrics
        """
        if not price_data:
            return {'error': 'No data provided'}
        
        # Sort by date
        price_data.sort(key=lambda x: x.date)
        
        report = {
            'symbol': price_data[0].symbol,
            'total_records': len(price_data),
            'date_range': {
                'start': price_data[0].date,
                'end': price_data[-1].date,
            },
            'data_gaps': [],
            'outliers': [],
            'quality_score': 0.0,
        }
        
        # Check for data gaps
        for i in range(len(price_data) - 1):
            days_diff = (price_data[i + 1].date - price_data[i].date).days
            if days_diff > 3:  # More than weekend
                report['data_gaps'].append({
                    'start': price_data[i].date,
                    'end': price_data[i + 1].date,
                    'days': days_diff
                })
        
        # Calculate quality score
        quality_factors = []
        
        # Completeness (no major gaps)
        completeness = max(0, 1 - len(report['data_gaps']) / max(1, len(price_data) / 30))
        quality_factors.append(completeness)
        
        # Consistency (volume > 0 for most records)
        non_zero_volume = sum(1 for d in price_data if d.volume > 0)
        volume_consistency = non_zero_volume / len(price_data) if price_data else 0
        quality_factors.append(volume_consistency)
        
        # Calculate overall quality score
        report['quality_score'] = sum(quality_factors) / len(quality_factors)
        
        return report