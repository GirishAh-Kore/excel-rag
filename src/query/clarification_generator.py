"""
Clarification Question Generator

Generates clarifying questions when queries are ambiguous or when
multiple candidates have similar relevance scores.
"""

import logging
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field

from src.abstractions.llm_service import LLMService
from src.query.semantic_searcher import SearchResults

logger = logging.getLogger(__name__)


class ClarificationOption(BaseModel):
    """A single clarification option to present to the user."""
    
    id: str = Field(..., description="Unique identifier for this option")
    label: str = Field(..., description="Display label for the option")
    description: Optional[str] = Field(
        default=None,
        description="Additional description or context"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about this option"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "file123",
                "label": "Expenses_Jan2024.xlsx",
                "description": "Monthly expense report for January 2024",
                "metadata": {"file_path": "/Finance/2024/", "modified": "2024-01-15"}
            }
        }


class ClarificationRequest(BaseModel):
    """Request for user clarification."""
    
    question: str = Field(..., description="Clarifying question to ask the user")
    options: List[ClarificationOption] = Field(
        default_factory=list,
        description="Options to present to the user"
    )
    clarification_type: str = Field(
        ...,
        description="Type of clarification (file_selection, sheet_selection, intent_clarification)"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence that clarification is needed"
    )
    allow_none: bool = Field(
        default=True,
        description="Whether 'none of these' is a valid option"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Which file would you like to query?",
                "options": [],
                "clarification_type": "file_selection",
                "confidence": 0.85,
                "allow_none": True
            }
        }


