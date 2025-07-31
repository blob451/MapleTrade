#!/usr/bin/env python3
"""
MapleTrade Project Cleanup Script for Windows
Handles permission errors and provides better Windows compatibility
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

class WindowsProjectCleaner:
    def __init__(self, project_root='.'):
        self.project_root = Path(project_root).resolve()
        self.removed_count = 0
        self.failed_count = 0
        self.removed_size = 0
        self.in_venv = self.check_if_in_venv()
        
    def check_if_in_venv(self):
        """Check if we're running inside a virtual environment"""
        return hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        )
        
    def log(self, message, emoji="", level="info"):
        """Print formatted log message"""
        if level == "error":
            print(f"❌ {message}")
        elif level == "warning":
            print(f"⚠️  {message}")
        else:
            print(f"{emoji} {message}" if emoji else message)
            
    def get_size(self, path):
        """Get size of file or directory in bytes"""
        try:
            if path.is_file():
                return path.stat().st_size
            elif path.is_dir():
                return sum(f.stat().st_size for f in path.glob('**/*') if f.is_file())
        except:
            return 0
            
    def force_remove_readonly(self, path):
        """Remove read-only attribute and delete"""
        try:
            os.chmod(path, 0o777)
            if path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
            return True
        except:
            return False
            
    def safe_remove(self, path):
        """Safely remove file or directory with Windows permission handling"""
        path = Path(path)
        if not path.exists():
            return
            
        # Skip if it's in the virtual environment and we're running from venv
        if self.in_venv and str(path).startswith(str(Path(sys.prefix))):
            return
            
        size = self.get_size(path)
        
        try:
            if path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
            self.removed_count += 1
            self.removed_size += size
            self.log(f"✓ Removed: {path.relative_to(self.project_root)}", level="info")
        except PermissionError:
            # Try to remove read-only attribute and retry
            if self.force_remove_readonly(path):
                self.removed_count += 1
                self.removed_size += size
                self.log(f"✓ Removed (forced): {path.relative_to(self.project_root)}", level="info")
            else:
                self.failed_count += 1
        except Exception as e:
            self.failed_count += 1
            
    def clean_pycache(self):
        """Remove Python cache files, excluding venv if we're in it"""
        self.log("Cleaning Python cache files...", "📦")
        
        # Exclude patterns
        exclude_dirs = []
        if self.in_venv:
            venv_path = Path(sys.prefix)
            exclude_dirs.append(venv_path)
            
        # Clean __pycache__ directories
        for pycache in self.project_root.rglob('__pycache__'):
            # Skip if in excluded directories
            if any(str(pycache).startswith(str(excl)) for excl in exclude_dirs):
                continue
            self.safe_remove(pycache)
            
        # Clean .pyc files
        for pyc in self.project_root.glob('**/*.pyc'):
            if any(str(pyc).startswith(str(excl)) for excl in exclude_dirs):
                continue
            self.safe_remove(pyc)
            
    def clean_django_files(self):
        """Remove Django specific temporary files"""
        self.log("Cleaning Django files...", "🎯")
        
        # Database files
        for db_file in ['db.sqlite3', 'db.sqlite3-journal']:
            self.safe_remove(self.project_root / db_file)
            
        # Static and media directories
        for dir_name in ['staticfiles', 'media']:
            dir_path = self.project_root / dir_name
            if dir_path.exists() and dir_path.is_dir():
                self.safe_remove(dir_path)
                
    def clean_logs(self, days_to_keep=7):
        """Clean old log files"""
        self.log(f"Cleaning log files older than {days_to_keep} days...", "📋")
        
        logs_dir = self.project_root / 'logs'
        if logs_dir.exists():
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            for log_file in logs_dir.glob('*.log'):
                try:
                    mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if mtime < cutoff_date:
                        self.safe_remove(log_file)
                except:
                    pass
                    
    def clean_ide_files(self):
        """Remove IDE specific files"""
        self.log("Cleaning IDE files...", "💻")
        
        # IDE directories
        for ide_dir in ['.vscode', '.idea', '.sublime-project']:
            self.safe_remove(self.project_root / ide_dir)
            
        # IDE files
        for pattern in ['*.swp', '*.swo', '*~', '*.bak']:
            for file in self.project_root.glob(f'**/{pattern}'):
                self.safe_remove(file)
                
    def clean_os_files(self):
        """Remove OS specific files"""
        self.log("Cleaning OS-specific files...", "🖥️")
        
        patterns = [
            '.DS_Store', '.DS_Store?', '._*', 'Thumbs.db', 
            'ehthumbs.db', 'desktop.ini'
        ]
        
        for pattern in patterns:
            for file in self.project_root.rglob(pattern):
                self.safe_remove(file)
                
    def clean_test_artifacts(self):
        """Remove test and coverage artifacts"""
        self.log("Cleaning test artifacts...", "🧪")
        
        artifacts = [
            '.coverage', '.pytest_cache', 'htmlcov',
            '.tox', '.nox', '.hypothesis'
        ]
        
        for artifact in artifacts:
            self.safe_remove(self.project_root / artifact)
            
        # Coverage files
        for cov_file in self.project_root.glob('.coverage.*'):
            self.safe_remove(cov_file)
            
    def clean_build_artifacts(self):
        """Remove build artifacts"""
        self.log("Cleaning build artifacts...", "🏗️")
        
        dirs = ['build', 'dist', 'target', '.eggs']
        for dir_name in dirs:
            self.safe_remove(self.project_root / dir_name)
            
        # Egg info
        for egg_info in self.project_root.glob('*.egg-info'):
            self.safe_remove(egg_info)
            
    def clean_docker_volumes(self):
        """Clean Docker volumes and containers"""
        self.log("Checking Docker cleanup...", "🐳")
        
        try:
            # Check if docker-compose.yml exists
            compose_file = self.project_root / 'docker-compose.yml'
            if not compose_file.exists():
                return
                
            # Check if Docker is running
            result = subprocess.run(['docker', 'info'], 
                                  capture_output=True, 
                                  text=True,
                                  shell=True)
            
            if result.returncode == 0:
                self.log("Docker is running. To clean Docker volumes:")
                self.log("  docker-compose down -v", level="info")
            else:
                self.log("Docker is not running or not installed", level="warning")
                
        except Exception as e:
            self.log("Could not check Docker status", level="warning")
            
    def format_size(self, bytes):
        """Format bytes to human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.2f} TB"
        
    def generate_gitignore(self):
        """Generate recommended .gitignore entries"""
        return """
