"""
Add missing custom fields to User model.

This migration adds only the fields that don't already exist in the database.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        # Add phone_number field
        migrations.AddField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20, default=''),
            preserve_default=False,
        ),
        
        # Add date_of_birth field
        migrations.AddField(
            model_name='user',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
            preserve_default=True,
        ),
        
        # Update the meta options to set the custom table name
        migrations.AlterModelOptions(
            name='user',
            options={'db_table': 'mapletrade_users'},
        ),
    ]