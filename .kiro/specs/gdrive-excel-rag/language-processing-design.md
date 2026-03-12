# Language Processing Design

## Overview

Comprehensive multi-language support for Thai and English, with focus on accurate cell-level matching, query understanding, and morphological variations.

## Language Characteristics

### English
- **Word Boundaries**: Space-separated
- **Morphology**: Rich (plurals, tenses, conjugations)
- **Challenges**: 
  - "expense" vs "expenses"
  - "sold" vs "selling" vs "sells"
  - "category" vs "categories"
  - Compound words: "revenue_total" vs "total revenue"

### Thai (ภาษาไทย)
- **Word Boundaries**: No spaces between words
- **Morphology**: Minimal (no plurals, no verb conjugation)
- **Challenges**:
  - Word segmentation: "ฉันกินข้าว" → ["ฉัน", "กิน", "ข้าว"]
  - Tone marks affect meaning
  - Multiple romanization systems
  - Classifiers for counting
- **Advantages**:
  - No plural/singular variations
  - No tense conjugations
  - Simpler morphology than English

## Architecture

### Layer 1: Language Detection
Detect query and content language(s).

```python
class LanguageDetector:
    def detect(text: str) -> Language
    def detect_mixed(text: str) -> List[LanguageSpan]
    def get_confidence() -> float
```

**Libraries**: `langdetect`, `fasttext`

### Layer 2: Tokenization
Break text into meaningful units.

```python
class Tokenizer(ABC):
    def tokenize(text: str) -> List[Token]
    def detokenize(tokens: List[Token]) -> str

class EnglishTokenizer(Tokenizer):
    # Uses spaCy or NLTK
    
class ThaiTokenizer(Tokenizer):
    # Uses pythainlp (newmm, longest matching)
    
class MultilingualTokenizer(Tokenizer):
    # Delegates to language-specific tokenizers
```

**Libraries**: 
- English: `spaCy`, `nltk`
- Thai: `pythainlp` (newmm algorithm)

### Layer 3: Normalization
Handle morphological variations.

```python
class TextNormalizer(ABC):
    def normalize(text: str) -> str
    def lemmatize(tokens: List[Token]) -> List[str]
    def stem(tokens: List[Token]) -> List[str]

class EnglishNormalizer(TextNormalizer):
    # Lemmatization: "expenses" → "expense"
    # Stemming: "selling" → "sell"
    # Case normalization: "Revenue" → "revenue"
    
class ThaiNormalizer(TextNormalizer):
    # Remove tone marks (optional)
    # Normalize Thai digits to Arabic
    # Handle variant spellings
```

**Libraries**:
- English: `spaCy` (lemmatization), `nltk` (stemming)
- Thai: `pythainlp` (normalization)

### Layer 4: Text Preprocessing Pipeline
Orchestrate all processing steps.

```python
class TextPreprocessor:
    def __init__(self, language: Language):
        self.detector = LanguageDetector()
        self.tokenizer = TokenizerFactory.create(language)
        self.normalizer = NormalizerFactory.create(language)
    
    def preprocess_for_embedding(text: str) -> str:
        """Prepare text for embedding generation"""
        
    def preprocess_for_matching(text: str) -> List[str]:
        """Prepare text for exact/fuzzy matching"""
        
    def extract_keywords(text: str) -> List[str]:
        """Extract important terms for search"""
```

## Use Cases

### Use Case 1: Query Processing
**Query**: "Show me total expenses for January" (English)
**Query**: "แสดงค่าใช้จ่ายทั้งหมดในเดือนมกราคม" (Thai)

**Processing**:
1. Detect language: English / Thai
2. Tokenize: ["Show", "me", "total", "expenses", "for", "January"]
3. Normalize: ["show", "total", "expense", "january"]
4. Extract keywords: ["total", "expense", "january"]
5. Generate embedding (multilingual model handles both)

### Use Case 2: Cell Content Matching
**Excel Header**: "Total Expenses" or "ค่าใช้จ่ายรวม"
**Query**: "expense" or "ค่าใช้จ่าย"

**Matching Strategy**:
1. **Semantic Match** (primary): Use embeddings
   - "expense" matches "Total Expenses" (high similarity)
   - "ค่าใช้จ่าย" matches "ค่าใช้จ่ายรวม" (high similarity)

2. **Keyword Match** (fallback): Use normalized tokens
   - Lemmatize: "expenses" → "expense"
   - Thai: Already in base form
   - Fuzzy match with Levenshtein distance

3. **Exact Match** (highest priority): Direct string comparison
   - Case-insensitive
   - Whitespace normalized

### Use Case 3: Mixed Language Content
**Excel Header**: "Revenue (รายได้)"
**Query**: "What is the revenue?" or "รายได้เท่าไหร่"

**Processing**:
1. Detect mixed language in header
2. Create embeddings for both parts
3. Match query against either language
4. Return result with original formatting

## Implementation Details

### English Morphology Handling

```python
class EnglishNormalizer:
    def __init__(self):
        import spacy
        self.nlp = spacy.load("en_core_web_sm")
    
    def lemmatize(self, text: str) -> List[str]:
        """
        Handle morphological variations:
        - Plurals: expenses → expense
        - Tenses: sold/selling/sells → sell
        - Gerunds: running → run
        """
        doc = self.nlp(text)
        return [token.lemma_ for token in doc]
    
    def normalize_for_matching(self, text: str) -> str:
        """
        Normalize for cell matching:
        - Lowercase
        - Lemmatize
        - Remove punctuation
        - Handle compound words
        """
        lemmas = self.lemmatize(text.lower())
        return " ".join(lemmas)
```

### Thai Word Segmentation

