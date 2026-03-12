"""
Basic test to verify comparison engine components can be imported and instantiated.
Run this after installing all dependencies.
"""

def test_imports():
    """Test that all comparison engine components can be imported."""
    print("Testing imports...")
    
    try:
        from src.query.comparison_engine import ComparisonEngine
        print("✓ ComparisonEngine imported")
    except ImportError as e:
        print(f"✗ Failed to import ComparisonEngine: {e}")
        return False
    
    try:
        from src.query.sheet_aligner import SheetAligner
        print("✓ SheetAligner imported")
    except ImportError as e:
        print(f"✗ Failed to import SheetAligner: {e}")
        return False
    
    try:
        from src.query.difference_calculator import DifferenceCalculator, TrendDirection
        print("✓ DifferenceCalculator imported")
    except ImportError as e:
        print(f"✗ Failed to import DifferenceCalculator: {e}")
        return False
    
    try:
        from src.query.comparison_formatter import ComparisonFormatter
        print("✓ ComparisonFormatter imported")
    except ImportError as e:
        print(f"✗ Failed to import ComparisonFormatter: {e}")
        return False
    
    return True


def test_instantiation():
    """Test that components can be instantiated."""
    print("\nTesting instantiation...")
    
    try:
        from src.query.sheet_aligner import SheetAligner
        aligner = SheetAligner()
        print("✓ SheetAligner instantiated")
    except Exception as e:
        print(f"✗ Failed to instantiate SheetAligner: {e}")
        return False
    
    try:
        from src.query.difference_calculator import DifferenceCalculator
        calculator = DifferenceCalculator()
        print("✓ DifferenceCalculator instantiated")
    except Exception as e:
        print(f"✗ Failed to instantiate DifferenceCalculator: {e}")
        return False
    
    try:
        from src.query.comparison_formatter import ComparisonFormatter
        formatter = ComparisonFormatter()
        print("✓ ComparisonFormatter instantiated")
    except Exception as e:
        print(f"✗ Failed to instantiate ComparisonFormatter: {e}")
        return False
    
    return True


def test_basic_alignment():
    """Test basic sheet alignment functionality."""
    print("\nTesting basic alignment...")
    
    try:
        from src.query.sheet_aligner import SheetAligner
        from src.models.domain_models import SheetData
        
        aligner = SheetAligner()
        
        # Create test sheets
        sheet1 = SheetData(
            sheet_name='Summary',
            headers=['Month', 'Revenue'],
            rows=[{'Month': 'Jan', 'Revenue': 10000}],
            data_types={'Month': 'text', 'Revenue': 'number'},
            row_count=1,
            column_count=2,
            summary='Test sheet',
            has_dates=False,
            has_numbers=True
        )
        
        sheet2 = SheetData(
            sheet_name='Summary',
            headers=['Month', 'Revenue'],
            rows=[{'Month': 'Jan', 'Revenue': 12000}],
            data_types={'Month': 'text', 'Revenue': 'number'},
            row_count=1,
            column_count=2,
            summary='Test sheet',
            has_dates=False,
            has_numbers=True
        )
        
        # Align sheets
        aligned = aligner.align_sheets([sheet1, sheet2], ['file1', 'file2'])
        
        assert len(aligned.common_columns) == 2, "Should have 2 common columns"
        assert 'Month' in aligned.common_columns, "Should have Month column"
        assert 'Revenue' in aligned.common_columns, "Should have Revenue column"
        
        print(f"✓ Basic alignment works (common columns: {aligned.common_columns})")
        return True
        
    except Exception as e:
        print(f"✗ Basic alignment failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_basic_difference_calculation():
    """Test basic difference calculation."""
    print("\nTesting basic difference calculation...")
    
    try:
        from src.query.difference_calculator import DifferenceCalculator
        from src.models.domain_models import AlignedData
        
        calculator = DifferenceCalculator()
        
        # Create test aligned data
        aligned_data = AlignedData(
            common_columns=['Month', 'Revenue'],
            file_data={
                'file1': [{'Month': 'Jan', 'Revenue': 10000}],
                'file2': [{'Month': 'Jan', 'Revenue': 12000}]
            },
            missing_columns={}
        )
        
        # Calculate differences
        differences = calculator.calculate_differences(aligned_data)
        
        assert 'column_differences' in differences, "Should have column_differences"
        assert 'aggregates' in differences, "Should have aggregates"
        assert 'trends' in differences, "Should have trends"
        
        print(f"✓ Basic difference calculation works")
        return True
        
    except Exception as e:
        print(f"✗ Basic difference calculation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("Comparison Engine Basic Tests")
    print("=" * 70)
    
    all_passed = True
    
    if not test_imports():
        all_passed = False
    
    if not test_instantiation():
        all_passed = False
    
    if not test_basic_alignment():
        all_passed = False
    
    if not test_basic_difference_calculation():
        all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
