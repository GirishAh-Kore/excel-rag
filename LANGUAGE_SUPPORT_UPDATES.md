# Multi-Language Support Updates

## Summary

Added comprehensive Thai + English language support to the Google Drive Excel RAG system, with focus on accurate cell-level matching and morphological variation handling.

## Key Decisions

### Why Option 2 (Full Support)?
You correctly identified that cell-level queries require proper linguistic processing:
- **English**: Need lemmatization for "expense" vs "expenses", "sold" vs "selling"
- **Thai**: Need tokenization because there are no spaces between words
- **Both**: Need semantic + keyword matching strategies

### Thai Language Characteristics
- ✅ **Simpler morphology**: No plurals, no verb conjugation
- ⚠️ **Complex tokenization**: No word boundaries ("ฉันกินข้าว" = "I eat rice")
- ✅ **No tense variations**: Makes matching easier than English
- ⚠️ **Tone marks**: Can affect meaning

## Documents Updated

### 1. Requirements Document (.kiro/specs/gdrive-excel-rag/requirements.md)
**Added**:
- **Requirement 11**: Thai language query support
  - Language detection (80% confidence)
  - Thai tokenization
  - Thai content preservation
  - Thai response generation

- **Requirement 12**: Bilingual (Thai + English) support
  - Mixed-language content indexing
  - Cross-language querying
  - Multilingual embeddings

- **Requirement 13**: Morphological variation handling
  - English lemmatization (expense/expenses)
  - Verb tense normalization
  - Thai tokenization
  - Semantic + keyword matching strategies

**Updated Glossary**:
- Added Language Detector, Text Preprocessor, Lemmatization, Tokenization, Multilingual Embeddings

### 2. Language Processing Design (.kiro/specs/gdrive-excel-rag/language-processing-design.md)
**Created comprehensive design covering**:
- Language characteristics (English vs Thai)
- 4-layer architecture:
  1. Language Detection
  2. Tokenization
  3. Normalization
  4. Text Preprocessing Pipeline
- Use cases and matching strategies
- Implementation details with code examples
- Configuration and dependencies
- Testing strategy

### 3. Tasks Document (.kiro/specs/gdrive-excel-rag/tasks.md)
**Added Task 2.5**: Implement multi-language support (6 subtasks)
- 2.5.1: Language detection module
- 2.5.2: Tokenization layer (English + Thai)
- 2.5.3: Text normalization layer (lemmatization + Thai normalization)
- 2.5.4: Text preprocessing pipeline
- 2.5.5: Configuration updates
- 2.5.6: Dependency installation

## Architecture Overview

### Processing Layers

```
User Query (Thai or English)
    ↓
[Language Detection] → Detect: Thai/English/Mixed
    ↓
[Tokenization] → English: spaCy | Thai: pythainlp
    ↓
[Normalization] → English: Lemmatize | Thai: Normalize
    ↓
[Preprocessing] → Prepare for embedding/matching
    ↓
[Embedding] → Multilingual model (OpenAI/Cohere)
    ↓
[Matching] → Semantic (primary) + Keyword (fallback)
    ↓
Answer in Query Language
```

### Matching Strategies

1. **Semantic Matching** (Primary - 70%+ confidence)
   - Use multilingual embeddings
   - Handles morphology automatically
   - Works across languages

2. **Keyword Matching** (Fallback - <70% confidence)
   - Use lemmatized/tokenized keywords
   - Exact term matching
   - Language-specific

3. **Fuzzy Matching** (Last resort)
   - Levenshtein distance
   - Handle typos
   - Language-agnostic

## Dependencies to Install

```bash
# Language Detection
pip install langdetect fasttext

# English Processing
pip install spacy
python -m spacy download en_core_web_sm

# Thai Processing
pip install pythainlp
python -m pythainlp data install

# Text Processing
pip install nltk
python -m nltk.downloader punkt wordnet

# Fuzzy Matching
pip install python-Levenshtein
```

## Configuration Changes

### New Environment Variables

