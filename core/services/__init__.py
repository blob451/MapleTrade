"""
Core Services Package.

This package contains the orchestration layer that coordinates
between data, analytics, and user services.
"""

from .orchestrator import CoreOrchestrator, OrchestratorError, get_orchestrator
from .cache_manager import CacheManager
from .transaction_manager import TransactionManager

# Legacy imports commented out to avoid import errors
# Uncomment only if you fix the imports in those files
# from .analytics_engine import AnalyticsEngine as LegacyAnalyticsEngine
# from .sector_mapping import SectorMapper as LegacySectorMapper

__all__ = [
    # New orchestration services
    'CoreOrchestrator',
    'OrchestratorError',
    'get_orchestrator',  # Added this
    'CacheManager',
    'TransactionManager',
]

# Version info
__version__ = '2.0.0'