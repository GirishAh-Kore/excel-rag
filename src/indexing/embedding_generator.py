"""
Embedding Generator

This module handles the generation of embeddings for Excel content using the
EmbeddingService abstraction. It supports batching, caching, error handling,
and cost tracking for API-based embedding services.
"""

import logging
import hashlib
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from src.abstractions.embedding_service import EmbeddingService
from src.abstractions.cache_service import CacheService
from src.models.domain_models import SheetData, PivotTableData, ChartData, WorkbookData
from src.indexing.excel_chunker import ExcelChunker


logger = logging.getLogger(__name__)


@dataclass
class EmbeddingCost:
    """Tracks embedding generation costs"""
    total_tokens: int = 0
    total_requests: int = 0
    total_embeddings: int = 0
    estimated_cost_usd: float = 0.0
    provider: str = ""
    model: str = ""
    
    def add_batch(self, num_texts: int, num_tokens: int, cost_per_token: float = 0.0):
        """Add a batch of embeddings to cost tracking"""
        self.total_requests += 1
        self.total_embeddings += num_texts
        self.total_tokens += num_tokens
        self.estimated_cost_usd += num_tokens * cost_per_token


@dataclass
class EmbeddingResult:
    """Result of embedding generation"""
    embeddings: List[List[float]]
    texts: List[str]
    ids: List[str]
    metadata: List[Dict[str, Any]]
    from_cache: List[bool]
    cost: EmbeddingCost