```bash
# Language Support
SUPPORTED_LANGUAGES=en,th
DEFAULT_LANGUAGE=en
ENABLE_LANGUAGE_DETECTION=true
LANGUAGE_DETECTION_CONFIDENCE_THRESHOLD=0.8

# Text Processing
ENABLE_LEMMATIZATION=true  # English morphology
ENABLE_THAI_TOKENIZATION=true
THAI_TOKENIZER_ENGINE=newmm

# Matching Strategy
SEMANTIC_MATCH_THRESHOLD=0.7
ENABLE_KEYWORD_FALLBACK=true
ENABLE_FUZZY_MATCHING=true
FUZZY_MATCH_THRESHOLD=0.85

# Preprocessing
PREPROCESS_BEFORE_EMBEDDING=true
```

## Example Use Cases

### Use Case 1: English Morphology
**Query**: "Show me total expenses"
**Excel Header**: "Total Expense" or "Expenses"
**Processing**:
1. Detect: English
2. Tokenize: ["Show", "me", "total", "expenses"]
3. Lemmatize: ["show", "total", "expense"]
4. Match: "expense" matches "Expense", "Expenses", "EXPENSES"

### Use Case 2: Thai Tokenization
**Query**: "แสดงค่าใช้จ่ายทั้งหมด" (Show all expenses)
**Excel Header**: "ค่าใช้จ่ายรวม" (Total expenses)
**Processing**:
1. Detect: Thai
2. Tokenize: ["แสดง", "ค่าใช้จ่าย", "ทั้งหมด"]
3. Normalize: Thai text normalization
4. Match: "ค่าใช้จ่าย" matches "ค่าใช้จ่ายรวม"

### Use Case 3: Mixed Language
**Query**: "What is the รายได้?" (What is the revenue?)
**Excel Header**: "Revenue (รายได้)"
**Processing**:
1. Detect: Mixed (English + Thai)
2. Tokenize both parts separately
3. Match against either language
4. Return with both languages preserved

## Testing Strategy

### Test Coverage
1. **English Morphology**
   - Plurals: expense/expenses
   - Tenses: sold/selling/sells
   - Case: REVENUE/Revenue/revenue

2. **Thai Tokenization**
   - Word segmentation accuracy
   - Compound words
   - Proper nouns

3. **Mixed Language**
   - English query → Thai content
   - Thai query → English content
   - Mixed query → Mixed content

4. **Edge Cases**
   - Very short queries
   - Numbers and dates
   - Special characters
   - Typos and misspellings

## Performance Considerations

### Optimization Strategies
1. **Caching**: Cache tokenization and lemmatization results
2. **Batch Processing**: Process multiple texts together
3. **Lazy Loading**: Load language models on demand
4. **Index-time Preprocessing**: Store normalized versions

### Expected Performance
- Language detection: <10ms
- Tokenization: <50ms per text
- Lemmatization: <100ms per text
- Total preprocessing overhead: <200ms per query

## Migration Impact

### Existing Tasks
- ✅ **Task 1-2**: No changes needed (already complete)
- ⚠️ **Task 3**: Add language field to data models
- ⚠️ **Task 6**: Update Content Extractor to preserve Thai text
- ⚠️ **Task 7**: Update Indexing Pipeline to use preprocessing
- ⚠️ **Task 8**: Update Query Engine with language detection
- ⚠️ **Task 11**: Update Answer Generator to match query language

### New Task
- ➕ **Task 2.5**: Implement multi-language support (6 subtasks)

## Next Steps

1. **Review** this document and the updated requirements/design
2. **Confirm** the approach meets your needs
3. **Implement** Task 2.5 (estimated 1-2 days)
4. **Test** with Thai and English Excel files
5. **Iterate** based on real-world usage

## Questions for You

1. Do you have sample Thai Excel files we should test with?
2. Are there specific Thai terms or domain vocabulary we should handle?
3. Should we support Thai numerals (๐-๙) or just Arabic (0-9)?
4. Do you need romanization support (Thai → English transliteration)?
5. Should we handle formal vs informal Thai language?

## Benefits of This Approach

✅ **Accurate Matching**: Handles "expense" vs "expenses", Thai word boundaries
✅ **Cross-Language**: Query in English, find Thai content (and vice versa)
✅ **Extensible**: Easy to add more languages later
✅ **Performant**: Caching and batch processing
✅ **Configurable**: Turn features on/off via environment variables
✅ **Tested**: Comprehensive test coverage for both languages
