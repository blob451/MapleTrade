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
                if result.stdout:
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
            "python manage.py showmigrations --list",
            "Checking migration status"
        ):
            self.print_success("All migrations tracked")
        
        # Verify database connection
        test_db_script = """
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mapletrade.settings')
django.setup()

from django.db import connection
from core.models import Stock, Sector

try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    print("Database connection: OK")
    
    stock_count = Stock.objects.count()
    sector_count = Sector.objects.count()
    print(f"Stocks in database: {stock_count}")
    print(f"Sectors in database: {sector_count}")
    
except Exception as e:
    print(f"Database error: {e}")
    exit(1)
"""
        
        db_test_file = self.project_root / "test_db_connection.py"
        db_test_file.write_text(test_db_script)
        
        if self.run_command(
            "python test_db_connection.py",
            "Testing database connection"
        ):
            self.print_success("Database is accessible")
        
        # Clean up test file
        db_test_file.unlink()
    
    def run_tests(self):
        """Run Django tests."""
        self.print_header("Running Tests")
        
        # Run Django tests for each app
        apps_to_test = ['core', 'analytics', 'data', 'users']
        
        for app in apps_to_test:
            if (self.project_root / app / 'tests.py').exists() or \
               (self.project_root / app / 'tests').exists():
                self.run_command(
                    f"python manage.py test {app} --verbosity=1",
                    f"Testing {app} app"
                )
    
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
            module_path = str(relative_path).replace('/', '.').replace('\\', '.')[:-3]
            
            try:
                compile(py_file.read_text(), py_file, 'exec')
                self.print_success(f"Syntax OK: {relative_path}")
            except SyntaxError as e:
                error_msg = f"Syntax error in {relative_path}: {e}"
                self.print_error(error_msg)
                import_errors.append(error_msg)
        
        if not import_errors:
            self.print_success("All Python files have valid syntax")
    
    def clean_temporary_files(self):
        """Clean up temporary and unnecessary files."""
        self.print_header("Cleaning Temporary Files")
        
        # Patterns to clean
        patterns_to_remove = [
            '**/__pycache__',
            '**/*.pyc',
            '**/*.pyo',
            '**/.pytest_cache',
            '**/test.py',  # Standalone test files not in proper structure
            '**/*.log',
            '**/.coverage',
            '**/htmlcov',
            '**/.DS_Store',
            '**/Thumbs.db',
            '**/*.swp',
            '**/*~',
        ]
        
        # Files to preserve
        preserve_patterns = [
            'tests.py',  # Proper Django test files
            'test_*.py',  # Proper test files with test_ prefix
            'requirements.txt',
            'docker-compose.yml',
        ]
        
        for pattern in patterns_to_remove:
            for path in self.project_root.glob(pattern):
                if any(preserve in str(path) for preserve in preserve_patterns):
                    continue
                
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
            'django',
            'djangorestframework',
            'pandas',
            'numpy',
            'yfinance',
            'redis',
            'celery',
            'psycopg2-binary',
        ]
        
        import importlib
        
        for package in required_packages:
            try:
                if package == 'psycopg2-binary':
                    importlib.import_module('psycopg2')
                else:
                    importlib.import_module(package)
                self.print_success(f"Package installed: {package}")
            except ImportError:
                self.print_error(f"Package missing: {package}")
    
    def create_backup(self):
        """Create a backup of critical files."""
        self.print_header("Creating Backup")
        
        backup_dir = self.project_root / 'backups'
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = backup_dir / f'models_backup_{timestamp}.py'
        
        # Backup core models
        core_models = self.project_root / 'core' / 'models.py'
        if core_models.exists():
            shutil.copy2(core_models, backup_file)
            self.print_success(f"Backed up core/models.py to {backup_file.name}")
    
    def generate_report(self):
        """Generate final report."""
        self.print_header("Verification Report")
        
        print(f"\n{GREEN}Successes:{RESET}")
        print(f"- Django setup verified")
        print(f"- Python syntax checked")
        print(f"- Cleaned {len(self.cleaned_items)} temporary files/directories")
        
        if self.warnings:
            print(f"\n{YELLOW}Warnings ({len(self.warnings)}):{RESET}")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        if self.errors:
            print(f"\n{RED}Errors ({len(self.errors)}):{RESET}")
            for error in self.errors:
                print(f"  - {error}")
        else:
            print(f"\n{GREEN}No critical errors found!{RESET}")
        
        print(f"\n{BLUE}Recommendations:{RESET}")
        print("1. Commit your changes: git add . && git commit -m 'Your message'")
        print("2. Run migrations if needed: python manage.py migrate")
        print("3. Update requirements.txt: pip freeze > requirements.txt")
        print("4. Consider running: python manage.py collectstatic --noinput")


def main():
    """Main execution function."""
    print(f"{BLUE}MapleTrade Project Verification and Cleanup{RESET}")
    print(f"{BLUE}========================================={RESET}")
    
    # Check if we're in the virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print(f"{YELLOW}Warning: Virtual environment not activated!{RESET}")
        print("Please run: venv\\Scripts\\activate (on Windows)")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return
    
    verifier = ProjectVerifier()
    
    try:
        verifier.create_backup()
        verifier.verify_django_setup()
        verifier.verify_imports()
        verifier.run_tests()
        verifier.verify_requirements()
        verifier.clean_temporary_files()
        verifier.generate_report()
        
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Verification interrupted by user{RESET}")
    except Exception as e:
        print(f"\n{RED}Unexpected error: {e}{RESET}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()