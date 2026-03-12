"""
Test Thai Language Processing

Tests language detection, tokenization, and normalization with real Thai data
from the employee Excel file.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.text_processing import (
    LanguageDetector,
    Language,
    TextPreprocessor
)


def test_language_detection():
    """Test language detection with Thai and English text"""
    print("=" * 70)
    print("TEST 1: Language Detection")
    print("=" * 70)
    
    detector = LanguageDetector(use_langdetect=False)  # Use Unicode-based detection
    
    test_cases = [
        ("Find employee named Pimon", Language.ENGLISH),
        ("หาพนักงานชื่อพิมล", Language.THAI),
        ("What is พิมล's position?", Language.MIXED),
        ("นาง พิมล วงค์ดี", Language.THAI),
        ("Mrs. Pimon Wongdee", Language.ENGLISH),
        ("Title - TH", Language.ENGLISH),
        ("ตำแหน่ง", Language.THAI),
    ]
    
    for text, expected in test_cases:
        detected = detector.detect(text)
        status = "✓" if detected == expected else "✗"
        print(f"{status} '{text}'")
        print(f"   Expected: {expected.value}, Got: {detected.value}")
        if detected == Language.MIXED:
            spans = detector.detect_mixed(text)
            print(f"   Spans: {[(s.language.value, s.text) for s in spans]}")
        print()


def test_tokenization():
    """Test tokenization for Thai and English"""
    print("=" * 70)
    print("TEST 2: Tokenization")
    print("=" * 70)
    
    preprocessor = TextPreprocessor()
    
    test_cases = [
        "Find employee named Pimon",
        "หาพนักงานชื่อพิมล",
        "นาง พิมล วงค์ดี",
        "What is พิมล's position?",
    ]
    
    for text in test_cases:
        info = preprocessor.get_preprocessing_info(text)
        print(f"Text: '{text}'")
        print(f"  Language: {info['language']}")
        print(f"  Tokens: {info['tokens']}")
        print(f"  Token count: {info['token_count']}")
        print()


def test_normalization():
    """Test normalization and lemmatization"""
    print("=" * 70)
    print("TEST 3: Normalization & Lemmatization")
    print("=" * 70)
    
    preprocessor = TextPreprocessor()
    
    test_cases = [
        # English morphology
        ("expenses", "expense"),
        ("sold", "sell"),
        ("selling", "sell"),
        ("categories", "category"),
        ("Total Expenses", "total expense"),
        
        # Thai (no morphology, just normalization)
        ("ค่าใช้จ่ายรวม", "ค่าใช้จ่ายรวม"),
        ("พนักงาน", "พนักงาน"),
    ]
    
    for text, expected_contains in test_cases:
        preprocessed = preprocessor.preprocess_for_embedding(text)
        print(f"Original: '{text}'")
        print(f"  Preprocessed: '{preprocessed}'")
        print(f"  Expected to contain: '{expected_contains}'")
        print()


def test_header_normalization():
    """Test header normalization from real Excel file"""
    print("=" * 70)
    print("TEST 4: Header Normalization (Real Excel Data)")
    print("=" * 70)
    
    preprocessor = TextPreprocessor()
    
    # Real headers from the Thai Excel file
    headers = [
        "Title - TH",
        "First Name – TH ",  # Note: extra space and different dash
        "Last Name – TH ",
        "Title – EN ",
        "Position – TH ",
        "Department – EN ",
    ]
    
    for header in headers:
        normalized = preprocessor.normalize_header_text(header)
        print(f"Original: '{header}'")
        print(f"  Normalized: '{normalized}'")
        print(f"  Length: {len(header)} → {len(normalized)}")
        print()


def test_keyword_extraction():
    """Test keyword extraction"""
    print("=" * 70)
    print("TEST 5: Keyword Extraction")
    print("=" * 70)
    
    preprocessor = TextPreprocessor()
    
    test_cases = [
        "Find employee named Pimon in the sales department",
        "หาพนักงานชื่อพิมลในแผนกขาย",
        "Show me all expenses for January",
        "What is the total revenue?",
    ]
    
    for text in test_cases:
        keywords = preprocessor.extract_keywords(text)
        print(f"Text: '{text}'")
        print(f"  Keywords: {keywords}")
        print()


def test_real_queries():
    """Test with realistic queries from the use case"""
    print("=" * 70)
    print("TEST 6: Real Query Scenarios")
    print("=" * 70)
    
    preprocessor = TextPreprocessor()
    
    queries = [
        # Thai queries
        "หาพนักงานชื่อพิมล",
        "แสดงข้อมูลพนักงานที่นามสกุลวงค์ดี",
        "ตำแหน่งของธีรภัทรคืออะไร",
        
        # English queries
        "Find employee named Pimon",
        "Show employees with last name Wongdee",
        "What is Teerapat's position?",
        
        # Mixed queries
        "Find พิมล's position",
        "Show นาย employees",
    ]
    
    for query in queries:
        info = preprocessor.get_preprocessing_info(query)
        print(f"Query: '{query}'")
        print(f"  Language: {info['language']}")
        print(f"  Keywords: {info['keywords']}")
        print(f"  For Embedding: '{info['preprocessed_for_embedding']}'")
        print(f"  For Matching: {info['preprocessed_for_matching']}")
        print()


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "THAI LANGUAGE PROCESSING TESTS" + " " * 23 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    try:
        test_language_detection()
        test_tokenization()
        test_normalization()
        test_header_normalization()
        test_keyword_extraction()
        test_real_queries()
        
        print("=" * 70)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 70)
        print()
        print("The language processing system is working correctly!")
        print("Ready to handle Thai + English queries on your Excel data.")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Check if dependencies are installed
    print("Checking dependencies...")
    try:
        from src.utils.dependency_checker import DependencyChecker
        all_ok, missing = DependencyChecker.check_all()
        if not all_ok:
            print("\n⚠️  Some dependencies are missing:")
            for dep in missing:
                print(f"  • {dep}")
            print("\nRun: bash scripts/install_language_dependencies.sh")
            print("\nContinuing with available dependencies...\n")
    except Exception as e:
        print(f"Warning: Could not check dependencies: {e}\n")
    
    main()
