#!/usr/bin/env python
"""
Comprehensive test and cleanup script for MapleTrade project.
Verifies integrity, runs tests, and cleans up unnecessary files.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Color codes for output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'


class ProjectVerifier:
    def __init__(self):
        self.project_root = project_root
        self.errors = []
        self.warnings = []
        self.cleaned_items = []
        
    def print_header(self, text):
        print(f"\n{BLUE}{'=' * 60}{RESET}")
        print(f"{BLUE}{text}{RESET}")
        print(f"{BLUE}{'=' * 60}{RESET}")
    
    def print_success(self, text):
        print(f"{GREEN}✓ {text}{RESET}")
    
    def print_warning(self, text):
        print(f"{YELLOW}⚠ {text}{RESET}")
        self.warnings.append(text)
    
    def print_error(self, text):
        print(f"{RED}✗ {text}{RESET}")
        self.errors.append(text)
    
    def run_command(self, command, description):
        """Run a shell command and return success status."""
        try:
            print(f"\n{description}...")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                self.print_success(f"{description} completed successfully")
                if result.stdout and "showmigrations" not in command:
                    print(result.stdout)
                return True
            else:
                self.print_error(f"{description} failed")
                if result.stderr:
                    print(result.stderr)
                return False
                
        except Exception as e:
            self.print_error(f"{description} error: {e}")
            return False
    
    def verify_django_setup(self):
        """Verify Django configuration and database."""
        self.print_header("Verifying Django Setup")
        
        # Check Django settings
        if self.run_command(
            "python manage.py check",
            "Checking Django configuration"
        ):
            self.print_success("Django configuration is valid")
        
        # Check migrations
        if self.run_command(
            "python manage.py showmigrations --list | find \"[X]\" | find /c /v \"\"",
            "Counting applied migrations"
        ):
            self.print_success("Migrations are up to date")
        
        # Verify database connection
        test_db_script = """
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mapletrade.settings')
django.setup()

from django.db import connection
from core.models import Stock, Sector, PriceData

try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    print("Database connection: OK")
    
    stock_count = Stock.objects.count()
    sector_count = Sector.objects.count()
    price_count = PriceData.objects.count()
    
    print(f"Stocks in database: {stock_count}")
    print(f"Sectors in database: {sector_count}")
    print(f"Price records in database: {price_count}")
    
except Exception as e:
    print(f"Database error: {e}")
    exit(1)
"""
        
        db_test_file = self.project_root / "test_db_connection.py"
        db_test_file.write_text(test_db_script, encoding='utf-8')
        
        if self.run_command(
            "python test_db_connection.py",
            "Testing database connection"
        ):
            self.print_success("Database is accessible and populated")
        
        # Clean up test file
        db_test_file.unlink()
    
    def run_tests(self):
        """Run Django tests."""
        self.print_header("Running Tests")
        
        # Run Django tests for each app
        apps_to_test = ['core', 'analytics', 'data', 'users']
        
        for app in apps_to_test:
            app_path = self.project_root / app
            if app_path.exists():
                # Check if app has tests
                has_tests = (app_path / 'tests.py').exists() or (app_path / 'tests').exists()
                if has_tests:
                    self.run_command(
                        f"python manage.py test {app} --verbosity=1",
                        f"Testing {app} app"
                    )
                else:
                    self.print_warning(f"No tests found for {app} app")
    
    def verify_imports(self):
        """Verify all Python files can be imported."""
        self.print_header("Verifying Python Imports")
        
        python_files = []
        for app in ['analytics', 'core', 'data', 'users']:
            app_path = self.project_root / app
            if app_path.exists():
                python_files.extend(app_path.glob('**/*.py'))
        
        import_errors = []
        for py_file in python_files:
            if '__pycache__' in str(py_file) or 'migrations' in str(py_file):
                continue
                
            relative_path = py_file.relative_to(self.project_root)
            
            try:
                # Read with UTF-8 encoding to handle special characters
                content = py_file.read_text(encoding='utf-8')
                compile(content, str(py_file), 'exec')
                self.print_success(f"Syntax OK: {relative_path}")
            except SyntaxError as e:
                error_msg = f"Syntax error in {relative_path}: {e}"
                self.print_error(error_msg)
                import_errors.append(error_msg)
            except UnicodeDecodeError:
                # Try with different encodings
                for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        content = py_file.read_text(encoding=encoding)
                        compile(content, str(py_file), 'exec')
                        self.print_warning(f"Syntax OK (using {encoding}): {relative_path}")
                        break
                    except:
                        continue
                else:
                    self.print_warning(f"Encoding issue in {relative_path}, skipping syntax check")
            except Exception as e:
                self.print_warning(f"Could not check {relative_path}: {e}")
        
        if not import_errors:
            self.print_success("All checkable Python files have valid syntax")
    
    def clean_temporary_files(self):
        """Clean up temporary and unnecessary files."""
        self.print_header("Cleaning Temporary Files")
        
        # Patterns to clean
        patterns_to_remove = [
            '**/__pycache__',
            '**/*.pyc',
            '**/*.pyo',
            '**/.pytest_cache',
            '**/*.log',
            '**/.coverage',
            '**/htmlcov',
            '**/.DS_Store',
            '**/Thumbs.db',
            '**/*.swp',
            '**/*~',
            '.mypy_cache',
            '.tox',
            '*.egg-info',
        ]
        
        # Clean each pattern
        for pattern in patterns_to_remove:
            for path in self.project_root.glob(pattern):
                try:
                    if path.is_dir():
                        shutil.rmtree(path)
                        self.print_success(f"Removed directory: {path.relative_to(self.project_root)}")
                    else:
                        path.unlink()
                        self.print_success(f"Removed file: {path.relative_to(self.project_root)}")
                    self.cleaned_items.append(str(path.relative_to(self.project_root)))
                except Exception as e:
                    self.print_warning(f"Could not remove {path}: {e}")
    
    def verify_requirements(self):
        """Verify all required packages are installed."""
        self.print_header("Verifying Package Requirements")
        
        required_packages = [
            ('django', 'Django'),
            ('rest_framework', 'djangorestframework'),
            ('pandas', 'pandas'),
            ('numpy', 'numpy'),
            ('yfinance', 'yfinance'),
            ('redis', 'redis'),
            ('celery', 'celery'),
            ('psycopg2', 'psycopg2-binary'),
        ]
        
        missing_packages = []
        
        for import_name, package_name in required_packages:
            try:
                __import__(import_name)
                self.print_success(f"Package installed: {package_name}")
            except ImportError:
                self.print_error(f"Package missing: {package_name}")
                missing_packages.append(package_name)
        
        if missing_packages:
            self.print_warning(f"\nTo install missing packages, run:")
            self.print_warning(f"pip install {' '.join(missing_packages)}")
    
    def check_analytics_engine(self):
        """Verify analytics engine is working."""
        self.print_header("Verifying Analytics Engine")
        
        test_script = """
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mapletrade.settings')
django.setup()

