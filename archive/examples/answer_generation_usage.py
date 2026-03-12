"""
Example usage of the answer generation system.

This script demonstrates how to use the PromptBuilder, DataFormatter,
CitationGenerator, ConfidenceScorer, NoResultsHandler, and AnswerGenerator
to create complete query responses.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.models.domain_models import (
    RetrievedData,
    RankedFile,
    FileMetadata,
    FileStatus,
    SheetSelection,
    DataType
)
from src.query import (
    PromptBuilder,
    AnswerType,
    Language,
    DataFormatter,
    CitationGenerator,
    ConfidenceScorer,
    NoResultsHandler,
    AnswerGenerator
)
from src.abstractions.llm_service_factory import LLMServiceFactory
from src.config import AppConfig


def example_prompt_builder():
    """Demonstrate PromptBuilder usage."""
    print("=" * 80)
    print("EXAMPLE 1: Prompt Builder")
    print("=" * 80)
    
    builder = PromptBuilder()
    
    # Create sample retrieved data
    retrieved_data = [
        RetrievedData(
            file_name="Expenses_Jan2024.xlsx",
            file_path="/Finance/2024/Expenses_Jan2024.xlsx",
            sheet_name="Summary",
            cell_range="B10",
            data=1500.50,
            data_type=DataType.NUMBER,
            original_format="$#,##0.00"
        )
    ]
    
    # Build a prompt for a single value answer
    prompt = builder.build_answer_prompt(
        query="What were the total expenses in January?",
        retrieved_data=retrieved_data,
        answer_type=AnswerType.SINGLE_VALUE,
        language=Language.ENGLISH
    )
    
    print("\nGenerated Prompt:")
    print("-" * 80)
    print(prompt)
    print()


def example_data_formatter():
    """Demonstrate DataFormatter usage."""
    print("=" * 80)
    print("EXAMPLE 2: Data Formatter")
    print("=" * 80)
    
    formatter = DataFormatter(language="en")
    
    # Format currency
    print("\n1. Currency Formatting:")
    print(f"   Value: 1500.50")
    print(f"   Formatted: {formatter.format_currency(1500.50, '$', 2)}")
    
    # Format percentage
    print("\n2. Percentage Formatting:")
    print(f"   Value: 0.15")
    print(f"   Formatted: {formatter.format_percentage(0.15, 2)}")
    
    # Format date
    print("\n3. Date Formatting:")
    date_value = datetime(2024, 1, 15)
    print(f"   Value: {date_value}")
    print(f"   Long format: {formatter.format_date(date_value, 'long')}")
    print(f"   Short format: {formatter.format_date(date_value, 'short')}")
    
    # Format table
    print("\n4. Table Formatting:")
    table_data = [
        {"Month": "January", "Revenue": 10000, "Expenses": 7000},
        {"Month": "February", "Revenue": 12000, "Expenses": 8000},
        {"Month": "March", "Revenue": 11000, "Expenses": 7500}
    ]
    table = formatter.format_table(table_data)
    print(table)
    
    # Format formula
    print("\n5. Formula Formatting:")
    formula = formatter.format_formula(
        formula="=SUM(B2:B9)",
        calculated_value=1500.50,
        include_explanation=True
    )
    print(formula)
    print()


def example_citation_generator():
    """Demonstrate CitationGenerator usage."""
    print("=" * 80)
    print("EXAMPLE 3: Citation Generator")
    print("=" * 80)
    
    generator = CitationGenerator(language="en")
    
    # Add citations
    citation1 = generator.add_citation(
        file_name="Expenses_Jan2024.xlsx",
        sheet_name="Summary",
        cell_range="B10"
    )
    
    citation2 = generator.add_citation(
        file_name="Expenses_Feb2024.xlsx",
        sheet_name="Summary",
        cell_range="B10"
    )
    
    print("\n1. Inline Citations:")
    print(f"   Citation 1: {citation1.format_inline()}")
    print(f"   Citation 2: {citation2.format_inline()}")
    
    print("\n2. Full Citations:")
    print(f"   {citation1.format_full()}")
    print(f"   {citation2.format_full()}")
    
    print("\n3. Citation List:")
    citation_list = generator.generate_citation_list()
    print(citation_list)
    print()


def example_confidence_scorer():
    """Demonstrate ConfidenceScorer usage."""
    print("=" * 80)
    print("EXAMPLE 4: Confidence Scorer")
    print("=" * 80)
    
    scorer = ConfidenceScorer(language="en")
    
    # Create sample data
    retrieved_data = [
        RetrievedData(
            file_name="Expenses_Jan2024.xlsx",
            file_path="/Finance/2024/Expenses_Jan2024.xlsx",
            sheet_name="Summary",
            cell_range="B10",
            data=1500.50,
            data_type=DataType.NUMBER,
            original_format="$#,##0.00"
        )
    ]
    
    ranked_files = [
        RankedFile(
            file_metadata=FileMetadata(
                file_id="1abc",
                name="Expenses_Jan2024.xlsx",
                path="/Finance/2024/Expenses_Jan2024.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                size=52480,
                modified_time=datetime(2024, 1, 15),
                md5_checksum="abc123",
                status=FileStatus.INDEXED
            ),
            relevance_score=0.92,
            semantic_score=0.95,
            metadata_score=0.88,
            preference_score=0.90
        )
    ]
    
    sheet_selection = SheetSelection(
        sheet_name="Summary",
        relevance_score=0.87,
        requires_clarification=False
    )
    
    # Calculate confidence
    breakdown = scorer.calculate_confidence(
        query="What were the total expenses in January?",
        retrieved_data=retrieved_data,
        ranked_files=ranked_files,
        sheet_selection=sheet_selection,
        expected_data_points=1
    )
    
    print("\nConfidence Breakdown:")
    print(f"  Overall: {breakdown.overall_confidence:.2%}")
    print(f"  Data Completeness: {breakdown.data_completeness_score:.2%} - {breakdown.data_completeness_reason}")
    print(f"  Semantic Similarity: {breakdown.semantic_similarity_score:.2%} - {breakdown.semantic_similarity_reason}")
    print(f"  Query Clarity: {breakdown.query_ambiguity_score:.2%} - {breakdown.query_ambiguity_reason}")
    print(f"  Selection Confidence: {breakdown.selection_confidence_score:.2%} - {breakdown.selection_confidence_reason}")
    
    print("\nFormatted Explanation:")
    explanation = scorer.format_confidence_explanation(breakdown, include_details=True)
    print(explanation)
    print()


def example_no_results_handler():
    """Demonstrate NoResultsHandler usage."""
    print("=" * 80)
    print("EXAMPLE 5: No Results Handler")
    print("=" * 80)
    
    handler = NoResultsHandler(language="en")
    
    # Create sample indexed data
    indexed_files = [
        FileMetadata(
            file_id="1abc",
            name="Expenses_Jan2024.xlsx",
            path="/Finance/2024/Expenses_Jan2024.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size=52480,
            modified_time=datetime(2024, 1, 15),
            md5_checksum="abc123",
            status=FileStatus.INDEXED
        ),
        FileMetadata(
            file_id="2def",
            name="Revenue_Q1_2024.xlsx",
            path="/Finance/2024/Revenue_Q1_2024.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size=48320,
            modified_time=datetime(2024, 3, 31),
            md5_checksum="def456",
            status=FileStatus.INDEXED
        )
    ]
    
    indexed_sheets = ["Summary", "Details", "Monthly", "Quarterly"]
    indexed_columns = {"Month", "Revenue", "Expenses", "Profit", "Category"}
    
    # Handle no results
    response = handler.handle_no_results(
        query="What were the marketing costs in December?",
        search_criteria={
            "query": "marketing costs December",
            "date_filter": "December 2024",
            "min_similarity": 0.8
        },
        indexed_files=indexed_files,
        indexed_sheets=indexed_sheets,
        indexed_columns=indexed_columns,
        min_similarity_threshold=0.8
    )
    
    print("\nNo Results Response:")
    formatted = handler.format_response(response)
    print(formatted)
    print()


def example_answer_generator():
    """Demonstrate AnswerGenerator usage."""
    print("=" * 80)
    print("EXAMPLE 6: Answer Generator (with mock LLM)")
    print("=" * 80)
    
    # Note: This example uses a mock LLM service
    # In production, use actual LLM service from config
    
    print("\nNote: This example requires a configured LLM service.")
    print("To run this example:")
    print("1. Set up your .env file with LLM credentials")
    print("2. Uncomment the code below")
    print()
    
    # Uncomment to run with actual LLM:
    """
    # Load config
    config = AppConfig.from_env()
    
    # Create LLM service
    from src.abstractions.llm_service_factory import LLMServiceFactory
    llm_service = LLMServiceFactory.create(
        config.llm.provider,
        config.llm.config
    )
    
    # Create answer generator
    generator = AnswerGenerator(
        llm_service=llm_service,
        language="en"
    )
    
    # Create sample data
    retrieved_data = [
        RetrievedData(
            file_name="Expenses_Jan2024.xlsx",
            file_path="/Finance/2024/Expenses_Jan2024.xlsx",
            sheet_name="Summary",
            cell_range="B10",
            data=1500.50,
            data_type=DataType.NUMBER,
            original_format="$#,##0.00"
        )
    ]
    
    # Generate answer
    result = generator.generate_answer(
        query="What were the total expenses in January?",
        retrieved_data=retrieved_data
    )
    
    print("\nGenerated Answer:")
    print(result.answer)
    print(f"\nConfidence: {result.confidence:.2%}")
    print(f"Processing Time: {result.processing_time_ms}ms")
    """


def example_thai_language():
    """Demonstrate Thai language support."""
    print("=" * 80)
    print("EXAMPLE 7: Thai Language Support")
    print("=" * 80)
    
    # Data formatter in Thai
    formatter = DataFormatter(language="th")
    
    print("\n1. Thai Date Formatting:")
    date_value = datetime(2024, 1, 15)
    print(f"   Long format: {formatter.format_date(date_value, 'long')}")
    
    # Citation generator in Thai
    generator = CitationGenerator(language="th")
    citation = generator.add_citation(
        file_name="ค่าใช้จ่าย_ม.ค._2567.xlsx",
        sheet_name="สรุป",
        cell_range="B10"
    )
    
    print("\n2. Thai Citation:")
    print(f"   {citation.format_full('th')}")
    
    # Confidence scorer in Thai
    scorer = ConfidenceScorer(language="th")
    confidence_level = scorer.get_confidence_level(0.85)
    print(f"\n3. Thai Confidence Level:")
    print(f"   0.85 = {confidence_level}")
    print()


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "ANSWER GENERATION SYSTEM EXAMPLES" + " " * 25 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    try:
        example_prompt_builder()
        example_data_formatter()
        example_citation_generator()
        example_confidence_scorer()
        example_no_results_handler()
        example_answer_generator()
        example_thai_language()
        
        print("=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)
        print()
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
