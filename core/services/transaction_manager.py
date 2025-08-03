"""
Transaction management service for coordinating database operations.

Ensures data consistency across multiple service operations.
"""

import logging
from typing import Any, Callable, Optional, Dict, List  # Fixed import
from contextlib import contextmanager
from functools import wraps

from django.db import transaction, DatabaseError
from django.utils import timezone

logger = logging.getLogger(__name__)


class TransactionManager:
    """
    Manages database transactions across services.
    
    Provides utilities for atomic operations, savepoints,
    and coordinated rollbacks.
    """
    
    def __init__(self):
        self.active_transactions = {}
        self.transaction_count = 0
    
    @contextmanager
    def atomic(self, using: Optional[str] = None, savepoint: bool = True,
               durable: bool = False):
        """
        Context manager for atomic transactions.
        
        Args:
            using: Database alias
            savepoint: Use savepoint for nested transactions
            durable: Ensure durability (wait for commit)
            
        Yields:
            Transaction context
        """
        transaction_id = self._generate_transaction_id()
        start_time = timezone.now()
        
        try:
            logger.debug(f"Starting transaction {transaction_id}")
            self.active_transactions[transaction_id] = {
                'start_time': start_time,
                'using': using,
                'savepoint': savepoint
            }
            
            with transaction.atomic(using=using, savepoint=savepoint, durable=durable):
                yield transaction_id
            
            # Transaction succeeded
            duration = (timezone.now() - start_time).total_seconds()
            logger.debug(f"Transaction {transaction_id} committed ({duration:.2f}s)")
            
        except Exception as e:
            # Transaction failed
            duration = (timezone.now() - start_time).total_seconds()
            logger.error(f"Transaction {transaction_id} rolled back ({duration:.2f}s): {e}")
            raise
            
        finally:
            # Clean up
            self.active_transactions.pop(transaction_id, None)
    
    def atomic_operation(self, func: Callable) -> Callable:
        """
        Decorator for atomic operations.
        
        Args:
            func: Function to wrap
            
        Returns:
            Wrapped function
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.atomic():
                return func(*args, **kwargs)
        return wrapper
    
    @contextmanager
    def savepoint(self, using: Optional[str] = None):
        """
        Create a savepoint within a transaction.
        
        Args:
            using: Database alias
            
        Yields:
            Savepoint ID
        """
        if not transaction.get_connection(using).in_atomic_block:
            raise DatabaseError("Savepoint can only be used inside a transaction")
        
        sid = transaction.savepoint(using=using)
        
        try:
            yield sid
            transaction.savepoint_commit(sid, using=using)
            logger.debug(f"Savepoint {sid} committed")
        except Exception as e:
            transaction.savepoint_rollback(sid, using=using)
            logger.debug(f"Savepoint {sid} rolled back: {e}")
            raise
    
    def execute_in_transaction(self, operations: List[Callable],
                              rollback_on_error: bool = True) -> List[Any]:
        """
        Execute multiple operations in a single transaction.
        
        Args:
            operations: List of callables to execute
            rollback_on_error: Rollback all on any error
            
        Returns:
            List of operation results
        """
        results = []
        
        try:
            with self.atomic():
                for i, operation in enumerate(operations):
                    try:
                        result = operation()
                        results.append(result)
                        logger.debug(f"Operation {i+1}/{len(operations)} succeeded")
                    except Exception as e:
                        logger.error(f"Operation {i+1} failed: {e}")
                        if rollback_on_error:
                            raise
                        results.append(None)
            
            return results
            
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            raise
    
    def batch_create(self, model_class: Any, objects: List[Dict],
                    batch_size: int = 1000) -> int:
        """
        Efficiently create multiple objects.
        
        Args:
            model_class: Django model class
            objects: List of object data
            batch_size: Batch size for bulk_create
            
        Returns:
            Number of objects created
        """
        created_count = 0
        
        try:
            with self.atomic():
                for i in range(0, len(objects), batch_size):
                    batch = objects[i:i + batch_size]
                    instances = [model_class(**obj) for obj in batch]
                    model_class.objects.bulk_create(instances)
                    created_count += len(instances)
                    logger.debug(f"Created batch of {len(instances)} {model_class.__name__} objects")
            
            logger.info(f"Successfully created {created_count} {model_class.__name__} objects")
            return created_count
            
        except Exception as e:
            logger.error(f"Batch create failed: {e}")
            raise
    
    def batch_update(self, model_class: Any, updates: List[Dict],
                    batch_size: int = 1000) -> int:
        """
        Efficiently update multiple objects.
        
        Args:
            model_class: Django model class
            updates: List of dicts with 'id' and fields to update
            batch_size: Batch size for bulk_update
            
        Returns:
            Number of objects updated
        """
        updated_count = 0
        
        try:
            with self.atomic():
                # Get all objects to update
                ids = [u['id'] for u in updates]
                objects = {obj.id: obj for obj in model_class.objects.filter(id__in=ids)}
                
                # Apply updates
                updated_objects = []
                update_fields = set()
                
                for update in updates:
                    obj_id = update.pop('id')
                    if obj_id in objects:
                        obj = objects[obj_id]
                        for field, value in update.items():
                            setattr(obj, field, value)
                            update_fields.add(field)
                        updated_objects.append(obj)
                
                # Bulk update in batches
                if updated_objects and update_fields:
                    for i in range(0, len(updated_objects), batch_size):
                        batch = updated_objects[i:i + batch_size]
                        model_class.objects.bulk_update(batch, update_fields)
                        updated_count += len(batch)
                        logger.debug(f"Updated batch of {len(batch)} {model_class.__name__} objects")
            
            logger.info(f"Successfully updated {updated_count} {model_class.__name__} objects")
            return updated_count
            
        except Exception as e:
            logger.error(f"Batch update failed: {e}")
            raise
    
    def ensure_atomic(self, func: Callable) -> Any:
        """
        Ensure a function runs in an atomic block.
        
        If already in a transaction, uses a savepoint.
        Otherwise, starts a new transaction.
        
        Args:
            func: Function to execute
            
        Returns:
            Function result
        """
        if transaction.get_connection().in_atomic_block:
            # Already in transaction, use savepoint
            with self.savepoint():
                return func()
        else:
            # Start new transaction
            with self.atomic():
                return func()
    
    def get_active_transactions(self) -> Dict[str, Dict]:
        """
        Get information about active transactions.
        
        Returns:
            Dictionary of active transactions
        """
        now = timezone.now()
        
        return {
            tid: {
                **info,
                'duration': (now - info['start_time']).total_seconds()
            }
            for tid, info in self.active_transactions.items()
        }
    
    def _generate_transaction_id(self) -> str:
        """Generate unique transaction ID."""
        self.transaction_count += 1
        return f"txn_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{self.transaction_count}"
    
    @contextmanager
    def distributed_transaction(self, participants: List[str]):
        """
        Context manager for distributed transactions (placeholder).
        
        This is a placeholder for future distributed transaction support.
        Currently just ensures all operations use the same database.
        
        Args:
            participants: List of service names participating
            
        Yields:
            Transaction context
        """
        transaction_id = self._generate_transaction_id()
        logger.info(f"Starting distributed transaction {transaction_id} with participants: {participants}")
        
        try:
            with self.atomic():
                yield transaction_id
            logger.info(f"Distributed transaction {transaction_id} completed successfully")
        except Exception as e:
            logger.error(f"Distributed transaction {transaction_id} failed: {e}")
            raise