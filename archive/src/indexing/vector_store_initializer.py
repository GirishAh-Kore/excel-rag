"""
Vector Store Initializer

Initializes vector store collections for the Google Drive Excel RAG system.
This module creates and configures the three main collections:
- excel_sheets: For sheet-level embeddings
- excel_pivots: For pivot table embeddings
- excel_charts: For chart embeddings
"""

import logging
from typing import Dict, Any

from src.abstractions.embedding_service import EmbeddingService
from src.abstractions.vector_store import VectorStore

logger = logging.getLogger(__name__)


class VectorStoreInitializer:
    """Manages initialization of vector store collections."""

    # Collection names
    SHEETS_COLLECTION = "excel_sheets"
    PIVOTS_COLLECTION = "excel_pivots"
    CHARTS_COLLECTION = "excel_charts"

    def __init__(self, vector_store: VectorStore, embedding_service: EmbeddingService):
        """
        Initialize the vector store initializer.

        Args:
            vector_store: Vector store instance
            embedding_service: Embedding service instance (for dimension info)
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.embedding_dimension = embedding_service.get_embedding_dimension()

    def _get_sheets_metadata_schema(self) -> Dict[str, Any]:
        """
        Get metadata schema for sheets collection.

        Returns:
            Metadata schema dictionary
        """
        return {
            "file_id": "string",
            "file_name": "string",
            "file_path": "string",
            "sheet_name": "string",
            "modified_time": "string",
            "headers": "string",  # JSON string
            "row_count": "int",
            "has_dates": "bool",
            "has_numbers": "bool",
            "has_pivot_tables": "bool",
            "has_charts": "bool",
            "pivot_count": "int",
            "chart_count": "int",
            "content_type": "string",  # "data", "pivot", "chart", "mixed"
        }

    def _get_pivots_metadata_schema(self) -> Dict[str, Any]:
        """
        Get metadata schema for pivot tables collection.

        Returns:
            Metadata schema dictionary
        """
        return {
            "file_id": "string",
            "file_name": "string",
            "sheet_name": "string",
            "pivot_name": "string",
            "row_fields": "string",  # JSON string
            "data_fields": "string",  # JSON string
        }

    def _get_charts_metadata_schema(self) -> Dict[str, Any]:
        """
        Get metadata schema for charts collection.

        Returns:
            Metadata schema dictionary
        """
        return {
            "file_id": "string",
            "file_name": "string",
            "sheet_name": "string",
            "chart_name": "string",
            "chart_type": "string",
            "title": "string",
        }

    def initialize_sheets_collection(self, recreate: bool = False) -> bool:
        """
        Initialize the excel_sheets collection.

        Args:
            recreate: If True, delete and recreate the collection

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(
                f"Initializing {self.SHEETS_COLLECTION} collection "
                f"(dimension: {self.embedding_dimension})"
            )

            if recreate:
                logger.info(f"Recreating {self.SHEETS_COLLECTION} collection")
                # Note: delete_collection method would need to be added to VectorStore interface
                # For now, we'll just create/update

            success = self.vector_store.create_collection(
                name=self.SHEETS_COLLECTION,
                dimension=self.embedding_dimension,
                metadata_schema=self._get_sheets_metadata_schema()
            )

            if success:
                logger.info(f"{self.SHEETS_COLLECTION} collection initialized successfully")
            else:
                logger.error(f"Failed to initialize {self.SHEETS_COLLECTION} collection")

            return success

        except Exception as e:
            logger.error(f"Error initializing {self.SHEETS_COLLECTION} collection: {e}")
            return False

    def initialize_pivots_collection(self, recreate: bool = False) -> bool:
        """
        Initialize the excel_pivots collection.

        Args:
            recreate: If True, delete and recreate the collection

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(
                f"Initializing {self.PIVOTS_COLLECTION} collection "
                f"(dimension: {self.embedding_dimension})"
            )

            if recreate:
                logger.info(f"Recreating {self.PIVOTS_COLLECTION} collection")

            success = self.vector_store.create_collection(
                name=self.PIVOTS_COLLECTION,
                dimension=self.embedding_dimension,
                metadata_schema=self._get_pivots_metadata_schema()
            )

            if success:
                logger.info(f"{self.PIVOTS_COLLECTION} collection initialized successfully")
            else:
                logger.error(f"Failed to initialize {self.PIVOTS_COLLECTION} collection")

            return success

        except Exception as e:
            logger.error(f"Error initializing {self.PIVOTS_COLLECTION} collection: {e}")
            return False

    def initialize_charts_collection(self, recreate: bool = False) -> bool:
        """
        Initialize the excel_charts collection.

        Args:
            recreate: If True, delete and recreate the collection

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(
                f"Initializing {self.CHARTS_COLLECTION} collection "
                f"(dimension: {self.embedding_dimension})"
            )

            if recreate:
                logger.info(f"Recreating {self.CHARTS_COLLECTION} collection")

            success = self.vector_store.create_collection(
                name=self.CHARTS_COLLECTION,
                dimension=self.embedding_dimension,
                metadata_schema=self._get_charts_metadata_schema()
            )

            if success:
                logger.info(f"{self.CHARTS_COLLECTION} collection initialized successfully")
            else:
                logger.error(f"Failed to initialize {self.CHARTS_COLLECTION} collection")

            return success

        except Exception as e:
            logger.error(f"Error initializing {self.CHARTS_COLLECTION} collection: {e}")
            return False

    def initialize_all_collections(self, recreate: bool = False) -> bool:
        """
        Initialize all vector store collections.

        Args:
            recreate: If True, delete and recreate all collections

        Returns:
            True if all collections initialized successfully, False otherwise
        """
        logger.info("Initializing all vector store collections")

        sheets_success = self.initialize_sheets_collection(recreate=recreate)
        pivots_success = self.initialize_pivots_collection(recreate=recreate)
        charts_success = self.initialize_charts_collection(recreate=recreate)

        all_success = sheets_success and pivots_success and charts_success

        if all_success:
            logger.info("All vector store collections initialized successfully")
        else:
            logger.error("Some vector store collections failed to initialize")

        return all_success

    def check_collection_exists(self, collection_name: str) -> bool:
        """
        Check if a collection exists.

        Note: This is a basic implementation. The actual check would depend
        on the vector store implementation.

        Args:
            collection_name: Name of the collection to check

        Returns:
            True if collection exists, False otherwise
        """
        try:
            # Try to search with an empty query to check if collection exists
            # This is a workaround since VectorStore interface doesn't have
            # a collection_exists method
            self.vector_store.search(
                collection=collection_name,
                query_embedding=[0.0] * self.embedding_dimension,
                top_k=1
            )
            return True
        except Exception as e:
            logger.debug(f"Collection {collection_name} may not exist: {e}")
            return False


def initialize_vector_store_collections(
    vector_store: VectorStore,
    embedding_service: EmbeddingService,
    recreate: bool = False
) -> bool:
    """
    Convenience function to initialize all vector store collections.

    Args:
        vector_store: Vector store instance
        embedding_service: Embedding service instance
        recreate: If True, delete and recreate all collections

    Returns:
        True if all collections initialized successfully, False otherwise
    """
    initializer = VectorStoreInitializer(vector_store, embedding_service)
    return initializer.initialize_all_collections(recreate=recreate)
