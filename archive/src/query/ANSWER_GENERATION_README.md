# Answer Generation System

This document describes the answer generation system for the Google Drive Excel RAG application. The system transforms retrieved data into natural language answers with proper formatting, citations, and confidence scoring.

## Overview

The answer generation system consists of six main components:

1. **PromptBuilder** - Creates structured prompts for LLM-based answer generation
2. **DataFormatter** - Formats numbers, dates, tables, and formulas for presentation
3. **CitationGenerator** - Generates source citations linking answers to Excel files
4. **ConfidenceScorer** - Calculates confidence scores for answers
5. **NoResultsHandler** - Handles queries that return no results with helpful suggestions
6. **AnswerGenerator** - Orchestrates the complete answer generation pipeline

## Components

### 1. PromptBuilder

Creates structured prompts for different types of answers with support for multiple languages.

**Features:**
- Multiple answer types (single value, table, comparison, formula, list, general)
- Multi-language support (English and Thai)
- Automatic language detection
- Answer type inference from query and data
- Structured prompt templates with clear instructions

**Usage:**
```python
from src.query import PromptBuilder, AnswerType, Language

builder = PromptBuilder()

# Build a prompt
prompt = builder.build_answer_prompt(
    query="What were the total expenses?",
    retrieved_data=retrieved_data,
    answer_type=AnswerType.SINGLE_VALUE,
    language=Language.ENGLISH
)

# Build a formula explanation prompt
formula_prompt = builder.build_formula_explanation_prompt(
    formula="=SUM(B2:B9)",
    cell_range="B10",
    sheet_name="Summary",
    file_name="Expenses.xlsx"
)

# Build a comparison prompt
comparison_prompt = builder.build_comparison_prompt(
    query="Compare expenses between January and February",
    comparison_data=comparison_data,
    files_compared=["Jan.xlsx", "Feb.xlsx"]
)
```

**Answer Types:**
- `SINGLE_VALUE` - Direct answers with a single value
- `TABLE` - Data presented in table format
- `COMPARISON` - Comparison across multiple files
- `FORMULA` - Formula explanations
- `LIST` - List of items
- `GENERAL` - General purpose answers

### 2. DataFormatter

Formats Excel data for readable presentation with support for various data types and formats.

**Features:**
- Number formatting (currency, percentage, thousands separator)
- Date formatting (long, short, ISO formats)
- Table formatting (Markdown tables)
- Formula formatting with explanations
- List formatting
- Multi-language support (English and Thai)
- Excel format string parsing

**Usage:**
```python
from src.query import DataFormatter

formatter = DataFormatter(language="en")

# Format currency
formatted = formatter.format_currency(1500.50, "$", 2)
# Output: "$1,500.50"

# Format percentage
formatted = formatter.format_percentage(0.15, 2)
# Output: "15.00%"

# Format date
formatted = formatter.format_date(datetime(2024, 1, 15), "long")
# Output: "January 15, 2024"

# Format table
table = formatter.format_table(
    rows=[
        {"Month": "Jan", "Revenue": 10000},
        {"Month": "Feb", "Revenue": 12000}
    ]
)

# Format formula
formula = formatter.format_formula(
    formula="=SUM(B2:B9)",
    calculated_value=1500.50,
    include_explanation=True
)
```

**Supported Excel Formats:**
- Currency: `$#,##0.00`, `฿#,##0.00`
- Percentage: `0.00%`
- Thousands separator: `#,##0`
- Custom formats parsed automatically

### 3. CitationGenerator

Generates consistent citations for data sources with inline references and citation lists.

**Features:**
- Unique citation numbering
- Inline citation formatting (superscript, bracket, parenthesis)
- Full citation formatting
- Citation list generation
- Grouped citations by file
- Comparison source formatting
- Multi-language support

