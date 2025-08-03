"""
Batch analysis service for processing multiple stocks or portfolios.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.utils import timezone
from django.core.cache import cache

from data.services import StockService, PriceService
from .technical import TechnicalIndicators
from .calculations import FinancialCalculations

logger = logging.getLogger(__name__)


class BatchAnalysisService:
    """
    Service for performing batch analysis operations.
    """
    
    def __init__(
        self,
        max_workers: int = 4,
        stock_service: Optional[StockService] = None,
        price_service: Optional[PriceService] = None
    ):
        self.max_workers = max_workers
        self.stock_service = stock_service or StockService()
        self.price_service = price_service or PriceService()
        self.technical_analyzer = TechnicalIndicators(stock_service, price_service)
        self.financial_calc = FinancialCalculations(stock_service, price_service)
    
    def analyze_multiple_stocks(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        analysis_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze multiple stocks in parallel.
        
        Args:
            symbols: List of stock symbols
            start_date: Analysis start date
            end_date: Analysis end date
            analysis_types: List of analysis types to perform
            
        Returns:
            Dictionary with results for each symbol
        """
        if not analysis_types:
            analysis_types = ['technical', 'price_history']
        
        results = {
            'analysis_date': timezone.now().isoformat(),
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'symbols': symbols,
            'results': {},
            'errors': {},
            'summary': {}
        }
        
        # Process stocks in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit tasks
            future_to_symbol = {
                executor.submit(
                    self._analyze_single_stock,
                    symbol,
                    start_date,
                    end_date,
                    analysis_types
                ): symbol
                for symbol in symbols
            }
            
            # Collect results
            completed = 0
            total = len(symbols)
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                completed += 1
                
                try:
                    result = future.result()
                    results['results'][symbol] = result
                    
                    logger.info(f"Completed analysis for {symbol} ({completed}/{total})")
                    
                except Exception as e:
                    logger.error(f"Error analyzing {symbol}: {e}")
                    results['errors'][symbol] = str(e)
        
        # Generate summary
        results['summary'] = self._generate_batch_summary(results['results'])
        
        return results
    
    def _analyze_single_stock(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        analysis_types: List[str]
    ) -> Dict[str, Any]:
        """Analyze a single stock."""
        # Check cache first
        cache_key = f"batch_analysis_{symbol}_{start_date}_{end_date}_{'_'.join(analysis_types)}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.debug(f"Returning cached analysis for {symbol}")
            return cached_result
        
        result = {
            'symbol': symbol,
            'analysis_date': timezone.now().isoformat()
        }
        
        try:
            # Get or create stock
            stock = self.stock_service.get_or_create_stock(symbol)
            result['stock_info'] = {
                'name': stock.name,
                'sector': stock.sector.name if stock.sector else 'Unknown',
                'exchange': stock.exchange,
                'market_cap': float(stock.market_cap) if stock.market_cap else None,
                'current_price': float(stock.current_price) if stock.current_price else None
            }
            
            # Perform requested analyses
            if 'technical' in analysis_types:
                technical_result = self.technical_analyzer.analyze(
                    symbol,
                    datetime.combine(start_date, datetime.min.time()),
                    datetime.combine(end_date, datetime.min.time())
                )
                result['technical'] = technical_result
            
            if 'price_history' in analysis_types:
                price_data = self.price_service.get_price_history(
                    stock,
                    start_date,
                    end_date
                )
                result['price_history'] = {
                    'data_points': len(price_data),
                    'first_date': price_data[0].date.isoformat() if price_data else None,
                    'last_date': price_data[-1].date.isoformat() if price_data else None
                }
                
                if price_data:
                    # Calculate price range
                    prices = [float(p.close_price) for p in price_data]
                    result['price_history']['high'] = max(prices)
                    result['price_history']['low'] = min(prices)
                    result['price_history']['avg'] = sum(prices) / len(prices)
            
            if 'volatility' in analysis_types and 'technical' in result:
                result['risk_metrics'] = {
                    'volatility': result['technical'].get('volatility'),
                    'risk_level': self._categorize_volatility(
                        result['technical'].get('volatility')
                    )
                }
            
            # Cache the result for 1 hour
            cache.set(cache_key, result, 3600)
            
        except Exception as e:
            logger.error(f"Error in single stock analysis for {symbol}: {e}")
            result['error'] = str(e)
        
        return result
    
    def screen_stocks(
        self,
        symbols: List[str],
        criteria: Dict[str, Any],
        end_date: date = None
    ) -> Dict[str, Any]:
        """
        Screen stocks based on criteria.
        
        Args:
            symbols: List of symbols to screen
            criteria: Screening criteria
            end_date: Date for analysis (default: today)
            
        Returns:
            Stocks that match criteria
        """
        if not end_date:
            end_date = timezone.now().date()
        
        start_date = end_date - timedelta(days=30)  # Default 30-day analysis
        
        # Analyze all stocks
        analysis_results = self.analyze_multiple_stocks(
            symbols,
            start_date,
            end_date,
            ['technical', 'volatility']
        )
        
        # Apply screening criteria
        matched_stocks = []
        
        for symbol, result in analysis_results['results'].items():
            if 'error' in result:
                continue
            
            if self._matches_criteria(result, criteria):
                matched_stocks.append({
                    'symbol': symbol,
                    'name': result['stock_info']['name'],
                    'metrics': self._extract_screening_metrics(result, criteria)
                })
        
        return {
            'screening_date': timezone.now().isoformat(),
            'criteria': criteria,
            'total_screened': len(symbols),
            'matches': len(matched_stocks),
            'stocks': sorted(matched_stocks, key=lambda x: x['symbol'])
        }
    
    def _matches_criteria(self, result: Dict, criteria: Dict) -> bool:
        """Check if stock matches screening criteria."""
        try:
            technical = result.get('technical', {})
            
            # RSI criteria
            if 'rsi_min' in criteria:
                rsi = technical.get('rsi_14')
                if not rsi or rsi < criteria['rsi_min']:
                    return False
            
            if 'rsi_max' in criteria:
                rsi = technical.get('rsi_14')
                if not rsi or rsi > criteria['rsi_max']:
                    return False
            
            # Volatility criteria
            if 'volatility_max' in criteria:
                volatility = technical.get('volatility')
                if not volatility or volatility > criteria['volatility_max']:
                    return False
            
            # Price criteria
            if 'price_min' in criteria:
                price = result['stock_info'].get('current_price')
                if not price or price < criteria['price_min']:
                    return False
            
            if 'price_max' in criteria:
                price = result['stock_info'].get('current_price')
                if not price or price > criteria['price_max']:
                    return False
            
            # Trend criteria
            if 'trend' in criteria:
                trend = technical.get('trend', {})
                if criteria['trend'] == 'bullish':
                    if trend.get('short_term') != 'bullish':
                        return False
                elif criteria['trend'] == 'bearish':
                    if trend.get('short_term') != 'bearish':
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error matching criteria: {e}")
            return False
    
    def _extract_screening_metrics(self, result: Dict, criteria: Dict) -> Dict:
        """Extract relevant metrics based on criteria."""
        metrics = {}
        technical = result.get('technical', {})
        
        if 'rsi_min' in criteria or 'rsi_max' in criteria:
            metrics['rsi'] = technical.get('rsi_14')
        
        if 'volatility_max' in criteria:
            metrics['volatility'] = technical.get('volatility')
        
        if 'price_min' in criteria or 'price_max' in criteria:
            metrics['price'] = result['stock_info'].get('current_price')
        
        if 'trend' in criteria:
            trend = technical.get('trend', {})
            metrics['trend'] = trend.get('short_term')
        
        return metrics
    
    def _generate_batch_summary(self, results: Dict[str, Dict]) -> Dict[str, Any]:
        """Generate summary of batch analysis results."""
        if not results:
            return {}
        
        successful = [r for r in results.values() if 'error' not in r]
        
        if not successful:
            return {'error': 'No successful analyses'}
        
        # Aggregate metrics
        volatilities = []
        rsrs = []
        returns = []
        
        for result in successful:
            technical = result.get('technical', {})
            
            if technical.get('volatility'):
                volatilities.append(technical['volatility'])
            
            if technical.get('rsi_14'):
                rsrs.append(technical['rsi_14'])
            
            if technical.get('returns', {}).get('total_return'):
                returns.append(technical['returns']['total_return'])
        
        summary = {
            'total_analyzed': len(results),
            'successful': len(successful),
            'failed': len(results) - len(successful)
        }
        
        if volatilities:
            summary['avg_volatility'] = sum(volatilities) / len(volatilities)
            summary['max_volatility'] = max(volatilities)
            summary['min_volatility'] = min(volatilities)
        
        if rsrs:
            summary['avg_rsi'] = sum(rsrs) / len(rsrs)
            summary['oversold_count'] = len([r for r in rsrs if r < 30])
            summary['overbought_count'] = len([r for r in rsrs if r > 70])
        
        if returns:
            summary['avg_return'] = sum(returns) / len(returns)
            summary['best_return'] = max(returns)
            summary['worst_return'] = min(returns)
            summary['positive_returns'] = len([r for r in returns if r > 0])
        
        return summary
    
    def _categorize_volatility(self, volatility: Optional[float]) -> str:
        """Categorize volatility level."""
        if volatility is None:
            return 'unknown'
        elif volatility < 20:
            return 'low'
        elif volatility < 35:
            return 'moderate'
        elif volatility < 50:
            return 'high'
        else:
            return 'very_high'
    
    def compare_stocks(
        self,
        symbols: List[str],
        metrics: List[str] = None,
        end_date: date = None
    ) -> Dict[str, Any]:
        """
        Compare multiple stocks side by side.
        
        Args:
            symbols: List of symbols to compare
            metrics: Metrics to compare (default: all available)
            end_date: Date for comparison
            
        Returns:
            Comparison results
        """
        if not end_date:
            end_date = timezone.now().date()
        
        start_date = end_date - timedelta(days=90)  # 90-day comparison
        
        # Analyze all stocks
        analysis_results = self.analyze_multiple_stocks(
            symbols,
            start_date,
            end_date,
            ['technical', 'volatility']
        )
        
        # Extract comparison data
        comparison = {
            'comparison_date': timezone.now().isoformat(),
            'symbols': symbols,
            'metrics': {}
        }
        
        if not metrics:
            metrics = ['price', 'return', 'volatility', 'rsi', 'trend']
        
        for metric in metrics:
            comparison['metrics'][metric] = self._extract_comparison_metric(
                analysis_results['results'],
                metric
            )
        
        # Rank stocks by each metric
        comparison['rankings'] = self._rank_stocks(comparison['metrics'])
        
        return comparison
    
    def _extract_comparison_metric(
        self,
        results: Dict[str, Dict],
        metric: str
    ) -> List[Dict]:
        """Extract specific metric for comparison."""
        metric_data = []
        
        for symbol, result in results.items():
            if 'error' in result:
                continue
            
            data = {'symbol': symbol}
            technical = result.get('technical', {})
            
            if metric == 'price':
                data['value'] = result['stock_info'].get('current_price')
            elif metric == 'return':
                returns = technical.get('returns', {})
                data['value'] = returns.get('total_return')
            elif metric == 'volatility':
                data['value'] = technical.get('volatility')
            elif metric == 'rsi':
                data['value'] = technical.get('rsi_14')
            elif metric == 'trend':
                trend = technical.get('trend', {})
                data['value'] = trend.get('short_term')
            
            if data.get('value') is not None:
                metric_data.append(data)
        
        return sorted(metric_data, key=lambda x: x['symbol'])
    
    def _rank_stocks(self, metrics: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """Rank stocks by each metric."""
        rankings = {}
        
        for metric_name, metric_data in metrics.items():
            if not metric_data:
                continue
            
            # Skip non-numeric metrics
            if metric_name == 'trend':
                continue
            
            # Sort by value (handle None values)
            sorted_data = sorted(
                [d for d in metric_data if d.get('value') is not None],
                key=lambda x: x['value'],
                reverse=(metric_name in ['return', 'price'])  # Higher is better for these
            )
            
            # Assign ranks
            rankings[metric_name] = []
            for i, data in enumerate(sorted_data):
                rankings[metric_name].append({
                    'rank': i + 1,
                    'symbol': data['symbol'],
                    'value': data['value']
                })
        
        return rankings