class ClarificationGenerator:
    """
    Generates clarifying questions for ambiguous queries.
    
    Features:
    - Detects ambiguous queries (low confidence, similar scores)
    - Generates natural language clarifying questions
    - Presents top candidates as options
    - Handles different clarification types (file, sheet, intent)
    """
    
    # Confidence threshold for requiring clarification
    CLARIFICATION_THRESHOLD = 0.70
    
    # Score difference threshold (if top results are too similar)
    SCORE_SIMILARITY_THRESHOLD = 0.05
    
    def __init__(self, llm_service: LLMService):
        """
        Initialize ClarificationGenerator.
        
        Args:
            llm_service: LLM service for generating questions
        """
        self.llm_service = llm_service
        logger.info(f"ClarificationGenerator initialized with LLM: {llm_service.get_model_name()}")
    
    def needs_clarification(
        self,
        search_results: SearchResults,
        confidence: float
    ) -> bool:
        """
        Determine if clarification is needed.
        
        Args:
            search_results: Search results from semantic search
            confidence: Overall confidence score
            
        Returns:
            True if clarification is needed
        """
        # Check if confidence is below threshold
        if confidence < self.CLARIFICATION_THRESHOLD:
            logger.info(f"Clarification needed: low confidence ({confidence:.2f})")
            return True
        
        # Check if top results have similar scores
        if len(search_results.results) >= 2:
            top_score = search_results.results[0].score
            second_score = search_results.results[1].score
            
            if abs(top_score - second_score) < self.SCORE_SIMILARITY_THRESHOLD:
                logger.info(
                    f"Clarification needed: similar scores "
                    f"({top_score:.2f} vs {second_score:.2f})"
                )
                return True
        
        return False
    
    def generate_file_clarification(
        self,
        query: str,
        search_results: SearchResults,
        max_options: int = 3
    ) -> ClarificationRequest:
        """
        Generate clarification for file selection.
        
        Args:
            query: Original user query
            search_results: Search results with multiple file candidates
            max_options: Maximum number of options to present
            
        Returns:
            ClarificationRequest with file options
        """
        logger.info("Generating file clarification")
        
        # Get unique files from search results
        file_map = {}
        for result in search_results.results:
            if result.file_id not in file_map:
                file_map[result.file_id] = {
                    "file_name": result.file_name,
                    "file_path": result.file_path,
                    "score": result.score,
                    "metadata": result.metadata
                }
            else:
                # Keep highest score for this file
                if result.score > file_map[result.file_id]["score"]:
                    file_map[result.file_id]["score"] = result.score
        
        # Sort by score and take top options
        sorted_files = sorted(
            file_map.items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )[:max_options]
        
        # Create options
        options = []
        for file_id, file_info in sorted_files:
            options.append(ClarificationOption(
                id=file_id,
                label=file_info["file_name"],
                description=f"Path: {file_info['file_path']} (Score: {file_info['score']:.2f})",
                metadata=file_info["metadata"]
            ))
        
        # Generate question using LLM
        question = self._generate_question_with_llm(
            query=query,
            clarification_type="file_selection",
            options=options
        )
        
        return ClarificationRequest(
            question=question,
            options=options,
            clarification_type="file_selection",
            confidence=0.85,
            allow_none=True
        )
    
    def generate_sheet_clarification(
        self,
        query: str,
        file_name: str,
        sheet_names: List[str],
        max_options: int = 3
    ) -> ClarificationRequest:
        """
        Generate clarification for sheet selection.
        
        Args:
            query: Original user query
            file_name: Name of the file
            sheet_names: List of sheet names to choose from
            max_options: Maximum number of options to present
            
        Returns:
            ClarificationRequest with sheet options
        """
        logger.info(f"Generating sheet clarification for file: {file_name}")
        
        # Create options from sheet names
        options = []
        for i, sheet_name in enumerate(sheet_names[:max_options]):
            options.append(ClarificationOption(
                id=f"sheet_{i}",
                label=sheet_name,
                description=f"Sheet in {file_name}",
                metadata={"sheet_name": sheet_name, "file_name": file_name}
            ))
        
        # Generate question
        question = self._generate_question_with_llm(
            query=query,
            clarification_type="sheet_selection",
            options=options
        )
        
        return ClarificationRequest(
            question=question,
            options=options,
            clarification_type="sheet_selection",
            confidence=0.80,
            allow_none=False  # Must select a sheet
        )
    
    def generate_intent_clarification(
        self,
        query: str,
        possible_intents: List[Dict[str, str]]
    ) -> ClarificationRequest:
        """
        Generate clarification for query intent.
        
        Args:
            query: Original user query
            possible_intents: List of possible intents with descriptions
            
        Returns:
            ClarificationRequest with intent options
        """
        logger.info("Generating intent clarification")
        
        # Create options from intents
        options = []
        for i, intent_info in enumerate(possible_intents):
            options.append(ClarificationOption(
                id=intent_info.get("id", f"intent_{i}"),
                label=intent_info.get("label", ""),
                description=intent_info.get("description", ""),
                metadata={"intent": intent_info.get("intent", "")}
            ))
        
        # Generate question
        question = self._generate_question_with_llm(
            query=query,
            clarification_type="intent_clarification",
            options=options
        )
        
        return ClarificationRequest(
            question=question,
            options=options,
            clarification_type="intent_clarification",
            confidence=0.75,
            allow_none=False
        )
    
    def handle_clarification_response(
        self,
        clarification_request: ClarificationRequest,
        user_response: str
    ) -> Optional[Dict[str, Any]]:
        """
        Handle user's response to clarification.
        
        Args:
            clarification_request: Original clarification request
            user_response: User's response (option ID or text)
            
        Returns:
            Dictionary with resolved information or None if invalid
        """
        logger.info(f"Handling clarification response: {user_response}")
        
        # Check if user selected "none"
        if user_response.lower() in ["none", "none of these", "neither", "cancel"]:
            if clarification_request.allow_none:
                return {"selection": None, "type": "none"}
            else:
                logger.warning("User selected 'none' but it's not allowed")
                return None
        
        # Try to find matching option by ID
        for option in clarification_request.options:
            if option.id == user_response:
                return {
                    "selection": option.id,
                    "type": clarification_request.clarification_type,
                    "label": option.label,
                    "metadata": option.metadata
                }
        
        # Try to find matching option by label (case-insensitive)
        user_response_lower = user_response.lower()
        for option in clarification_request.options:
            if option.label.lower() == user_response_lower:
                return {
                    "selection": option.id,
                    "type": clarification_request.clarification_type,
                    "label": option.label,
                    "metadata": option.metadata
                }
        
        # Try to parse as number (1-indexed)
        try:
            index = int(user_response) - 1
            if 0 <= index < len(clarification_request.options):
                option = clarification_request.options[index]
                return {
                    "selection": option.id,
                    "type": clarification_request.clarification_type,
                    "label": option.label,
                    "metadata": option.metadata
                }
        except ValueError:
            pass
        
        logger.warning(f"Could not match user response: {user_response}")
        return None
    
    def _generate_question_with_llm(
        self,
        query: str,
        clarification_type: str,
        options: List[ClarificationOption]
    ) -> str:
        """
        Generate a natural language clarifying question using LLM.
        
        Args:
            query: Original user query
            clarification_type: Type of clarification
            options: Available options
            
        Returns:
            Generated question text
        """
        # Create fallback questions
        fallback_questions = {
            "file_selection": "Which file would you like to query?",
            "sheet_selection": "Which sheet contains the data you're looking for?",
            "intent_clarification": "What would you like to know?"
        }
        
        try:
            system_prompt = """You are a helpful assistant that generates clarifying questions.
Generate a natural, conversational question to help disambiguate the user's query.
Keep the question concise and friendly. Return only the question text."""

            # Build option descriptions
            option_descriptions = []
            for i, option in enumerate(options, 1):
                desc = f"{i}. {option.label}"
                if option.description:
                    desc += f" - {option.description}"
                option_descriptions.append(desc)
            
            user_prompt = f"""Original query: "{query}"

Clarification type: {clarification_type}

Available options:
{chr(10).join(option_descriptions)}

Generate a friendly clarifying question to help the user choose the right option."""

            question = self.llm_service.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=100
            )
            
            # Clean up the question
            question = question.strip().strip('"\'')
            
            # Ensure it ends with a question mark
            if not question.endswith('?'):
                question += '?'
            
            return question
            
        except Exception as e:
            logger.warning(f"LLM question generation failed, using fallback: {e}")
            return fallback_questions.get(
                clarification_type,
                "Please select an option:"
            )
    
    def format_clarification_for_display(
        self,
        clarification_request: ClarificationRequest
    ) -> str:
        """
        Format clarification request for display to user.
        
        Args:
            clarification_request: Clarification request
            
        Returns:
            Formatted text for display
        """
        lines = [clarification_request.question, ""]
        
        for i, option in enumerate(clarification_request.options, 1):
            line = f"{i}. {option.label}"
            if option.description:
                line += f"\n   {option.description}"
            lines.append(line)
        
        if clarification_request.allow_none:
            lines.append("")
            lines.append("Or type 'none' if none of these are correct.")
        
        return "\n".join(lines)