**Usage:**
```python
from src.query import CitationGenerator

generator = CitationGenerator(language="en")

# Add citations
citation = generator.add_citation(
    file_name="Expenses_Jan2024.xlsx",
    sheet_name="Summary",
    cell_range="B10"
)

# Get inline citation
inline = citation.format_inline()  # "[1]"

# Get full citation
full = citation.format_full()
# "Source: Expenses_Jan2024.xlsx, Sheet: Summary, Cell: B10"

# Generate citation list
citation_list = generator.generate_citation_list()

# Annotate answer with citations
annotated_answer, citations = generator.annotate_answer(
    answer="The total expenses were $1,500.50",
    data_sources=retrieved_data
)
```

**Citation Styles:**
- Superscript: `[1]`
- Bracket: `[1]`
- Parenthesis: `(1)`

### 4. ConfidenceScorer

Calculates confidence scores for answers based on multiple factors.

**Features:**
- Multi-factor confidence calculation
- Detailed breakdown of confidence components
- Confidence level labels
- Formatted explanations
- Multi-language support

**Confidence Components:**
1. **Data Completeness (40%)** - Whether all expected data was found
2. **Semantic Similarity (30%)** - How well the data matches the query
3. **Query Clarity (20%)** - How clear and specific the query is
4. **Selection Confidence (10%)** - Confidence in file/sheet selection

**Usage:**
```python
from src.query import ConfidenceScorer

scorer = ConfidenceScorer(language="en")

# Calculate confidence
breakdown = scorer.calculate_confidence(
    query="What were the total expenses?",
    retrieved_data=retrieved_data,
    ranked_files=ranked_files,
    sheet_selection=sheet_selection,
    expected_data_points=1
)

# Access scores
overall = breakdown.overall_confidence  # 0.0 to 1.0
data_score = breakdown.data_completeness_score
semantic_score = breakdown.semantic_similarity_score

# Format explanation
explanation = scorer.format_confidence_explanation(
    breakdown,
    include_details=True
)

# Get confidence level
level = scorer.get_confidence_level(0.85)  # "high"
```

**Confidence Levels:**
- Very High: ≥ 90%
- High: 75-89%
- Moderate: 60-74%
- Low: 40-59%
- Very Low: < 40%

### 5. NoResultsHandler

Handles queries that return no results with helpful error messages and suggestions.

**Features:**
- Reason determination for no results
- Query refinement suggestions
- Available data display
- Relaxed search options
- Search criteria explanation
- Multi-language support

**Usage:**
```python
from src.query import NoResultsHandler

handler = NoResultsHandler(language="en")

# Handle no results
response = handler.handle_no_results(
    query="What were the marketing costs?",
    search_criteria={
        "query": "marketing costs",
        "date_filter": "December 2024",
        "min_similarity": 0.8
    },
    indexed_files=indexed_files,
    indexed_sheets=indexed_sheets,
    indexed_columns=indexed_columns,
    min_similarity_threshold=0.8
)

# Format response
formatted = handler.format_response(response)

# Get suggestions
suggestions = response.suggestions
available_files = response.available_files
```

**Suggestion Types:**
- Remove date filters
- Remove file name filters
- Lower similarity threshold
- Use different search terms
- Check available data

### 6. AnswerGenerator

Main orchestrator that integrates all components to generate complete query results.

**Features:**
- Complete answer generation pipeline
- Multiple answer types support
- Automatic language detection
- LLM integration with fallback
- Citation integration
- Confidence scoring
- Error handling
- Processing time tracking

**Usage:**
```python
from src.query import AnswerGenerator
from src.abstractions.llm_service_factory import LLMServiceFactory
from src.config import AppConfig

# Load config and create LLM service
config = AppConfig.from_env()
llm_service = LLMServiceFactory.create(
    config.llm.provider,
    config.llm.config
)

# Create answer generator
generator = AnswerGenerator(
    llm_service=llm_service,
    language="en"
)

# Generate answer
result = generator.generate_answer(
    query="What were the total expenses in January?",
    retrieved_data=retrieved_data,
    ranked_files=ranked_files,
    sheet_selection=sheet_selection
)

# Access result
print(result.answer)
print(f"Confidence: {result.confidence:.2%}")
print(f"Processing time: {result.processing_time_ms}ms")

# Generate comparison answer
comparison_result = generator.generate_comparison_answer(
    query="Compare expenses between January and February",
    comparison_result=comparison_result,
    ranked_files=ranked_files
)

# Generate formula explanation
explanation = generator.generate_formula_explanation(
    formula="=SUM(B2:B9)",
    cell_range="B10",
    sheet_name="Summary",
    file_name="Expenses.xlsx",
    calculated_value=1500.50
)
```

