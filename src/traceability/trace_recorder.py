"""
Trace Recorder

This module provides real-time recording of query processing decisions
for complete audit trails. It generates unique trace IDs and records
each step of the query pipeline with reasoning explanations.

Key Features:
- Generate unique trace_id for every query
- Record file selection, sheet selection, classification, and retrieval
- Include reasoning explanations for each decision
- Support export in JSON and CSV formats

Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6
"""

import csv
import io
import json
import logging
import time
import uuid
from dataclasses import asdict, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.exceptions import TraceError
from src.models.query_pipeline import (
    Citation,
    FileCandidate,
    QueryType,
    SheetCandidate,
)
from src.models.traceability import QueryTrace
from src.traceability.trace_storage import TraceStorage

logger = logging.getLogger(__name__)


class TraceRecorder:
    """
    Records query processing decisions in real-time for audit trails.
    
    Provides methods to start a trace, record each decision point in the
    query pipeline, and complete the trace with the final answer. Supports
    export of traces in JSON and CSV formats for compliance reporting.
    
    Attributes:
        storage: Injected TraceStorage for persisting traces.
        _active_traces: Dictionary of in-progress traces keyed by trace_id.
    
    Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6
    """
    
    def __init__(self, storage: TraceStorage) -> None:
        """
        Initialize the trace recorder.
        
        Args:
            storage: TraceStorage instance for persisting traces.
        
        Raises:
            TraceError: If storage is None.
        """
        if storage is None:
            raise TraceError(
                "TraceStorage is required",
                details={"parameter": "storage"}
            )
        
        self.storage = storage
        self._active_traces: Dict[str, Dict[str, Any]] = {}
        logger.info("TraceRecorder initialized")

    def start_trace(
        self,
        query: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Start a new trace for a query.
        
        Generates a unique trace_id and initializes the trace record
        with the query text and metadata.
        
        Args:
            query: The natural language query text.
            user_id: Optional user identifier for audit purposes.
            session_id: Optional session identifier for conversation context.
        
        Returns:
            The generated trace_id.
        
        Raises:
            TraceError: If trace initialization fails.
        
        Requirements: 16.1, 16.2
        """
        try:
            trace_id = f"tr_{uuid.uuid4().hex[:16]}"
            timestamp = datetime.now().isoformat()
            
            self._active_traces[trace_id] = {
                "trace_id": trace_id,
                "query_text": query,
                "timestamp": timestamp,
                "user_id": user_id,
                "session_id": session_id,
                "start_time": time.time(),
                "file_candidates": [],
                "file_selection_reasoning": "",
                "selected_file_id": "",
                "file_confidence": 0.0,
                "file_selection_time_ms": 0,
                "sheet_candidates": [],
                "sheet_selection_reasoning": "",
                "selected_sheets": [],
                "sheet_confidence": 0.0,
                "sheet_selection_time_ms": 0,
                "query_type": None,
                "classification_confidence": 0.0,
                "chunks_retrieved": [],
                "retrieval_scores": [],
                "retrieval_time_ms": 0,
                "answer_text": "",
                "citations": [],
                "answer_confidence": 0.0,
                "generation_time_ms": 0,
            }
            
            logger.debug(f"Started trace: {trace_id}")
            return trace_id
            
        except Exception as e:
            logger.error(f"Failed to start trace: {e}", exc_info=True)
            raise TraceError(
                f"Failed to start trace: {e}",
                details={"query": query[:100]}
            )

    def record_file_selection(
        self,
        trace_id: str,
        candidates: List[FileCandidate],
        selected_file_id: str,
        reasoning: str,
        confidence: float,
        time_ms: int = 0,
    ) -> None:
        """
        Record file selection decision in the trace.
        
        Args:
            trace_id: The trace identifier.
            candidates: List of file candidates that were evaluated.
            selected_file_id: ID of the file that was selected.
            reasoning: Explanation of why this file was selected.
            confidence: Confidence score for the selection (0.0 to 1.0).
            time_ms: Time taken for file selection in milliseconds.
        
        Raises:
            TraceError: If trace not found or recording fails.
        
        Requirements: 16.2, 16.4
        """
        try:
            if trace_id not in self._active_traces:
                raise TraceError(
                    f"Trace not found: {trace_id}",
                    details={"trace_id": trace_id}
                )
            
            trace = self._active_traces[trace_id]
            trace["file_candidates"] = candidates
            trace["selected_file_id"] = selected_file_id
            trace["file_selection_reasoning"] = reasoning
            trace["file_confidence"] = confidence
            trace["file_selection_time_ms"] = time_ms
            
            logger.debug(
                f"Recorded file selection for trace {trace_id}: "
                f"selected={selected_file_id}, confidence={confidence:.2f}"
            )
            
        except TraceError:
            raise
        except Exception as e:
            logger.error(f"Failed to record file selection: {e}", exc_info=True)
            raise TraceError(
                f"Failed to record file selection: {e}",
                details={"trace_id": trace_id}
            )

    def record_sheet_selection(
        self,
        trace_id: str,
        candidates: List[SheetCandidate],
        selected_sheets: List[str],
        reasoning: str,
        confidence: float,
        time_ms: int = 0,
    ) -> None:
        """
        Record sheet selection decision in the trace.
        
        Args:
            trace_id: The trace identifier.
            candidates: List of sheet candidates that were evaluated.
            selected_sheets: List of sheet names that were selected.
            reasoning: Explanation of why these sheets were selected.
            confidence: Confidence score for the selection (0.0 to 1.0).
            time_ms: Time taken for sheet selection in milliseconds.
        
        Raises:
            TraceError: If trace not found or recording fails.
        
        Requirements: 16.2, 16.4
        """
        try:
            if trace_id not in self._active_traces:
                raise TraceError(
                    f"Trace not found: {trace_id}",
                    details={"trace_id": trace_id}
                )
            
            trace = self._active_traces[trace_id]
            trace["sheet_candidates"] = candidates
            trace["selected_sheets"] = selected_sheets
            trace["sheet_selection_reasoning"] = reasoning
            trace["sheet_confidence"] = confidence
            trace["sheet_selection_time_ms"] = time_ms
            
            logger.debug(
                f"Recorded sheet selection for trace {trace_id}: "
                f"selected={selected_sheets}, confidence={confidence:.2f}"
            )
            
        except TraceError:
            raise
        except Exception as e:
            logger.error(f"Failed to record sheet selection: {e}", exc_info=True)
            raise TraceError(
                f"Failed to record sheet selection: {e}",
                details={"trace_id": trace_id}
            )

    def record_classification(
        self,
        trace_id: str,
        query_type: QueryType,
        confidence: float,
    ) -> None:
        """
        Record query classification in the trace.
        
        Args:
            trace_id: The trace identifier.
            query_type: The classified query type.
            confidence: Confidence score for the classification (0.0 to 1.0).
        
        Raises:
            TraceError: If trace not found or recording fails.
        
        Requirements: 16.2
        """
        try:
            if trace_id not in self._active_traces:
                raise TraceError(
                    f"Trace not found: {trace_id}",
                    details={"trace_id": trace_id}
                )
            
            trace = self._active_traces[trace_id]
            trace["query_type"] = query_type
            trace["classification_confidence"] = confidence
            
            logger.debug(
                f"Recorded classification for trace {trace_id}: "
                f"type={query_type.value}, confidence={confidence:.2f}"
            )
            
        except TraceError:
            raise
        except Exception as e:
            logger.error(f"Failed to record classification: {e}", exc_info=True)
            raise TraceError(
                f"Failed to record classification: {e}",
                details={"trace_id": trace_id}
            )

    def record_retrieval(
        self,
        trace_id: str,
        chunk_ids: List[str],
        scores: List[float],
        time_ms: int = 0,
    ) -> None:
        """
        Record chunk retrieval in the trace.
        
        Args:
            trace_id: The trace identifier.
            chunk_ids: List of retrieved chunk IDs.
            scores: Similarity scores for each retrieved chunk.
            time_ms: Time taken for retrieval in milliseconds.
        
        Raises:
            TraceError: If trace not found or recording fails.
        
        Requirements: 16.2
        """
        try:
            if trace_id not in self._active_traces:
                raise TraceError(
                    f"Trace not found: {trace_id}",
                    details={"trace_id": trace_id}
                )
            
            trace = self._active_traces[trace_id]
            trace["chunks_retrieved"] = chunk_ids
            trace["retrieval_scores"] = scores
            trace["retrieval_time_ms"] = time_ms
            
            logger.debug(
                f"Recorded retrieval for trace {trace_id}: "
                f"{len(chunk_ids)} chunks retrieved"
            )
            
        except TraceError:
            raise
        except Exception as e:
            logger.error(f"Failed to record retrieval: {e}", exc_info=True)
            raise TraceError(
                f"Failed to record retrieval: {e}",
                details={"trace_id": trace_id}
            )

    def complete_trace(
        self,
        trace_id: str,
        answer: str,
        citations: List[Citation],
        confidence: float,
        generation_time_ms: int = 0,
    ) -> QueryTrace:
        """
        Complete and persist the trace with the final answer.
        
        Calculates total processing time and persists the complete trace
        to storage. Removes the trace from active traces after completion.
        
        Args:
            trace_id: The trace identifier.
            answer: The generated answer text.
            citations: Source citations for the answer.
            confidence: Overall confidence score for the answer (0.0 to 1.0).
            generation_time_ms: Time taken for answer generation in milliseconds.
        
        Returns:
            The completed QueryTrace object.
        
        Raises:
            TraceError: If trace not found or completion fails.
        
        Requirements: 16.2
        """
        try:
            if trace_id not in self._active_traces:
                raise TraceError(
                    f"Trace not found: {trace_id}",
                    details={"trace_id": trace_id}
                )
            
            trace_data = self._active_traces[trace_id]
            
            # Calculate total processing time
            total_time_ms = int((time.time() - trace_data["start_time"]) * 1000)
            
            # Build QueryTrace object
            query_trace = QueryTrace(
                trace_id=trace_data["trace_id"],
                query_text=trace_data["query_text"],
                timestamp=trace_data["timestamp"],
                user_id=trace_data["user_id"],
                session_id=trace_data["session_id"],
                file_candidates=trace_data["file_candidates"],
                file_selection_reasoning=trace_data["file_selection_reasoning"],
                selected_file_id=trace_data["selected_file_id"],
                file_confidence=trace_data["file_confidence"],
                sheet_candidates=trace_data["sheet_candidates"],
                sheet_selection_reasoning=trace_data["sheet_selection_reasoning"],
                selected_sheets=trace_data["selected_sheets"],
                sheet_confidence=trace_data["sheet_confidence"],
                query_type=trace_data["query_type"],
                classification_confidence=trace_data["classification_confidence"],
                chunks_retrieved=trace_data["chunks_retrieved"],
                retrieval_scores=trace_data["retrieval_scores"],
                answer_text=answer,
                citations=citations,
                answer_confidence=confidence,
                total_processing_time_ms=total_time_ms,
                file_selection_time_ms=trace_data["file_selection_time_ms"],
                sheet_selection_time_ms=trace_data["sheet_selection_time_ms"],
                retrieval_time_ms=trace_data["retrieval_time_ms"],
                generation_time_ms=generation_time_ms,
            )
            
            # Persist to storage
            self.storage.create_trace(query_trace)
            
            # Remove from active traces
            del self._active_traces[trace_id]
            
            logger.debug(
                f"Completed trace {trace_id}: "
                f"total_time={total_time_ms}ms, confidence={confidence:.2f}"
            )
            
            return query_trace
            
        except TraceError:
            raise
        except Exception as e:
            logger.error(f"Failed to complete trace: {e}", exc_info=True)
            raise TraceError(
                f"Failed to complete trace: {e}",
                details={"trace_id": trace_id}
            )

    def abort_trace(self, trace_id: str) -> None:
        """
        Abort an in-progress trace without persisting.
        
        Use this when query processing fails and the trace should be discarded.
        
        Args:
            trace_id: The trace identifier.
        """
        if trace_id in self._active_traces:
            del self._active_traces[trace_id]
            logger.debug(f"Aborted trace: {trace_id}")

    def get_trace(self, trace_id: str) -> Optional[QueryTrace]:
        """
        Retrieve a completed trace by ID.
        
        Args:
            trace_id: The trace identifier.
        
        Returns:
            QueryTrace object or None if not found.
        
        Raises:
            TraceError: If retrieval fails.
        
        Requirements: 16.3
        """
        return self.storage.get_trace(trace_id)

    def export_traces(
        self,
        trace_ids: List[str],
        format: str = "json",
    ) -> bytes:
        """
        Export traces in JSON or CSV format.
        
        Args:
            trace_ids: List of trace IDs to export.
            format: Export format ("json" or "csv").
        
        Returns:
            Exported data as bytes.
        
        Raises:
            TraceError: If export fails or format is invalid.
        
        Requirements: 16.6
        """
        try:
            if format not in ("json", "csv"):
                raise TraceError(
                    f"Invalid export format: {format}",
                    details={"format": format, "valid_formats": ["json", "csv"]}
                )
            
            # Retrieve all traces
            traces: List[QueryTrace] = []
            for trace_id in trace_ids:
                trace = self.storage.get_trace(trace_id)
                if trace:
                    traces.append(trace)
            
            if format == "json":
                return self._export_json(traces)
            else:
                return self._export_csv(traces)
                
        except TraceError:
            raise
        except Exception as e:
            logger.error(f"Failed to export traces: {e}", exc_info=True)
            raise TraceError(
                f"Failed to export traces: {e}",
                details={"trace_count": len(trace_ids), "format": format}
            )

    def _export_json(self, traces: List[QueryTrace]) -> bytes:
        """Export traces to JSON format."""
        data = []
        for trace in traces:
            trace_dict = {
                "trace_id": trace.trace_id,
                "query_text": trace.query_text,
                "timestamp": trace.timestamp,
                "user_id": trace.user_id,
                "session_id": trace.session_id,
                "file_selection": {
                    "selected_file_id": trace.selected_file_id,
                    "reasoning": trace.file_selection_reasoning,
                    "confidence": trace.file_confidence,
                    "candidates_count": len(trace.file_candidates),
                },
                "sheet_selection": {
                    "selected_sheets": trace.selected_sheets,
                    "reasoning": trace.sheet_selection_reasoning,
                    "confidence": trace.sheet_confidence,
                    "candidates_count": len(trace.sheet_candidates),
                },
                "classification": {
                    "query_type": trace.query_type.value if trace.query_type else None,
                    "confidence": trace.classification_confidence,
                },
                "retrieval": {
                    "chunks_count": len(trace.chunks_retrieved),
                    "chunk_ids": trace.chunks_retrieved,
                },
                "answer": {
                    "text": trace.answer_text,
                    "confidence": trace.answer_confidence,
                    "citations_count": len(trace.citations),
                },
                "performance": {
                    "total_time_ms": trace.total_processing_time_ms,
                    "file_selection_time_ms": trace.file_selection_time_ms,
                    "sheet_selection_time_ms": trace.sheet_selection_time_ms,
                    "retrieval_time_ms": trace.retrieval_time_ms,
                    "generation_time_ms": trace.generation_time_ms,
                },
            }
            data.append(trace_dict)
        
        return json.dumps(data, indent=2).encode("utf-8")

    def _export_csv(self, traces: List[QueryTrace]) -> bytes:
        """Export traces to CSV format."""
        output = io.StringIO()
        
        fieldnames = [
            "trace_id", "query_text", "timestamp", "user_id", "session_id",
            "selected_file_id", "file_confidence", "file_selection_reasoning",
            "selected_sheets", "sheet_confidence", "sheet_selection_reasoning",
            "query_type", "classification_confidence",
            "chunks_retrieved_count", "answer_confidence",
            "total_time_ms", "file_selection_time_ms", "sheet_selection_time_ms",
            "retrieval_time_ms", "generation_time_ms",
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for trace in traces:
            row = {
                "trace_id": trace.trace_id,
                "query_text": trace.query_text,
                "timestamp": trace.timestamp,
                "user_id": trace.user_id or "",
                "session_id": trace.session_id or "",
                "selected_file_id": trace.selected_file_id,
                "file_confidence": trace.file_confidence,
                "file_selection_reasoning": trace.file_selection_reasoning,
                "selected_sheets": ";".join(trace.selected_sheets),
                "sheet_confidence": trace.sheet_confidence,
                "sheet_selection_reasoning": trace.sheet_selection_reasoning,
                "query_type": trace.query_type.value if trace.query_type else "",
                "classification_confidence": trace.classification_confidence,
                "chunks_retrieved_count": len(trace.chunks_retrieved),
                "answer_confidence": trace.answer_confidence,
                "total_time_ms": trace.total_processing_time_ms,
                "file_selection_time_ms": trace.file_selection_time_ms,
                "sheet_selection_time_ms": trace.sheet_selection_time_ms,
                "retrieval_time_ms": trace.retrieval_time_ms,
                "generation_time_ms": trace.generation_time_ms,
            }
            writer.writerow(row)
        
        return output.getvalue().encode("utf-8")

    def get_active_trace_count(self) -> int:
        """
        Get the count of currently active (in-progress) traces.
        
        Returns:
            Number of active traces.
        """
        return len(self._active_traces)

    def get_active_trace_ids(self) -> List[str]:
        """
        Get the IDs of all currently active traces.
        
        Returns:
            List of active trace IDs.
        """
        return list(self._active_traces.keys())

    def is_trace_active(self, trace_id: str) -> bool:
        """
        Check if a trace is currently active (in-progress).
        
        Args:
            trace_id: The trace identifier.
        
        Returns:
            True if trace is active, False otherwise.
        """
        return trace_id in self._active_traces
