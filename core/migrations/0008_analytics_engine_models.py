# Migration for analytics engine models - compatible with existing structure

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
    ('core', '0007_merge_20250730_1357'),
    ]

    operations = [
        # Create AnalysisResult model
        migrations.CreateModel(
            name='AnalysisResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('analysis_date', models.DateTimeField(default=django.utils.timezone.now, help_text='When analysis was performed')),
                ('analysis_period_months', models.IntegerField(help_text='Analysis lookback period in months')),
                ('signal', models.CharField(choices=[('BUY', 'Buy'), ('SELL', 'Sell'), ('HOLD', 'Hold')], help_text='Investment recommendation', max_length=4)),
                ('confidence', models.CharField(choices=[('HIGH', 'High'), ('MEDIUM', 'Medium'), ('LOW', 'Low')], help_text='Confidence level in recommendation', max_length=6)),
                ('stock_return', models.DecimalField(decimal_places=4, help_text='Stock total return over analysis period', max_digits=8)),
                ('sector_return', models.DecimalField(decimal_places=4, help_text='Sector ETF return over analysis period', max_digits=8)),
                ('outperformance', models.DecimalField(decimal_places=4, help_text='Stock outperformance vs sector', max_digits=8)),
                ('volatility', models.DecimalField(decimal_places=4, help_text='Annualized volatility', max_digits=6)),
                ('current_price', models.DecimalField(decimal_places=4, help_text='Price at time of analysis', max_digits=12)),
                ('target_price', models.DecimalField(blank=True, decimal_places=4, help_text='Analyst target price', max_digits=12, null=True)),
                ('outperformed_sector', models.BooleanField(help_text='Stock outperformed its sector ETF')),
                ('target_above_price', models.BooleanField(help_text='Analyst target above current price')),
                ('volatility_below_threshold', models.BooleanField(help_text='Volatility below sector threshold')),
                ('sector_name', models.CharField(help_text='Sector name at time of analysis', max_length=100)),
                ('sector_etf', models.CharField(help_text='Sector ETF symbol used', max_length=10)),
                ('sector_volatility_threshold', models.DecimalField(decimal_places=4, help_text='Volatility threshold used', max_digits=5)),
                ('rationale', models.TextField(help_text='Human-readable explanation of recommendation')),
                ('engine_version', models.CharField(default='1.0.0', help_text='Analytics engine version used', max_length=20)),
                ('stock', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analysis_results', to='core.stock')),
            ],
            options={
                'db_table': 'mapletrade_analysis_results',
                'ordering': ['-analysis_date'],
            },
        ),
        
        # Create PriceData model  
        migrations.CreateModel(
            name='PriceData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date', models.DateField(help_text='Trading date')),
                ('open_price', models.DecimalField(decimal_places=4, help_text='Opening price', max_digits=12)),
                ('high_price', models.DecimalField(decimal_places=4, help_text="Day's high price", max_digits=12)),
                ('low_price', models.DecimalField(decimal_places=4, help_text="Day's low price", max_digits=12)),
                ('close_price', models.DecimalField(decimal_places=4, help_text='Closing price', max_digits=12)),
                ('volume', models.BigIntegerField(help_text='Trading volume')),
                ('adjusted_close', models.DecimalField(blank=True, decimal_places=4, help_text='Dividend/split adjusted close', max_digits=12, null=True)),
                ('stock', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='price_history', to='core.stock')),
            ],
            options={
                'db_table': 'mapletrade_price_data',
                'ordering': ['-date'],
            },
        ),
        
        # Add indexes for AnalysisResult
        migrations.AddIndex(
            model_name='analysisresult',
            index=models.Index(fields=['stock', 'analysis_date'], name='mapletrade_analysis_stock_date_idx'),
        ),
        migrations.AddIndex(
            model_name='analysisresult',
            index=models.Index(fields=['analysis_date'], name='mapletrade_analysis_date_idx'),
        ),
        migrations.AddIndex(
            model_name='analysisresult',
            index=models.Index(fields=['signal'], name='mapletrade_analysis_signal_idx'),
        ),
        migrations.AddIndex(
            model_name='analysisresult',
            index=models.Index(fields=['stock', 'signal'], name='mapletrade_analysis_stock_signal_idx'),
        ),
        
        # Add indexes for PriceData
        migrations.AddIndex(
            model_name='pricedata',
            index=models.Index(fields=['stock', 'date'], name='mapletrade_price_stock_date_idx'),
        ),
        migrations.AddIndex(
            model_name='pricedata',
            index=models.Index(fields=['date'], name='mapletrade_price_date_idx'),
        ),
        
        # Add unique constraint for PriceData
        migrations.AddConstraint(
            model_name='pricedata',
            constraint=models.UniqueConstraint(fields=('stock', 'date'), name='unique_stock_price_date'),
        ),
        
        # Update PortfolioStock relationship if it exists
        # (This will only run if the field exists)
        migrations.RunSQL(
            "UPDATE mapletrade_portfolio_stocks SET portfolio_id = portfolio_id WHERE portfolio_id IS NOT NULL;",
            reverse_sql=migrations.RunSQL.noop,
            state_operations=[],
        ),
    ]