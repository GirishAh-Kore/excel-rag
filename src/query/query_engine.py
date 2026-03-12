"""
Query Engine Orchestrator

Main orchestrator for query processing pipeline. Coordinates all query
processing components to analyze queries, search for relevant data,
handle clarifications, and generate answers.
"""

import logging
import time
from typing import Optional, Dict, Any

from src.abstractions.llm_service import LLMService
from src.abstractions.embedding_service import EmbeddingService
from src.abstractions.cache_service import CacheService
from src.indexing.vector_storage import VectorStorageManager
from src.models.domain_models import QueryResult, ConversationContext
from src.query.query_analyzer import QueryAnalyzer, QueryAnalysis
from src.query.semantic_searcher import SemanticSearcher, SearchResults
from src.query.conversation_manager import ConversationManager
from src.query.clarification_generator import (
    ClarificationGenerator,
    ClarificationRequest
)
from src.utils.metrics import increment_counter, record_timer, timer
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class QueryEngine:
    """
    Main query processing engine that orchestrates the complete pipeline.
    
    Pipeline stages:
    1. Analyze query (extract entities, intent, temporal refs)
    2. Search for relevant data (semantic search)
    3. Check if clarification needed
    4. Select files and sheets (delegated to FileSelector/SheetSelector)
    5. Retrieve data (delegated to data retrieval components)
    6. Generate answer (delegated to AnswerGenerator)
    7. Handle comparisons (delegated to ComparisonEngine)
    
    Features:
    - Complete query processing pipeline
    - Conversation context management
    - Clarification handling
    - Comparison query routing
    - Error handling and logging
    """
    
    def __init__(
        self,
        llm_service: LLMService,
        embedding_service: EmbeddingService,
        cache_service: CacheService,
        vector_storage: VectorStorageManager,
        conversation_manager: ConversationManager
    ):
        """
        Initialize QueryEngine with all required services.
        
        Args:
            llm_service: LLM service for analysis and generation
            embedding_service: Embedding service for semantic search
            cache_service: Cache service for conversation context
            vector_storage: Vector storage manager for search
            conversation_manager: Injected conversation manager for session handling
        """
        self.llm_service = llm_service
        self.embedding_service = embedding_service
        self.cache_service = cache_service
        self.vector_storage = vector_storage
        
        # Initialize components
        self.query_analyzer = QueryAnalyzer(llm_service)
        self.semantic_searcher = SemanticSearcher(embedding_service, vector_storage)
        self.conversation_manager = conversation_manager  # Injected, not created
        self.clarification_generator = ClarificationGenerator(llm_service)
        
        logger.info("QueryEngine initialized with all components")
    
    def process_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        context: Optional[ConversationContext] = None
    ) -> QueryResult:
        """
        Process a user query through the complete pipeline.
        
        Args:
            query: Natural language query from user
            session_id: Optional session ID for conversation context
            context: Optional pre-loaded conversation context
            
        Returns:
            QueryResult with answer, sources, and confidence
        """
        start_time = time.time()
        logger.info(f"Processing query: {query}")
        
        # Track query metrics
        increment_counter('query.total_queries')
        
        try:
            # Create or get session
            if not session_id:
                session_id = self.conversation_manager.create_session()
                logger.info(f"Created new session: {session_id}")
                increment_counter('query.new_sessions')
            
            # Get conversation context
            if not context:
                context = self.conversation_manager.get_context(session_id)
            
            # Resolve ambiguous references using context
            if context:
                resolved_refs = self.conversation_manager.resolve_ambiguous_reference(
                    query, session_id
                )
                if resolved_refs:
                    logger.info(f"Resolved references: {resolved_refs}")
            
            # Stage 1: Analyze query
            with timer('query.analyze'):
                query_analysis = self.query_analyzer.analyze(query)
            
            logger.info(
                f"Query analysis: intent={query_analysis.intent}, "
                f"is_comparison={query_analysis.is_comparison}"
            )
            
            if query_analysis.is_comparison:
                increment_counter('query.comparison_queries')
            
            # Stage 2: Semantic search
            with timer('query.semantic_search'):
                if query_analysis.is_comparison:
                    search_results = self.semantic_searcher.search_for_comparison(
                        query=query,
                        query_analysis=query_analysis,
                        max_files=5
                    )
                else:
                    search_results = self.semantic_searcher.search(
                        query=query,
                        query_analysis=query_analysis,
                        top_k=10
                    )
            
            logger.info(f"Found {search_results.total_results} search results")
            
            # Stage 3: Check if clarification needed
            if self.clarification_generator.needs_clarification(
                search_results=search_results,
                confidence=query_analysis.confidence
            ):
                clarification = self.clarification_generator.generate_file_clarification(
                    query=query,
                    search_results=search_results,
                    max_options=3
                )
                
                # Update context
                self.conversation_manager.update_context(
                    session_id=session_id,
                    query=query
                )
                
                processing_time = int((time.time() - start_time) * 1000)
                
                # Track clarification metrics
                increment_counter('query.clarifications_needed')
                record_timer('query.response_time', processing_time)
                
                return QueryResult(
                    answer="",
                    confidence=query_analysis.confidence,
                    sources=[],
                    clarification_needed=True,
                    clarifying_questions=[clarification.question],
                    processing_time_ms=processing_time,
                    is_comparison=query_analysis.is_comparison
                )
            
            # Stage 4-7: File/sheet selection, data retrieval, answer generation
            # Note: These stages are placeholders for now as FileSelector,
            # SheetSelector, and AnswerGenerator are not yet implemented
            # (they are part of tasks 9, 10, and 11)
            
            # For now, return a basic response indicating the query was processed
            processing_time = int((time.time() - start_time) * 1000)
            
            # Update context with query
            self.conversation_manager.update_context(
                session_id=session_id,
                query=query
            )
            
            # Placeholder response
            answer = self._generate_placeholder_answer(
                query=query,
                query_analysis=query_analysis,
                search_results=search_results
            )
            
            # Track successful query metrics
            increment_counter('query.successful_queries')
            record_timer('query.response_time', processing_time)
            
            return QueryResult(
                answer=answer,
                confidence=query_analysis.confidence,
                sources=[],
                clarification_needed=False,
                clarifying_questions=[],
                processing_time_ms=processing_time,
                is_comparison=query_analysis.is_comparison,
                comparison_summary=None
            )
            
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            processing_time = int((time.time() - start_time) * 1000)
            
            # Track failed query metrics
            increment_counter('query.failed_queries')
            record_timer('query.response_time', processing_time)
            
            return QueryResult(
                answer=f"I encountered an error processing your query: {str(e)}",
                confidence=0.0,
                sources=[],
                clarification_needed=False,
                clarifying_questions=[],
                processing_time_ms=processing_time,
                is_comparison=False
            )
    
    def handle_clarification_response(
        self,
        session_id: str,
        clarification_request: ClarificationRequest,
        user_response: str
    ) -> Optional[QueryResult]:
        """
        Handle user's response to a clarification question.
        
        Args:
            session_id: Session identifier
            clarification_request: Original clarification request
            user_response: User's response
            
        Returns:
            QueryResult with updated processing or None if invalid response
        """
        logger.info(f"Handling clarification response: {user_response}")
        
        # Parse user response
        resolved = self.clarification_generator.handle_clarification_response(
            clarification_request=clarification_request,
            user_response=user_response
        )
        
        if not resolved:
            logger.warning("Invalid clarification response")
            return None
        
        # Update context with selection
        if resolved["type"] == "file_selection" and resolved["selection"]:
            self.conversation_manager.update_context(
                session_id=session_id,
                selected_file=resolved["selection"]
            )
        
        # Continue processing with the selected option
        # This would involve calling the appropriate next stage
        # For now, return a placeholder
        
        return QueryResult(
            answer=f"You selected: {resolved.get('label', 'unknown')}. "
                   f"Further processing would continue here.",
            confidence=0.8,
            sources=[],
            clarification_needed=False,
            clarifying_questions=[],
            processing_time_ms=0,
            is_comparison=False
        )
    
    def get_query_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> list[str]:
        """
        Get query history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of queries to return
            
        Returns:
            List of previous queries
        """
        context = self.conversation_manager.get_context(session_id)
        
        if not context:
            return []
        
        return context.previous_queries[-limit:]
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear conversation context for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful
        """
        return self.conversation_manager.clear_context(session_id)
    
    def _generate_placeholder_answer(
        self,
        query: str,
        query_analysis: QueryAnalysis,
        search_results: SearchResults
    ) -> str:
        """
        Generate a placeholder answer for demonstration.
        
        This will be replaced when AnswerGenerator is implemented.
        
        Args:
            query: Original query
            query_analysis: Analyzed query
            search_results: Search results
            
        Returns:
            Placeholder answer text
        """
        answer_parts = [
            f"Query processed successfully.",
            f"Intent: {query_analysis.intent}",
            f"Found {search_results.total_results} relevant results.",
        ]
        
        if search_results.results:
            top_result = search_results.results[0]
            answer_parts.append(
                f"Top match: {top_result.file_name} - {top_result.sheet_name} "
                f"(score: {top_result.score:.2f})"
            )
        
        if query_analysis.is_comparison:
            answer_parts.append("This appears to be a comparison query.")
        
        answer_parts.append(
            "\nNote: Full answer generation will be available when "
            "FileSelector, SheetSelector, and AnswerGenerator are implemented "
            "(tasks 9, 10, and 11)."
        )
        
        return "\n".join(answer_parts)
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session information or None
        """
        return self.conversation_manager.get_session_stats(session_id)
