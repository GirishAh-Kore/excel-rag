"""
Cache Invalidation Service Module.

This module provides a service for invalidating query cache entries
when files are re-indexed. It follows the Observer pattern to decouple
cache invalidation from the indexing pipeline.

Supports Requirement 43.2: Invalidate cache entries on re-indexing.
"""

import logging
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# =============================================================================
# Protocols
# =============================================================================


@runtime_checkable
class QueryCacheProtocol(Protocol):
    """
    Protocol for query cache operations.
    
    Defines the interface for cache invalidation operations.
    """
    
    def invalidate_by_file(self, file_id: str) -> int:
        """Invalidate all cache entries containing a specific file."""
        ...
    
    def invalidate_by_files(self, file_ids: list[str]) -> int:
        """Invalidate cache entries for multiple files."""
        ...


@runtime_checkable
class IndexingEventListenerProtocol(Protocol):
    """
    Protocol for indexing event listeners.
    
    Implementations receive notifications when indexing events occur.
    """
    
    def on_file_indexed(self, file_id: str, file_name: str) -> None:
        """Called when a file is successfully indexed or re-indexed."""
        ...
    
    def on_file_removed(self, file_id: str) -> None:
        """Called when a file is removed from the index."""
        ...


# =============================================================================
# Cache Invalidation Service
# =============================================================================


class CacheInvalidationService:
    """
    Service for invalidating query cache entries on re-indexing.
    
    This service listens for indexing events and invalidates relevant
    cache entries to ensure stale data is not served.
    
    Implements Requirement 43.2: Invalidate all cache entries containing
    re-indexed file_id.
    
    Example:
        >>> invalidation_service = CacheInvalidationService(query_cache)
        >>> # Called by indexing pipeline after file is indexed
        >>> invalidation_service.on_file_indexed("file123", "sales.xlsx")
    """
    
    def __init__(
        self,
        query_cache: Optional[QueryCacheProtocol] = None
    ) -> None:
        """
        Initialize CacheInvalidationService.
        
        Args:
            query_cache: Optional query cache for invalidation.
                        If None, invalidation operations are no-ops.
        """
        self._query_cache = query_cache
        self._invalidation_count = 0
        
        if query_cache is None:
            logger.warning(
                "CacheInvalidationService initialized without query_cache. "
                "Cache invalidation will be disabled."
            )
        else:
            logger.info("CacheInvalidationService initialized")

    def on_file_indexed(self, file_id: str, file_name: str) -> None:
        """
        Handle file indexed event.
        
        Invalidates all cache entries that reference the indexed file.
        
        Args:
            file_id: The ID of the indexed file.
            file_name: The name of the indexed file (for logging).
            
        Implements Requirement 43.2.
        """
        if self._query_cache is None:
            return
        
        try:
            count = self._query_cache.invalidate_by_file(file_id)
            self._invalidation_count += count
            
            if count > 0:
                logger.info(
                    f"Invalidated {count} cache entries for re-indexed file: "
                    f"{file_name} (file_id={file_id})"
                )
            else:
                logger.debug(
                    f"No cache entries to invalidate for file: "
                    f"{file_name} (file_id={file_id})"
                )
                
        except Exception as e:
            logger.error(
                f"Error invalidating cache for file {file_name}: {e}",
                exc_info=True
            )

    def on_file_removed(self, file_id: str) -> None:
        """
        Handle file removed event.
        
        Invalidates all cache entries that reference the removed file.
        
        Args:
            file_id: The ID of the removed file.
        """
        if self._query_cache is None:
            return
        
        try:
            count = self._query_cache.invalidate_by_file(file_id)
            self._invalidation_count += count
            
            if count > 0:
                logger.info(
                    f"Invalidated {count} cache entries for removed file: "
                    f"file_id={file_id}"
                )
                
        except Exception as e:
            logger.error(
                f"Error invalidating cache for removed file {file_id}: {e}",
                exc_info=True
            )

    def on_files_indexed(self, file_ids: list[str]) -> None:
        """
        Handle multiple files indexed event.
        
        Invalidates all cache entries that reference any of the indexed files.
        
        Args:
            file_ids: List of file IDs that were indexed.
        """
        if self._query_cache is None:
            return
        
        try:
            count = self._query_cache.invalidate_by_files(file_ids)
            self._invalidation_count += count
            
            if count > 0:
                logger.info(
                    f"Invalidated {count} cache entries for {len(file_ids)} "
                    f"re-indexed files"
                )
                
        except Exception as e:
            logger.error(
                f"Error invalidating cache for {len(file_ids)} files: {e}",
                exc_info=True
            )

    def get_invalidation_count(self) -> int:
        """
        Get total number of cache entries invalidated.
        
        Returns:
            Total invalidation count since service creation.
        """
        return self._invalidation_count

    def reset_stats(self) -> None:
        """Reset invalidation statistics."""
        self._invalidation_count = 0
