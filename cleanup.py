#!/usr/bin/env python3
"""
MapleTrade Project Cleanup Script
Removes unnecessary cache files, logs, and temporary files
while preserving important project structure.
"""

import os
import shutil
import sys
from pathlib import Path
from datetime import datetime, timedelta

class ProjectCleaner:
    def __init__(self, project_root='.'):
        self.project_root = Path(project_root)
        self.removed_count = 0
        self.removed_size = 0
        
    def log(self, message, emoji=""):
        """Print formatted log message"""
        print(f"{emoji} {message}" if emoji else message)
        
    def get_size(self, path):
        """Get size of file or directory in bytes"""
        if path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            return sum(f.stat().st_size for f in path.glob('**/*') if f.is_file())
        return 0
        
    def safe_remove(self, path):
        """Safely remove file or directory"""
        path = Path(path)
        if path.exists():
            size = self.get_size(path)
            try:
                if path.is_file():
                    path.unlink()
                else:
                    shutil.rmtree(path)
                self.removed_count += 1
                self.removed_size += size
                self.log(f"  ✓ Removed: {path}")
            except Exception as e:
                self.log(f"  ✗ Failed to remove {path}: {e}")
                
    def find_and_remove(self, pattern, file_type='f'):
        """Find and remove files matching pattern"""
        if file_type == 'f':
            for file in self.project_root.rglob(pattern):
                if file.is_file():
                    self.safe_remove(file)
        elif file_type == 'd':
            for dir in self.project_root.rglob(pattern):
                if dir.is_dir():
                    self.safe_remove(dir)
                    
    def clean_python_cache(self):
        """Remove Python cache and compiled files"""
        self.log("Cleaning Python cache files...", "📦")
        
        # __pycache__ directories
        self.find_and_remove('__pycache__', 'd')
        
        # Compiled Python files
        patterns = ['*.pyc', '*.pyo', '*.pyd', '*$py.class', '*.so']
        for pattern in patterns:
            self.find_and_remove(pattern)
            
    def clean_django_files(self):
        """Remove Django specific temporary files"""
        self.log("Cleaning Django files...", "🎯")
        
        files = ['db.sqlite3', 'db.sqlite3-journal']
        dirs = ['staticfiles', 'media']
        
        for file in files:
            self.safe_remove(self.project_root / file)
            
        for dir in dirs:
            self.safe_remove(self.project_root / dir)
            
    def clean_logs(self, days_to_keep=7):
        """Clean old log files"""
        self.log(f"Cleaning log files older than {days_to_keep} days...", "📋")
        
        logs_dir = self.project_root / 'logs'
        if logs_dir.exists():
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            for log_file in logs_dir.glob('*.log'):
                if datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff_date:
                    self.safe_remove(log_file)
                    
    def clean_virtual_envs(self):
        """Remove virtual environment directories"""
        self.log("Checking for virtual environments...", "🐍")
        
        venv_dirs = ['venv', 'env', 'ENV', '.venv', '.env']
        for venv in venv_dirs:
            self.safe_remove(self.project_root / venv)
            
    def clean_ide_files(self):
        """Remove IDE specific files"""
        self.log("Cleaning IDE files...", "💻")
        
        ide_dirs = ['.vscode', '.idea', '.sublime-project', '.sublime-workspace']
        ide_files = ['*.swp', '*.swo', '*~', '*.bak']
        
        for dir in ide_dirs:
            self.safe_remove(self.project_root / dir)
            
        for pattern in ide_files:
            self.find_and_remove(pattern)
            
    def clean_os_files(self):
        """Remove OS specific files"""
        self.log("Cleaning OS-specific files...", "🖥️")
        
        os_patterns = [
            '.DS_Store', '.DS_Store?', '._*', '.Spotlight-V100',
            '.Trashes', 'ehthumbs.db', 'Thumbs.db', 'desktop.ini'
        ]
        
        for pattern in os_patterns:
            self.find_and_remove(pattern)
            
    def clean_test_artifacts(self):
        """Remove test and coverage artifacts"""
        self.log("Cleaning test artifacts...", "🧪")
        
        artifacts = [
            'htmlcov', '.coverage', '.pytest_cache', '.tox',
            '.nox', '.hypothesis', 'nosetests.xml', 'coverage.xml'
        ]
        
        for artifact in artifacts:
            self.safe_remove(self.project_root / artifact)
            
        # Coverage files with wildcards
        for cov_file in self.project_root.glob('.coverage.*'):
            self.safe_remove(cov_file)
            
    def clean_jupyter(self):
        """Remove Jupyter notebook artifacts"""
        self.log("Cleaning Jupyter artifacts...", "📓")
        self.find_and_remove('.ipynb_checkpoints', 'd')
        
    def clean_celery(self):
        """Remove Celery specific files"""
        self.log("Cleaning Celery files...", "🥬")
        
        celery_files = ['celerybeat-schedule', 'celerybeat.pid', 'celerybeat-schedule.db']
        for file in celery_files:
            self.safe_remove(self.project_root / file)
            
    def clean_node_modules(self):
        """Remove Node.js artifacts"""
        self.log("Checking for Node.js artifacts...", "📦")
        
        self.safe_remove(self.project_root / 'node_modules')
        
        npm_logs = ['npm-debug.log', 'yarn-debug.log', 'yarn-error.log']
        for log in npm_logs:
            self.find_and_remove(f"{log}*")
            
    def clean_build_artifacts(self):
        """Remove build artifacts"""
        self.log("Cleaning build artifacts...", "🏗️")
        
        build_dirs = ['build', 'dist', 'target', 'out']
        for dir in build_dirs:
            self.safe_remove(self.project_root / dir)
            
        # Egg info directories
        for egg_info in self.project_root.glob('*.egg-info'):
            self.safe_remove(egg_info)
            
    def format_size(self, bytes):
        """Format bytes to human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.2f} TB"
        
    def run(self, keep_logs_days=7):
        """Run all cleanup operations"""
        self.log("🧹 Starting MapleTrade project cleanup...")
        self.log("")
        
        # Run all cleanup methods
        self.clean_python_cache()
        self.clean_django_files()
        self.clean_logs(keep_logs_days)
        self.clean_virtual_envs()
        self.clean_ide_files()
        self.clean_os_files()
        self.clean_test_artifacts()
        self.clean_jupyter()
        self.clean_celery()
        self.clean_node_modules()
        self.clean_build_artifacts()
        
        # Summary
        self.log("")
        self.log("✅ Cleanup complete!")
        self.log("")
        self.log("📊 Cleanup summary:")
        self.log(f"  - Files/directories removed: {self.removed_count}")
        self.log(f"  - Space freed: {self.format_size(self.removed_size)}")
        self.log("")
        self.log("💡 Tips:")
        self.log("  - Run 'git status' to verify no important files were removed")
        self.log("  - Consider adding a pre-commit hook to prevent cache files")
        self.log("  - Use 'docker-compose down -v' to clean Docker volumes if needed")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Clean up MapleTrade project files"
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
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be deleted")
        print("")
    
    cleaner = ProjectCleaner(args.path)
    
    if not args.dry_run:
        cleaner.run(args.keep_logs)
    else:
        print("Dry run not implemented yet. Run without --dry-run to clean.")


if __name__ == "__main__":
    main()