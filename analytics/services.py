"""
Analytics services for stock analysis.
Updated to integrate Technical Indicators (Task 3.2).
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
import yfinance as yf
from django.utils import timezone
from django.db import transaction

from .models import Stock, Sector, PriceData, AnalysisResult, TechnicalIndicator
from .technical_indicators import TechnicalIndicators
from .cache import technical_cache, market_data_cache

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """
    Core analytics engine with three-factor model and technical analysis integration.
    Updated for Task 3.2 implementation.
    """
    
    def __init__(self):
        """Initialize the analytics engine."""
        self.sector_etf_mapping = {
            'Technology': 'XLK',
            'Healthcare': 'XLV', 
            'Financial': 'XLF',
            'Consumer Discretionary': 'XLY',
            'Communication Services': 'XLC',
            'Industrials': 'XLI',
            'Consumer Staples': 'XLP',
            'Energy': 'XLE',
            'Utilities': 'XLU',
            'Real Estate': 'XLRE',
            'Materials': 'XLB'
        }
        
        self.volatility_thresholds = {
            'Technology': 0.35,
            'Healthcare': 0.25,
            'Financial': 0.30,
            'Consumer Discretionary': 0.30,
            'Communication Services': 0.28,
            'Industrials': 0.25,
            'Consumer Staples': 0.20,
            'Energy': 0.35,
            'Utilities': 0.18,
            'Real Estate': 0.25,
            'Materials': 0.28,
            'default': 0.25
        }
    
    def analyze_stock(self, symbol: str, period_months: int = 6, include_technical: bool = True) -> Dict:
        """
        Perform comprehensive stock analysis including technical indicators.
        
        Args:
            symbol: Stock symbol to analyze
            period_months: Analysis period in months
            include_technical: Whether to include technical analysis
            
        Returns:
            Complete analysis results dictionary
        """
        logger.info(f"Starting comprehensive analysis for {symbol}")
        
        try:
            # Get or create stock record
            stock = self._get_or_create_stock(symbol)
            
            # Fetch price data
            price_data = self._fetch_price_data(symbol, period_months)
            
            # Perform fundamental analysis (three-factor model)
            fundamental_analysis = self._perform_fundamental_analysis(
                stock, price_data, period_months
            )
            
            # Perform technical analysis if requested
            technical_analysis = {}
            if include_technical:
                technical_analysis = self._perform_technical_analysis(stock, price_data)
            
            # Generate overall recommendation
            overall_analysis = self._generate_overall_recommendation(
                fundamental_analysis, technical_analysis
            )
            
            # Save results to database
            analysis_result = self._save_analysis_result(
                stock, fundamental_analysis, technical_analysis, overall_analysis, period_months
            )
            
            # Combine all results
            complete_analysis = {
                'stock': {
                    'symbol': symbol,
                    'name': stock.name,
                    'sector': stock.sector.name if stock.sector else 'Unknown'
                },
                'fundamental': fundamental_analysis,
                'technical': technical_analysis,
                'overall': overall_analysis,
                'analysis_id': analysis_result.id,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Completed analysis for {symbol}: {overall_analysis['signal']}")
            return complete_analysis
            
        except Exception as e:
            logger.error(f"Analysis failed for {symbol}: {e}")
            raise
    
    def _get_or_create_stock(self, symbol: str) -> Stock:
        """Get or create stock record."""
        try:
            return Stock.objects.get(symbol=symbol.upper())
        except Stock.DoesNotExist:
            # Create new stock record
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Determine sector
            sector_name = info.get('sector', 'Unknown')
            sector = None
            try:
                sector, created = Sector.objects.get_or_create(
                    name=sector_name,
                    defaults={
                        'code': sector_name[:10],
                        'etf_symbol': self.sector_etf_mapping.get(sector_name, 'SPY'),
                        'volatility_threshold': self.volatility_thresholds.get(sector_name, 0.25)
                    }
                )
            except Exception as e:
                logger.warning(f"Could not create/get sector for {symbol}: {e}")
            
            stock = Stock.objects.create(
                symbol=symbol.upper(),
                name=info.get('shortName', symbol),
                sector=sector,
                exchange=info.get('exchange', ''),
                market_cap=info.get('marketCap')
            )
            
            logger.info(f"Created new stock record: {stock}")
            return stock
    
    def _fetch_price_data(self, symbol: str, period_months: int) -> pd.DataFrame:
        """Fetch historical price data with caching."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_months * 30 + 60)  # Extra buffer for indicators
        
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        # Try to get from cache first
        cached_data = market_data_cache.get_price_data(symbol, start_str, end_str)
        if cached_data is not None:
            logger.debug(f"Using cached price data for {symbol}")
            return cached_data
        
        # Fetch from Yahoo Finance
        ticker = yf.Ticker(symbol)
        data = ticker.history(start=start_date, end=end_date)
        
        if data.empty:
            raise ValueError(f"No price data found for {symbol}")
        
        # Prepare data for technical indicators
        price_df = pd.DataFrame({
            'date': data.index,
            'open': data['Open'],
            'high': data['High'], 
            'low': data['Low'],
            'close': data['Close'],
            'volume': data['Volume']
        }).reset_index(drop=True)
        
        # Cache the data
        market_data_cache.cache_price_data(symbol, start_str, end_str, price_df)
        
        logger.info(f"Fetched {len(price_df)} days of price data for {symbol}")
        return price_df
    
    def _perform_fundamental_analysis(self, stock: Stock, price_data: pd.DataFrame, period_months: int) -> Dict:
        """
        Perform fundamental analysis using the three-factor model from prototype.
        """
        logger.info(f"Performing fundamental analysis for {stock.symbol}")
        
        try:
            # Get current and historical prices
            current_price = float(price_data['close'].iloc[-1])
            
            # Calculate stock return over period
            period_start_idx = max(0, len(price_data) - (period_months * 22))  # ~22 trading days per month
            if period_start_idx >= len(price_data) - 1:
                period_start_idx = 0
                
            start_price = float(price_data['close'].iloc[period_start_idx])
            stock_return = (current_price - start_price) / start_price
            
            # Get sector ETF data for comparison
            sector_etf = self._get_sector_etf_symbol(stock)
            sector_return = self._calculate_sector_return(sector_etf, period_months)
            
            # Calculate volatility
            returns = price_data['close'].pct_change().dropna()
            volatility = float(returns.std() * np.sqrt(252))  # Annualized
            
            # Get analyst target
            target_price = self._get_analyst_target(stock.symbol)
            
            # Apply three-factor decision logic
            sector_outperformance = stock_return > sector_return
            analyst_target_positive = target_price > current_price if target_price else False
            volatility_threshold = self.volatility_thresholds.get(
                stock.sector.name if stock.sector else 'default', 0.25
            )
            volatility_acceptable = volatility < volatility_threshold
            
            # Generate signal based on prototype logic
            signal = self._generate_fundamental_signal(
                sector_outperformance, analyst_target_positive, volatility_acceptable
            )
            
            # Generate rationale
            rationale = self._generate_fundamental_rationale(
                sector_outperformance, analyst_target_positive, volatility_acceptable, signal
            )
            
            return {
                'signal': signal,
                'metrics': {
                    'current_price': current_price,
                    'target_price': target_price,
                    'stock_return': stock_return,
                    'sector_return': sector_return,
                    'volatility': volatility,
                    'volatility_threshold': volatility_threshold
                },
                'factors': {
                    'sector_outperformance': sector_outperformance,
                    'analyst_target_positive': analyst_target_positive,
                    'volatility_acceptable': volatility_acceptable
                },
                'rationale': rationale,
                'sector_etf': sector_etf
            }
            
        except Exception as e:
            logger.error(f"Fundamental analysis failed for {stock.symbol}: {e}")
            raise
    
    def _perform_technical_analysis(self, stock: Stock, price_data: pd.DataFrame) -> Dict:
        """
        Perform technical analysis using TechnicalIndicators class.
        """
        logger.info(f"Performing technical analysis for {stock.symbol}")
        
        try:
            # Initialize technical indicators calculator
            tech_indicators = TechnicalIndicators(stock.symbol, price_data)
            
            # Calculate all indicators
            indicators = tech_indicators.calculate_all_indicators()
            
            # Save technical indicators to database
            self._save_technical_indicators(stock, indicators)
            
            # Extract overall technical signal
            overall_signal = indicators.get('overall_signal', {})
            
            return {
                'signal': overall_signal.get('signal', 'HOLD'),
                'confidence': overall_signal.get('confidence', 0.0),
                'indicators': {
                    'sma_20': indicators.get('sma_20', {}),
                    'sma_50': indicators.get('sma_50', {}),
                    'ema_12': indicators.get('ema_12', {}),
                    'ema_26': indicators.get('ema_26', {}),
                    'rsi_14': indicators.get('rsi_14', {}),
                    'macd': indicators.get('macd', {}),
                    'bollinger_bands': indicators.get('bollinger_bands', {})
                },
                'summary': self._generate_technical_summary(indicators),
                'signals_breakdown': {
                    'bullish_signals': overall_signal.get('bullish_signals', 0),
                    'bearish_signals': overall_signal.get('bearish_signals', 0),
                    'total_signals': overall_signal.get('total_signals', 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Technical analysis failed for {stock.symbol}: {e}")
            # Return neutral technical analysis if calculation fails
            return {
                'signal': 'HOLD',
                'confidence': 0.0,
                'indicators': {},
                'summary': 'Technical analysis unavailable',
                'error': str(e)
            }
    
    def _save_technical_indicators(self, stock: Stock, indicators: Dict) -> None:
        """Save technical indicators to database."""
        calculation_time = timezone.now()
        
        try:
            with transaction.atomic():
                # Save individual indicators
                for indicator_name, indicator_data in indicators.items():
                    if indicator_name == 'overall_signal':
                        continue
                        
                    # Map indicator names to model choices
                    indicator_type_map = {
                        'sma_20': 'SMA',
                        'sma_50': 'SMA', 
                        'ema_12': 'EMA',
                        'ema_26': 'EMA',
                        'rsi_14': 'RSI',
                        'macd': 'MACD',
                        'bollinger_bands': 'BOLLINGER'
                    }
                    
                    indicator_type = indicator_type_map.get(indicator_name)
                    if not indicator_type:
                        continue
                    
                    # Extract parameters
                    period = indicator_data.get('period')
                    fast_period = indicator_data.get('fast_period')
                    slow_period = indicator_data.get('slow_period')
                    signal_period = indicator_data.get('signal_period')
                    std_dev = indicator_data.get('std_dev')
                    
                    # Create or update technical indicator record
                    tech_indicator, created = TechnicalIndicator.objects.update_or_create(
                        stock=stock,
                        indicator_type=indicator_type,
                        calculation_date=calculation_time,
                        period=period,
                        fast_period=fast_period,
                        slow_period=slow_period,
                        defaults={
                            'signal_period': signal_period,
                            'std_dev': std_dev,
                            'current_value': indicator_data.get('current_value'),
                            'signal': indicator_data.get('signal', 'NEUTRAL'),
                            'confidence': 0.8,  # Default confidence
                            'data': indicator_data
                        }
                    )
                    
                    logger.debug(f"{'Created' if created else 'Updated'} {indicator_type} for {stock.symbol}")
                    
        except Exception as e:
            logger.error(f"Failed to save technical indicators for {stock.symbol}: {e}")
    
    def _generate_overall_recommendation(self, fundamental: Dict, technical: Dict) -> Dict:
        """
        Generate overall recommendation combining fundamental and technical analysis.
        """
        fundamental_signal = fundamental.get('signal', 'HOLD')
        technical_signal = technical.get('signal', 'HOLD')
        technical_confidence = technical.get('confidence', 0.0)
        
        # Signal strength mapping
        signal_strength = {
            'STRONG_BUY': 2,
            'BUY': 1,
            'HOLD': 0,
            'SELL': -1,
            'STRONG_SELL': -2
        }
        
        # Get numeric values
        fund_strength = signal_strength.get(fundamental_signal, 0)
        tech_strength = signal_strength.get(technical_signal, 0)
        
        # Weight fundamental analysis more heavily (70% vs 30%)
        # This follows the prototype's primary focus on fundamental factors
        combined_strength = (fund_strength * 0.7) + (tech_strength * 0.3)
        
        # Convert back to signal
        if combined_strength >= 1.5:
            overall_signal = 'STRONG_BUY'
        elif combined_strength >= 0.5:
            overall_signal = 'BUY'
        elif combined_strength <= -1.5:
            overall_signal = 'STRONG_SELL'
        elif combined_strength <= -0.5:
            overall_signal = 'SELL'
        else:
            overall_signal = 'HOLD'
        
        # Calculate confidence score
        confidence = (abs(combined_strength) + technical_confidence) / 2
        confidence = min(confidence, 1.0)
        
        # Generate explanation
        explanation = self._generate_overall_explanation(
            fundamental_signal, technical_signal, overall_signal
        )
        
        return {
            'signal': overall_signal,
            'confidence': confidence,
            'fundamental_signal': fundamental_signal,
            'technical_signal': technical_signal,
            'explanation': explanation,
            'combined_strength': combined_strength
        }
    
    def _save_analysis_result(self, stock: Stock, fundamental: Dict, technical: Dict, 
                            overall: Dict, period_months: int) -> AnalysisResult:
        """Save complete analysis result to database."""
        
        # Get technical indicators for this analysis
        recent_indicators = TechnicalIndicator.objects.filter(
            stock=stock,
            calculation_date__gte=timezone.now() - timedelta(hours=1)
        )
        
        analysis_result = AnalysisResult.objects.create(
            stock=stock,
            analysis_date=timezone.now(),
            analysis_period_months=period_months,
            
            # Fundamental analysis results
            sector_outperformance=fundamental['factors']['sector_outperformance'],
            analyst_target_positive=fundamental['factors']['analyst_target_positive'],
            volatility_acceptable=fundamental['factors']['volatility_acceptable'],
            
            stock_return=fundamental['metrics']['stock_return'],
            sector_return=fundamental['metrics']['sector_return'],
            volatility=fundamental['metrics']['volatility'],
            current_price=fundamental['metrics']['current_price'],
            target_price=fundamental['metrics']['target_price'],
            
            # Signals
            fundamental_signal=fundamental['signal'],
            technical_signal=technical.get('signal', 'HOLD'),
            overall_signal=overall['signal'],
            
            confidence_score=overall['confidence'],
            risk_score=min(fundamental['metrics']['volatility'], 1.0),
            
            rationale=fundamental['rationale'],
            technical_summary=technical.get('summary', '')
        )
        
        # Add technical indicators to the analysis
        if recent_indicators.exists():
            analysis_result.technical_indicators.add(*recent_indicators)
        
        logger.info(f"Saved analysis result for {stock.symbol}: {analysis_result.id}")
        return analysis_result
    
    # Helper methods for fundamental analysis (from prototype)
    def _get_sector_etf_symbol(self, stock: Stock) -> str:
        """Get sector ETF symbol for comparison."""
        if stock.sector:
            return self.sector_etf_mapping.get(stock.sector.name, 'SPY')
        return 'SPY'
    
    def _calculate_sector_return(self, etf_symbol: str, period_months: int) -> float:
        """Calculate sector ETF return for comparison."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_months * 30)
            
            etf_ticker = yf.Ticker(etf_symbol)
            etf_data = etf_ticker.history(start=start_date, end=end_date)
            
            if etf_data.empty:
                return 0.0
                
            start_price = float(etf_data['Close'].iloc[0])
            end_price = float(etf_data['Close'].iloc[-1])
            
            return (end_price - start_price) / start_price
            
        except Exception as e:
            logger.warning(f"Could not calculate sector return for {etf_symbol}: {e}")
            return 0.0
    
    def _get_analyst_target(self, symbol: str) -> Optional[float]:
        """Get analyst target price."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return info.get('targetMeanPrice')
        except Exception as e:
            logger.warning(f"Could not get analyst target for {symbol}: {e}")
            return None
    
    def _generate_fundamental_signal(self, outperformance: bool, target_positive: bool, 
                                   volatility_ok: bool) -> str:
        """Generate signal using three-factor logic from prototype."""
        if outperformance and target_positive:
            return 'BUY'  # Both positive signals
        elif (outperformance or target_positive) and volatility_ok:
            return 'BUY'  # One positive signal + low volatility
        elif (outperformance or target_positive) and not volatility_ok:
            return 'HOLD'  # One positive signal + high volatility
        elif not outperformance and not target_positive and volatility_ok:
            return 'HOLD'  # Both negative + low volatility
        elif not outperformance and not target_positive and not volatility_ok:
            return 'SELL'  # Both negative + high volatility
        else:
            return 'HOLD'  # Default
    
    def _generate_fundamental_rationale(self, outperformance: bool, target_positive: bool,
                                      volatility_ok: bool, signal: str) -> str:
        """Generate rationale text from prototype logic."""
        conditions = []
        
        if outperformance:
            conditions.append("outperformed its sector")
        if target_positive:
            conditions.append("analyst target above current price")
        if volatility_ok:
            conditions.append("volatility within acceptable range")
        
        if signal == 'BUY':
            if outperformance and target_positive:
                return "Both outperformance and analyst target are positive. Strong buy signal."
            else:
                return f"Positive signal from {' and '.join(conditions)}. Volatility supports the position."
        elif signal == 'SELL':
            return "Both performance and target are negative, with high volatility increasing risk."
        else:
            return f"Mixed signals. {' and '.join(conditions) if conditions else 'No strong indicators'}. Recommend holding."
    
    def _generate_technical_summary(self, indicators: Dict) -> str:
        """Generate technical analysis summary."""
        overall = indicators.get('overall_signal', {})
        
        bullish = overall.get('bullish_signals', 0)
        bearish = overall.get('bearish_signals', 0)
        total = overall.get('total_signals', 0)
        
        if total == 0:
            return "Technical analysis unavailable due to insufficient data."
        
        summary_parts = []
        
        # RSI analysis
        rsi = indicators.get('rsi_14', {})
        if rsi and rsi.get('current_value'):
            rsi_val = rsi['current_value']
            if rsi_val > 70:
                summary_parts.append(f"RSI ({rsi_val:.1f}) indicates overbought conditions")
            elif rsi_val < 30:
                summary_parts.append(f"RSI ({rsi_val:.1f}) indicates oversold conditions")
            else:
                summary_parts.append(f"RSI ({rsi_val:.1f}) is neutral")
        
        # MACD analysis
        macd = indicators.get('macd', {})
        if macd and macd.get('signal'):
            summary_parts.append(f"MACD is {macd['signal'].lower()}")
        
        # Bollinger Bands
        bb = indicators.get('bollinger_bands', {})
        if bb and bb.get('position'):
            position = bb['position']
            if position > 80:
                summary_parts.append("price near upper Bollinger Band")
            elif position < 20:
                summary_parts.append("price near lower Bollinger Band")
        
        # Overall assessment
        if bullish > bearish:
            summary_parts.append(f"Overall technical outlook is bullish ({bullish}/{total} indicators)")
        elif bearish > bullish:
            summary_parts.append(f"Overall technical outlook is bearish ({bearish}/{total} indicators)")
        else:
            summary_parts.append("Technical indicators are mixed")
        
        return ". ".join(summary_parts) + "."
    
    def _generate_overall_explanation(self, fundamental_signal: str, technical_signal: str, 
                                    overall_signal: str) -> str:
        """Generate explanation for overall recommendation."""
        explanations = {
            ('BUY', 'BUY'): "Both fundamental and technical analysis support a buy recommendation.",
            ('BUY', 'HOLD'): "Strong fundamental analysis supports buying, with neutral technical signals.",
            ('BUY', 'SELL'): "Fundamental analysis suggests buying, but technical analysis shows caution.",
            ('HOLD', 'BUY'): "Fundamental analysis suggests holding, but technical signals are positive.",
            ('HOLD', 'HOLD'): "Both analyses recommend holding the position.",
            ('HOLD', 'SELL'): "Mixed signals with fundamental neutrality and technical weakness.",
            ('SELL', 'BUY'): "Conflicting signals between fundamental weakness and technical strength.",
            ('SELL', 'HOLD'): "Fundamental analysis suggests selling, technical analysis is neutral.",
            ('SELL', 'SELL'): "Both fundamental and technical analysis support selling."
        }
        
        key = (fundamental_signal, technical_signal)
        base_explanation = explanations.get(key, "Analysis complete with mixed signals.")
        
        return f"{base_explanation} Overall recommendation: {overall_signal}."


# Convenience function for external use
def analyze_stock_complete(symbol: str, period_months: int = 6, include_technical: bool = True) -> Dict:
    """
    Convenience function to perform complete stock analysis.
    
    Args:
        symbol: Stock symbol to analyze
        period_months: Analysis period in months
        include_technical: Whether to include technical analysis
        
    Returns:
        Complete analysis results
    """
    engine = AnalyticsEngine()
    return engine.analyze_stock(symbol, period_months, include_technical)