# Add these to your .gitignore file:

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv/

# Django
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal
media/
staticfiles/

# Testing
.coverage
.pytest_cache/
htmlcov/
.tox/
.hypothesis/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
"""

    def run(self, keep_logs_days=7):
        """Run cleanup operations"""
        self.log("🧹 Starting MapleTrade project cleanup for Windows...")
        
        if self.in_venv:
            self.log("📍 Running from virtual environment - will skip venv cleanup", level="warning")
        
        self.log("")
        
        # Run cleanup operations
        self.clean_pycache()
        self.clean_django_files()
        self.clean_logs(keep_logs_days)
        self.clean_ide_files()
        self.clean_os_files()
        self.clean_test_artifacts()
        self.clean_build_artifacts()
        self.clean_docker_volumes()
        
        # Summary
        self.log("")
        self.log("✅ Cleanup complete!")
        self.log("")
        self.log("📊 Cleanup summary:")
        self.log(f"  - Files/directories removed: {self.removed_count}")
        self.log(f"  - Failed removals: {self.failed_count}")
        self.log(f"  - Space freed: {self.format_size(self.removed_size)}")
        
        if self.failed_count > 0:
            self.log("")
            self.log("⚠️  Some files could not be removed (likely in use)", level="warning")
            self.log("  Try closing all applications and running again", level="warning")
            
        self.log("")
        self.log("💡 Recommendations:")
        self.log("  1. Run 'git status' to verify no important files were removed")
        self.log("  2. Deactivate venv and run again to clean virtual environment")
        self.log("  3. Close IDEs and terminals to release file locks")
        self.log("  4. Update your .gitignore file with recommended entries")
        
        # Offer to show gitignore recommendations
        self.log("")
        show_gitignore = input("Would you like to see recommended .gitignore entries? (y/n): ")
        if show_gitignore.lower() == 'y':
            print(self.generate_gitignore())


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Clean up MapleTrade project files (Windows optimized)"
    )
    parser.add_argument(
        '--path', '-p',
        default='.',
        help='Project root path (default: current directory)'
    )
    parser.add_argument(
        '--keep-logs',
        type=int,
        default=7,
        help='Number of days to keep log files (default: 7)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force removal of virtual environment even if active'
    )
    
    args = parser.parse_args()
    
    cleaner = WindowsProjectCleaner(args.path)
    
    if args.force:
        cleaner.in_venv = False
        
    cleaner.run(args.keep_logs)


if __name__ == "__main__":
    main()