class EmbeddingGenerator:
    """
    Generates embeddings for Excel content with batching, caching, and error handling.
    
    Features:
    - Batch processing (configurable batch size, default 100)
    - Caching to avoid regenerating embeddings for unchanged content
    - Retry logic for API errors and rate limits
    - Cost tracking for API-based services
    - Support for multiple embedding providers via abstraction
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        cache_service: Optional[CacheService] = None,
        batch_size: int = 100,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        cost_per_token: float = 0.0,
        chunk_size: int = 50,
        chunk_overlap: int = 5
    ):
        """
        Initialize the embedding generator.

        Args:
            embedding_service: Service for generating embeddings
            cache_service: Optional cache service for storing embeddings
            batch_size: Number of texts to embed in a single batch (default: 100)
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Initial delay between retries in seconds (exponential backoff)
            cost_per_token: Cost per token for API-based services (USD)
            chunk_size: Rows per sliding-window chunk (default: 50)
            chunk_overlap: Overlapping rows between chunks (default: 5)
        """
        self.embedding_service = embedding_service
        self.cache_service = cache_service
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.cost_per_token = cost_per_token
        self.chunker = ExcelChunker(chunk_size=chunk_size, overlap=chunk_overlap)

        # Cost tracking
        self.cost = EmbeddingCost(
            provider=embedding_service.__class__.__name__,
            model=embedding_service.get_model_name()
        )

        logger.info(
            f"EmbeddingGenerator initialized: "
            f"provider={self.cost.provider}, "
            f"model={self.cost.model}, "
            f"batch_size={batch_size}, "
            f"chunk_size={chunk_size}, overlap={chunk_overlap}"
        )
    
    def generate_workbook_embeddings(self, workbook_data: WorkbookData) -> EmbeddingResult:
        """
        Generate embeddings for all content in a workbook.
        
        Args:
            workbook_data: Workbook data to generate embeddings for
            
        Returns:
            EmbeddingResult with embeddings, texts, IDs, and metadata
        """
        logger.info(f"Generating embeddings for workbook: {workbook_data.file_name}")
        
        all_texts = []
        all_ids = []
        all_metadata = []
        
        # Generate embeddings for each sheet
        for sheet in workbook_data.sheets:
            texts, ids, metadata = self._generate_sheet_texts(
                sheet=sheet,
                file_id=workbook_data.file_id,
                file_name=workbook_data.file_name,
                file_path=workbook_data.file_path
            )
            all_texts.extend(texts)
            all_ids.extend(ids)
            all_metadata.extend(metadata)
        
        # Generate embeddings in batches
        embeddings, from_cache = self._generate_embeddings_batched(all_texts, all_ids)
        
        logger.info(
            f"Generated {len(embeddings)} embeddings for {workbook_data.file_name} "
            f"({sum(from_cache)} from cache)"
        )
        
        return EmbeddingResult(
            embeddings=embeddings,
            texts=all_texts,
            ids=all_ids,
            metadata=all_metadata,
            from_cache=from_cache,
            cost=self.cost
        )
    
    def _generate_sheet_texts(
        self,
        sheet: SheetData,
        file_id: str,
        file_name: str,
        file_path: str
    ) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
        """
        Generate embedding texts for a single sheet.
        
        Creates multiple text chunks per sheet:
        1. Sheet overview (name + headers + summary)
        2. Column-wise summaries for numerical data
        3. Pivot table descriptions
        4. Chart descriptions
        
        Args:
            sheet: Sheet data
            file_id: File ID
            file_name: File name
            file_path: File path
            
        Returns:
            Tuple of (texts, ids, metadata)
        """
        texts = []
        ids = []
        metadata = []
        
        # 1. Sheet overview embedding (uses sliding-window chunks for full coverage)
        sheet_chunks = self.chunker.chunk_sheet(sheet, file_name)

        if sheet_chunks:
            for chunk in sheet_chunks:
                chunk_id = f"{file_id}:{sheet.sheet_name}:chunk:{chunk['chunk_index']}"
                chunk_metadata = {
                    "file_id": file_id,
                    "file_name": file_name,
                    "file_path": file_path,
                    "sheet_name": sheet.sheet_name,
                    "content_type": "sheet_overview",
                    "row_count": sheet.row_count,
                    "column_count": sheet.column_count,
                    "has_dates": sheet.has_dates,
                    "has_numbers": sheet.has_numbers,
                    "has_pivot_tables": sheet.has_pivot_tables,
                    "has_charts": sheet.has_charts,
                    "chunk_start_row": chunk["start_row"],
                    "chunk_end_row": chunk["end_row"]
                }
                texts.append(chunk["text"])
                ids.append(chunk_id)
                metadata.append(chunk_metadata)
        else:
            # Fallback: overview text when no rows available
            overview_text = self._create_sheet_overview_text(sheet, file_name)
            overview_id = f"{file_id}:{sheet.sheet_name}:overview"
            overview_metadata = {
                "file_id": file_id,
                "file_name": file_name,
                "file_path": file_path,
                "sheet_name": sheet.sheet_name,
                "content_type": "sheet_overview",
                "row_count": sheet.row_count,
                "column_count": sheet.column_count,
                "has_dates": sheet.has_dates,
                "has_numbers": sheet.has_numbers,
                "has_pivot_tables": sheet.has_pivot_tables,
                "has_charts": sheet.has_charts
            }
            texts.append(overview_text)
            ids.append(overview_id)
            metadata.append(overview_metadata)
        
        # 2. Column summaries for numerical data
        if sheet.has_numbers and sheet.rows:
            column_texts, column_ids, column_metadata = self._create_column_summaries(
                sheet=sheet,
                file_id=file_id,
                file_name=file_name,
                file_path=file_path
            )
            texts.extend(column_texts)
            ids.extend(column_ids)
            metadata.extend(column_metadata)
        
        # 3. Pivot table embeddings
        for i, pivot in enumerate(sheet.pivot_tables):
            pivot_text = self._create_pivot_text(pivot, file_name, sheet.sheet_name)
            pivot_id = f"{file_id}:{sheet.sheet_name}:pivot:{i}"
            pivot_metadata = {
                "file_id": file_id,
                "file_name": file_name,
                "file_path": file_path,
                "sheet_name": sheet.sheet_name,
                "content_type": "pivot_table",
                "pivot_name": pivot.name,
                "row_fields": ",".join(pivot.row_fields),
                "data_fields": ",".join(pivot.data_fields)
            }
            
            texts.append(pivot_text)
            ids.append(pivot_id)
            metadata.append(pivot_metadata)
        
        # 4. Chart embeddings
        for i, chart in enumerate(sheet.charts):
            chart_text = self._create_chart_text(chart, file_name, sheet.sheet_name)
            chart_id = f"{file_id}:{sheet.sheet_name}:chart:{i}"
            chart_metadata = {
                "file_id": file_id,
                "file_name": file_name,
                "file_path": file_path,
                "sheet_name": sheet.sheet_name,
                "content_type": "chart",
                "chart_name": chart.name,
                "chart_type": chart.chart_type,
                "chart_title": chart.title or ""
            }
            
            texts.append(chart_text)
            ids.append(chart_id)
            metadata.append(chart_metadata)
        
        return texts, ids, metadata
    
    def _create_sheet_overview_text(self, sheet: SheetData, file_name: str) -> str:
        """Create overview text for sheet embedding"""
        parts = [
            f"File: {file_name}",
            f"Sheet: {sheet.sheet_name}",
            f"Description: {sheet.summary}"
        ]
        
        if sheet.headers:
            parts.append(f"Columns: {', '.join(sheet.headers)}")
        
        # Add sample data (first 5 rows)
        if sheet.rows:
            sample_rows = sheet.rows[:5]
            parts.append("Sample data:")
            for row in sample_rows:
                row_str = ", ".join(f"{k}: {v}" for k, v in row.items() if v is not None)
                parts.append(f"  {row_str}")
        
        # Add LLM summary if available
        if sheet.llm_summary:
            parts.append(f"Purpose: {sheet.llm_summary}")
        
        return "\n".join(parts)
    
    def _create_column_summaries(
        self,
        sheet: SheetData,
        file_id: str,
        file_name: str,
        file_path: str
    ) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
        """Create column-wise summaries for numerical data"""
        texts = []
        ids = []
        metadata = []
        
        # Find numerical columns
        numerical_columns = [
            col for col, dtype in sheet.data_types.items()
            if dtype.value == "number"
        ]
        
        for col in numerical_columns[:10]:  # Limit to 10 columns
            # Calculate basic statistics
            values = [row.get(col) for row in sheet.rows if row.get(col) is not None]
            if not values:
                continue
            
            try:
                min_val = min(values)
                max_val = max(values)
                avg_val = sum(values) / len(values)
                
                text = (
                    f"File: {file_name}, Sheet: {sheet.sheet_name}\n"
                    f"Column: {col}\n"
                    f"Statistics: min={min_val:.2f}, max={max_val:.2f}, avg={avg_val:.2f}\n"
                    f"Sample values: {', '.join(str(v) for v in values[:5])}"
                )
                
                col_id = f"{file_id}:{sheet.sheet_name}:column:{col}"
                col_metadata = {
                    "file_id": file_id,
                    "file_name": file_name,
                    "file_path": file_path,
                    "sheet_name": sheet.sheet_name,
                    "content_type": "column_summary",
                    "column_name": col,
                    "data_type": "number",
                    "min_value": min_val,
                    "max_value": max_val,
                    "avg_value": avg_val
                }
                
                texts.append(text)
                ids.append(col_id)
                metadata.append(col_metadata)
                
            except (TypeError, ValueError) as e:
                logger.warning(f"Error calculating statistics for column {col}: {e}")
                continue
        
        return texts, ids, metadata
    
    def _create_pivot_text(self, pivot: PivotTableData, file_name: str, sheet_name: str) -> str:
        """Create text description for pivot table"""
        parts = [
            f"File: {file_name}",
            f"Sheet: {sheet_name}",
            f"Pivot Table: {pivot.name}",
            f"Description: {pivot.summary}"
        ]
        
        if pivot.row_fields:
            parts.append(f"Grouped by: {', '.join(pivot.row_fields)}")
        
        if pivot.data_fields:
            parts.append(f"Aggregations: {', '.join(pivot.data_fields)}")
        
        if pivot.filters:
            filter_str = ", ".join(f"{k}={v}" for k, v in pivot.filters.items())
            parts.append(f"Filters: {filter_str}")
        
        return "\n".join(parts)
    
    def _create_chart_text(self, chart: ChartData, file_name: str, sheet_name: str) -> str:
        """Create text description for chart"""
        parts = [
            f"File: {file_name}",
            f"Sheet: {sheet_name}",
            f"Chart: {chart.name}",
            f"Type: {chart.chart_type}",
            f"Description: {chart.summary}"
        ]
        
        if chart.title:
            parts.append(f"Title: {chart.title}")
        
        if chart.x_axis_label:
            parts.append(f"X-axis: {chart.x_axis_label}")
        
        if chart.y_axis_label:
            parts.append(f"Y-axis: {chart.y_axis_label}")
        
        return "\n".join(parts)
    
    def _generate_embeddings_batched(
        self,
        texts: List[str],
        ids: List[str]
    ) -> Tuple[List[List[float]], List[bool]]:
        """
        Generate embeddings in batches with caching and retry logic.
        
        Args:
            texts: List of texts to embed
            ids: List of IDs for caching
            
        Returns:
            Tuple of (embeddings, from_cache flags)
        """
        all_embeddings = []
        all_from_cache = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            batch_ids = ids[i:i + self.batch_size]
            
            # Check cache for each text
            batch_embeddings = []
            batch_from_cache = []
            texts_to_embed = []
            indices_to_embed = []
            
            for j, (text, text_id) in enumerate(zip(batch_texts, batch_ids)):
                cached_embedding = self._get_cached_embedding(text_id, text)
                if cached_embedding is not None:
                    batch_embeddings.append(cached_embedding)
                    batch_from_cache.append(True)
                else:
                    batch_embeddings.append(None)  # Placeholder
                    batch_from_cache.append(False)
                    texts_to_embed.append(text)
                    indices_to_embed.append(j)
            
            # Generate embeddings for uncached texts
            if texts_to_embed:
                new_embeddings = self._generate_with_retry(texts_to_embed)
                
                # Insert new embeddings into batch
                for idx, embedding in zip(indices_to_embed, new_embeddings):
                    batch_embeddings[idx] = embedding
                    # Cache the new embedding
                    self._cache_embedding(batch_ids[idx], batch_texts[idx], embedding)
                
                # Track cost
                num_tokens = sum(len(text.split()) for text in texts_to_embed)
                self.cost.add_batch(len(texts_to_embed), num_tokens, self.cost_per_token)
            
            all_embeddings.extend(batch_embeddings)
            all_from_cache.extend(batch_from_cache)
            
            logger.debug(
                f"Processed batch {i // self.batch_size + 1}: "
                f"{len(texts_to_embed)} new, {len(batch_texts) - len(texts_to_embed)} cached"
            )
        
        return all_embeddings, all_from_cache
    
    def _generate_with_retry(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings with retry logic for API errors.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings
        """
        for attempt in range(self.max_retries):
            try:
                embeddings = self.embedding_service.embed_batch(texts)
                return embeddings
                
            except Exception as e:
                logger.warning(
                    f"Embedding generation failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(f"Failed to generate embeddings after {self.max_retries} attempts")
                    raise
    
    def _get_cached_embedding(self, text_id: str, text: str) -> Optional[List[float]]:
        """
        Get cached embedding if available.
        
        Args:
            text_id: Unique ID for the text
            text: The text content (for hash verification)
            
        Returns:
            Cached embedding or None
        """
        if not self.cache_service:
            return None
        
        try:
            # Create cache key from ID and text hash
            text_hash = hashlib.md5(text.encode()).hexdigest()
            cache_key = f"embedding:{text_id}:{text_hash}"
            
            cached = self.cache_service.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for {text_id}")
                return cached
            
        except Exception as e:
            logger.warning(f"Error retrieving cached embedding: {e}")
        
        return None
    
    def _cache_embedding(self, text_id: str, text: str, embedding: List[float]):
        """
        Cache an embedding.
        
        Args:
            text_id: Unique ID for the text
            text: The text content
            embedding: The embedding to cache
        """
        if not self.cache_service:
            return
        
        try:
            # Create cache key from ID and text hash
            text_hash = hashlib.md5(text.encode()).hexdigest()
            cache_key = f"embedding:{text_id}:{text_hash}"
            
            # Cache for 30 days
            ttl = 30 * 24 * 60 * 60
            self.cache_service.set(cache_key, embedding, ttl=ttl)
            
        except Exception as e:
            logger.warning(f"Error caching embedding: {e}")
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """
        Get summary of embedding generation costs.
        
        Returns:
            Dictionary with cost information
        """
        return {
            "provider": self.cost.provider,
            "model": self.cost.model,
            "total_embeddings": self.cost.total_embeddings,
            "total_tokens": self.cost.total_tokens,
            "total_requests": self.cost.total_requests,
            "estimated_cost_usd": round(self.cost.estimated_cost_usd, 4)
        }