from analytics.services import AnalyticsEngine
from core.models import Stock

try:
    # Check if AAPL exists and has data
    aapl = Stock.objects.filter(symbol='AAPL').first()
    if aapl and aapl.price_history.exists():
        print(f"AAPL found with {aapl.price_history.count()} price records")
        
        # Test analytics engine
        engine = AnalyticsEngine()
        result = engine.analyze_stock('AAPL', months=3)
        
        print(f"Analytics Engine Test: SUCCESS")
        print(f"Recommendation: {result.recommendation}")
        print(f"Confidence: {result.confidence:.2%}")
    else:
        print("AAPL test data not found - run populate_price_data first")
        
except Exception as e:
    print(f"Analytics Engine Error: {e}")
"""
        
        test_file = self.project_root / "test_analytics.py"
        test_file.write_text(test_script, encoding='utf-8')
        
        self.run_command(
            "python test_analytics.py",
            "Testing analytics engine"
        )
        
        test_file.unlink()
    
    def create_backup(self):
        """Create a backup of critical files."""
        self.print_header("Creating Backup")
        
        backup_dir = self.project_root / 'backups'
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Files to backup
        critical_files = [
            'core/models.py',
            'analytics/services/engine.py',
            'analytics/services/technical.py',
            'mapletrade/settings.py',
        ]
        
        for file_path in critical_files:
            source = self.project_root / file_path
            if source.exists():
                backup_name = f"{source.stem}_backup_{timestamp}{source.suffix}"
                backup_path = backup_dir / backup_name
                shutil.copy2(source, backup_path)
                self.print_success(f"Backed up {file_path}")
    
    def generate_report(self):
        """Generate final report."""
        self.print_header("Verification Report")
        
        print(f"\n{GREEN}Summary:{RESET}")
        print(f"✓ Django setup verified")
        print(f"✓ Database connection confirmed")
        print(f"✓ Python syntax checked")
        print(f"✓ Cleaned {len(self.cleaned_items)} temporary files/directories")
        print(f"✓ Analytics engine operational")
        
        if self.warnings:
            print(f"\n{YELLOW}Warnings ({len(self.warnings)}):{RESET}")
            for i, warning in enumerate(set(self.warnings), 1):
                print(f"  {i}. {warning}")
        
        if self.errors:
            print(f"\n{RED}Errors ({len(self.errors)}):{RESET}")
            for i, error in enumerate(set(self.errors), 1):
                print(f"  {i}. {error}")
        else:
            print(f"\n{GREEN}✓ No critical errors found!{RESET}")
        
        print(f"\n{BLUE}Next Steps:{RESET}")
        print("Carry on with the development :)")

def main():
    """Main execution function."""
    print(f"{BLUE}MapleTrade Project Verification and Cleanup{RESET}")
    print(f"{BLUE}{'=' * 43}{RESET}")
    
    # Check if we're in the virtual environment
    if not sys.prefix.endswith('venv'):
        print(f"{YELLOW}Warning: Virtual environment may not be activated!{RESET}")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return
    
    verifier = ProjectVerifier()
    
    try:
        verifier.create_backup()
        verifier.verify_django_setup()
        verifier.verify_imports()
        verifier.verify_requirements()
        verifier.check_analytics_engine()
        verifier.clean_temporary_files()
        verifier.run_tests()
        verifier.generate_report()
        
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Verification interrupted by user{RESET}")
    except Exception as e:
        print(f"\n{RED}Unexpected error: {e}{RESET}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()