```python
class ThaiTokenizer:
    def __init__(self):
        from pythainlp import word_tokenize
        self.tokenize_func = word_tokenize
    
    def tokenize(self, text: str) -> List[str]:
        """
        Segment Thai text into words:
        "ฉันกินข้าว" → ["ฉัน", "กิน", "ข้าว"]
        
        Uses newmm (Maximum Matching) algorithm
        """
        return self.tokenize_func(text, engine='newmm')
    
    def normalize(self, text: str) -> str:
        """
        Normalize Thai text:
        - Convert Thai digits to Arabic
        - Normalize whitespace
        - Optional: Remove tone marks for fuzzy matching
        """
        from pythainlp.util import normalize
        return normalize(text)
```

### Multilingual Embedding Strategy

```python
class MultilingualEmbeddingStrategy:
    """
    Strategy for handling multilingual content in embeddings
    """
    
    def embed_cell_content(self, text: str) -> List[float]:
        """
        Embed cell content with language awareness:
        1. Detect language
        2. Preprocess appropriately
        3. Generate embedding
        """
        language = self.detector.detect(text)
        
        if language == Language.THAI:
            # Tokenize Thai text first
            tokens = self.thai_tokenizer.tokenize(text)
            processed = " ".join(tokens)
        else:
            # English: lemmatize for better matching
            processed = self.english_normalizer.normalize_for_matching(text)
        
        return self.embedding_service.embed_text(processed)
    
    def embed_for_search(self, query: str) -> List[float]:
        """
        Embed query with same preprocessing as content
        """
        return self.embed_cell_content(query)
```

## Matching Strategies

### Strategy 1: Semantic Matching (Primary)
Use multilingual embeddings for fuzzy semantic matching.

**Pros**:
- Handles morphological variations automatically
- Works across languages
- Handles synonyms and related terms

**Cons**:
- May miss exact matches
- Requires good embedding model

**When to Use**: Default for all queries

### Strategy 2: Normalized Keyword Matching (Secondary)
Use lemmatized/tokenized keywords for exact matching.

**Pros**:
- Precise for exact terms
- Fast
- Handles morphological variations

**Cons**:
- Misses semantic relationships
- Language-specific

**When to Use**: When semantic match confidence < 0.7

### Strategy 3: Fuzzy String Matching (Fallback)
Use Levenshtein distance for typos and variations.

**Pros**:
- Handles typos
- Language-agnostic

**Cons**:
- Slow for large datasets
- May produce false positives

**When to Use**: When other methods fail

## Configuration

### Language Settings

```bash
# Language Support
SUPPORTED_LANGUAGES=en,th
DEFAULT_LANGUAGE=en
ENABLE_LANGUAGE_DETECTION=true
LANGUAGE_DETECTION_CONFIDENCE_THRESHOLD=0.8

# Text Processing
ENABLE_LEMMATIZATION=true  # English
ENABLE_THAI_TOKENIZATION=true
THAI_TOKENIZER_ENGINE=newmm  # or 'longest', 'deepcut'

# Matching Strategy
SEMANTIC_MATCH_THRESHOLD=0.7
ENABLE_KEYWORD_FALLBACK=true
ENABLE_FUZZY_MATCHING=true
FUZZY_MATCH_THRESHOLD=0.85

# Embedding Strategy
PREPROCESS_BEFORE_EMBEDDING=true  # Tokenize/lemmatize before embedding
```

## Dependencies

### Required Libraries

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

## Testing Strategy

### Test Cases

1. **English Morphology**
   - Query: "expense" → Match: "Expenses", "Total Expenses"
   - Query: "sold" → Match: "Selling", "Sales"
   - Query: "category" → Match: "Categories"

2. **Thai Tokenization**
   - Text: "ค่าใช้จ่ายรวม" → Tokens: ["ค่าใช้จ่าย", "รวม"]
   - Query: "ค่าใช้จ่าย" → Match: "ค่าใช้จ่ายรวม"

3. **Mixed Language**
   - Header: "Revenue (รายได้)"
   - Query: "revenue" → Match ✓
   - Query: "รายได้" → Match ✓

4. **Case Sensitivity**
   - Query: "REVENUE" → Match: "Revenue", "revenue", "REVENUE"

5. **Compound Words**
   - Query: "total revenue" → Match: "TotalRevenue", "total_revenue"

## Performance Considerations

### Optimization Strategies

1. **Caching**
   - Cache tokenization results
   - Cache lemmatization results
   - Cache language detection results

2. **Batch Processing**
   - Tokenize multiple texts in batch
   - Lemmatize in batch with spaCy

3. **Lazy Loading**
   - Load language models on demand
   - Unload unused models

4. **Preprocessing at Index Time**
   - Preprocess and store normalized versions
   - Store both original and normalized in metadata

## Migration Path

### Phase 1: Basic Support (MVP)
- Language detection
- Thai tokenization with pythainlp
- English lemmatization with spaCy
- Multilingual embeddings

### Phase 2: Enhanced Matching
- Fuzzy matching
- Compound word handling
- Synonym expansion

### Phase 3: Advanced Features
- Custom dictionaries for domain terms
- Named entity recognition
- Context-aware disambiguation

## Error Handling

### Language Detection Failures
- **Issue**: Cannot detect language with confidence
- **Solution**: Default to English, try both languages

### Tokenization Errors
- **Issue**: Thai tokenization produces unexpected results
- **Solution**: Fall back to character-level or use multiple engines

### Missing Language Models
- **Issue**: spaCy or pythainlp models not installed
- **Solution**: Graceful degradation to basic processing

## Monitoring

### Metrics to Track
- Language detection accuracy
- Query match success rate by language
- Average processing time per language
- Cache hit rates

### Logging
- Log detected language for each query
- Log tokenization results (debug mode)
- Log matching strategy used
- Log confidence scores