**Specialized Methods:**
- `generate_answer()` - General answer generation
- `generate_comparison_answer()` - Comparison queries
- `generate_formula_explanation()` - Formula explanations
- `generate_table_answer()` - Table data presentation
- `generate_single_value_answer()` - Single value answers

## Multi-Language Support

All components support both English and Thai languages:

**English:**
```python
formatter = DataFormatter(language="en")
generator = CitationGenerator(language="en")
scorer = ConfidenceScorer(language="en")
```

**Thai:**
```python
formatter = DataFormatter(language="th")
generator = CitationGenerator(language="th")
scorer = ConfidenceScorer(language="th")
```

**Features:**
- Thai date formatting with Buddhist calendar
- Thai number formatting
- Thai text in prompts and explanations
- Thai confidence level labels
- Thai error messages and suggestions

## Integration with Query Engine

The answer generation system integrates with the QueryEngine:

```python
from src.query import QueryEngine, AnswerGenerator
from src.abstractions.llm_service_factory import LLMServiceFactory
from src.config import AppConfig

# Setup
config = AppConfig.from_env()
llm_service = LLMServiceFactory.create(
    config.llm.provider,
    config.llm.config
)

# Create components
answer_generator = AnswerGenerator(llm_service=llm_service)
query_engine = QueryEngine(
    # ... other dependencies
    answer_generator=answer_generator
)

# Process query
result = query_engine.process_query("What were the expenses?")
```

## Error Handling

The system includes comprehensive error handling:

1. **LLM Failures** - Falls back to structured data presentation
2. **Missing Data** - Provides helpful no results messages
3. **Invalid Formats** - Uses default formatting
4. **Language Detection** - Defaults to English if uncertain

## Performance Considerations

- **Caching** - Citation generator caches citations to avoid duplicates
- **Lazy Formatting** - Data formatted only when needed
- **Batch Processing** - Multiple data points formatted efficiently
- **LLM Timeouts** - Configurable timeouts with fallback

## Examples

See `examples/answer_generation_usage.py` for complete working examples of all components.

## Testing

The system is designed to be testable with mock LLM services:

```python
from unittest.mock import Mock
from src.query import AnswerGenerator

# Create mock LLM
mock_llm = Mock()
mock_llm.generate.return_value = "The total expenses were $1,500.50"

# Test answer generator
generator = AnswerGenerator(llm_service=mock_llm)
result = generator.generate_answer(query, retrieved_data)

assert result.confidence > 0.8
assert "$1,500.50" in result.answer
```

## Future Enhancements

Potential improvements for the answer generation system:

1. **Streaming Responses** - Stream LLM responses for better UX
2. **Answer Caching** - Cache common query answers
3. **Custom Templates** - User-defined prompt templates
4. **Rich Formatting** - HTML/Markdown rendering options
5. **Voice Output** - Text-to-speech for answers
6. **Answer Validation** - Verify answer accuracy against data
7. **Multi-modal Answers** - Include charts and visualizations
8. **Answer History** - Track and learn from answer quality feedback

## Related Documentation

- [Query Processing README](README.md) - Overall query processing system
- [Comparison Engine README](COMPARISON_README.md) - File comparison functionality
- [Design Document](../../.kiro/specs/gdrive-excel-rag/design.md) - System architecture
- [Requirements](../../.kiro/specs/gdrive-excel-rag/requirements.md) - System requirements
