"""
Dependency Checker for Language Processing

Checks if all required language processing dependencies are installed
and provides helpful error messages if not.
"""

import sys
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class DependencyChecker:
    """Check and validate language processing dependencies"""
    
    @staticmethod
    def check_all() -> Tuple[bool, List[str]]:
        """
        Check all language processing dependencies
        
        Returns:
            Tuple of (all_ok: bool, missing_deps: List[str])
        """
        missing = []
        
        # Check langdetect
        try:
            import langdetect
            logger.info("✓ langdetect installed")
        except ImportError:
            missing.append("langdetect - Install with: pip install langdetect")
        
        # Check spaCy
        try:
            import spacy
            logger.info("✓ spaCy installed")
            
            # Check if English model is downloaded
            try:
                nlp = spacy.load("en_core_web_sm")
                logger.info("✓ spaCy English model (en_core_web_sm) installed")
            except OSError:
                missing.append("spaCy English model - Download with: python -m spacy download en_core_web_sm")
        except ImportError:
            missing.append("spaCy - Install with: pip install spacy")
        
        # Check pythainlp
        try:
            import pythainlp
            logger.info("✓ pythainlp installed")
            
            # Check if Thai data is downloaded
            try:
                from pythainlp import word_tokenize
                # Try to tokenize a simple Thai word
                word_tokenize("ทดสอบ", engine="newmm")
                logger.info("✓ pythainlp data installed")
            except Exception as e:
                missing.append(f"pythainlp data - Download with: python -m pythainlp data install")
        except ImportError:
            missing.append("pythainlp - Install with: pip install pythainlp")
        
        # Check NLTK
        try:
            import nltk
            logger.info("✓ NLTK installed")
            
            # Check if required NLTK data is downloaded
            try:
                nltk.data.find('tokenizers/punkt')
                logger.info("✓ NLTK punkt data installed")
            except LookupError:
                missing.append("NLTK punkt data - Download with: python -c \"import nltk; nltk.download('punkt')\"")
            
            try:
                nltk.data.find('corpora/wordnet')
                logger.info("✓ NLTK wordnet data installed")
            except LookupError:
                missing.append("NLTK wordnet data - Download with: python -c \"import nltk; nltk.download('wordnet')\"")
        except ImportError:
            missing.append("NLTK - Install with: pip install nltk")
        
        # Check python-Levenshtein
        try:
            import Levenshtein
            logger.info("✓ python-Levenshtein installed")
        except ImportError:
            missing.append("python-Levenshtein - Install with: pip install python-Levenshtein")
        
        all_ok = len(missing) == 0
        return all_ok, missing
    
    @staticmethod
    def check_and_exit_if_missing():
        """
        Check dependencies and exit with error if any are missing
        
        Use this at application startup to ensure all dependencies are available.
        """
        all_ok, missing = DependencyChecker.check_all()
        
        if not all_ok:
            print("\n" + "=" * 70)
            print("❌ Missing Language Processing Dependencies")
            print("=" * 70)
            print("\nThe following dependencies are required but not installed:\n")
            for dep in missing:
                print(f"  • {dep}")
            print("\n" + "=" * 70)
            print("Quick Install:")
            print("  Run: bash scripts/install_language_dependencies.sh")
            print("=" * 70 + "\n")
            sys.exit(1)
        else:
            logger.info("✅ All language processing dependencies are installed")
    
    @staticmethod
    def get_installation_instructions() -> str:
        """Get installation instructions for missing dependencies"""
        _, missing = DependencyChecker.check_all()
        
        if not missing:
            return "All dependencies are installed!"
        
        instructions = "Missing dependencies:\n\n"
        for dep in missing:
            instructions += f"  • {dep}\n"
        instructions += "\nQuick install all:\n"
        instructions += "  bash scripts/install_language_dependencies.sh\n"
        
        return instructions


if __name__ == "__main__":
    # Run dependency check
    print("Checking language processing dependencies...\n")
    
    all_ok, missing = DependencyChecker.check_all()
    
    if all_ok:
        print("\n✅ All dependencies are installed!")
        sys.exit(0)
    else:
        print("\n❌ Some dependencies are missing:")
        for dep in missing:
            print(f"  • {dep}")
        print("\nRun: bash scripts/install_language_dependencies.sh")
        sys.exit(1)
