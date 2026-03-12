"""
Unit Awareness Service for Intelligence Module

Detects and handles units and currencies in Excel data:
- Detects unit information ($, €, %, kg, miles, etc.)
- Performs unit-aware aggregations
- Warns on unit mismatches in comparisons
- Includes units in numeric answers

Supports Requirements 34.1, 34.2, 34.3, 34.4.
"""

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


class UnitCategory(str, Enum):
    """Category of unit types."""
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    WEIGHT = "weight"
    LENGTH = "length"
    VOLUME = "volume"
    AREA = "area"
    TIME = "time"
    TEMPERATURE = "temperature"
    COUNT = "count"
    UNKNOWN = "unknown"


@dataclass
class UnitDefinition:
    """Definition of a unit type."""
    symbol: str
    name: str
    category: UnitCategory
    aliases: list[str] = field(default_factory=list)
    conversion_factor: float = 1.0
    base_unit: Optional[str] = None


@dataclass
class UnitAwarenessConfig:
    """
    Configuration for UnitAwarenessService.
    
    Attributes:
        strict_mode: If True, raise errors on unit mismatches.
        default_currency: Default currency symbol when none detected.
        decimal_places: Number of decimal places for formatted output.
        warn_on_mismatch: Whether to log warnings on unit mismatches.
    """
    strict_mode: bool = False
    default_currency: str = "$"
    decimal_places: int = 2
    warn_on_mismatch: bool = True


@dataclass
class DetectedUnit:
    """
    Result of unit detection.
    
    Attributes:
        value: The numeric value extracted.
        unit: The unit symbol detected.
        category: Category of the unit.
        original_text: Original text that was parsed.
        confidence: Confidence in the detection (0.0 to 1.0).
        formatted: Formatted string with unit.
    """
    value: Decimal
    unit: str
    category: UnitCategory
    original_text: str
    confidence: float
    formatted: str
    
    def __post_init__(self) -> None:
        """Validate detected unit."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")


@dataclass
class AggregationResult:
    """
    Result of a unit-aware aggregation.
    
    Attributes:
        value: The aggregated value.
        unit: The unit of the result.
        category: Category of the unit.
        count: Number of values aggregated.
        warnings: Any warnings generated during aggregation.
    """
    value: Decimal
    unit: str
    category: UnitCategory
    count: int
    warnings: list[str] = field(default_factory=list)
    
    def format(self, decimal_places: int = 2) -> str:
        """Format the result with unit."""
        if self.category == UnitCategory.CURRENCY:
            return f"{self.unit}{self.value:,.{decimal_places}f}"
        elif self.category == UnitCategory.PERCENTAGE:
            return f"{self.value:.{decimal_places}f}{self.unit}"
        else:
            return f"{self.value:,.{decimal_places}f} {self.unit}"



class UnitAwarenessService:
    """
    Service for detecting and handling units in Excel data.
    
    Provides unit detection, unit-aware aggregations, and mismatch warnings.
    All dependencies are injected via constructor following DIP.
    
    Supports Requirements 34.1, 34.2, 34.3, 34.4.
    """
    
    # Currency patterns (prefix currencies)
    CURRENCY_PATTERNS: list[dict[str, Any]] = [
        {"symbol": "$", "pattern": r"\$\s*([\d,]+\.?\d*)", "name": "USD", "position": "prefix"},
        {"symbol": "€", "pattern": r"€\s*([\d,]+\.?\d*)", "name": "EUR", "position": "prefix"},
        {"symbol": "£", "pattern": r"£\s*([\d,]+\.?\d*)", "name": "GBP", "position": "prefix"},
        {"symbol": "¥", "pattern": r"¥\s*([\d,]+\.?\d*)", "name": "JPY", "position": "prefix"},
        {"symbol": "₹", "pattern": r"₹\s*([\d,]+\.?\d*)", "name": "INR", "position": "prefix"},
        {"symbol": "CHF", "pattern": r"CHF\s*([\d,]+\.?\d*)", "name": "CHF", "position": "prefix"},
        {"symbol": "CAD", "pattern": r"CAD\s*([\d,]+\.?\d*)", "name": "CAD", "position": "prefix"},
        {"symbol": "AUD", "pattern": r"AUD\s*([\d,]+\.?\d*)", "name": "AUD", "position": "prefix"},
    ]
    
    # Suffix currency patterns
    SUFFIX_CURRENCY_PATTERNS: list[dict[str, Any]] = [
        {"symbol": "USD", "pattern": r"([\d,]+\.?\d*)\s*USD", "name": "USD"},
        {"symbol": "EUR", "pattern": r"([\d,]+\.?\d*)\s*EUR", "name": "EUR"},
        {"symbol": "GBP", "pattern": r"([\d,]+\.?\d*)\s*GBP", "name": "GBP"},
    ]
    
    # Percentage patterns
    PERCENTAGE_PATTERNS: list[dict[str, Any]] = [
        {"symbol": "%", "pattern": r"([\d,]+\.?\d*)\s*%", "name": "percent"},
        {"symbol": "pct", "pattern": r"([\d,]+\.?\d*)\s*pct", "name": "percent"},
        {"symbol": "percent", "pattern": r"([\d,]+\.?\d*)\s*percent", "name": "percent"},
    ]
    
    # Weight unit patterns
    WEIGHT_PATTERNS: list[dict[str, Any]] = [
        {"symbol": "kg", "pattern": r"([\d,]+\.?\d*)\s*kg\b", "name": "kilogram", "base": "kg", "factor": 1.0},
        {"symbol": "g", "pattern": r"([\d,]+\.?\d*)\s*g\b", "name": "gram", "base": "kg", "factor": 0.001},
        {"symbol": "mg", "pattern": r"([\d,]+\.?\d*)\s*mg\b", "name": "milligram", "base": "kg", "factor": 0.000001},
        {"symbol": "lb", "pattern": r"([\d,]+\.?\d*)\s*(?:lb|lbs)\b", "name": "pound", "base": "kg", "factor": 0.453592},
        {"symbol": "oz", "pattern": r"([\d,]+\.?\d*)\s*oz\b", "name": "ounce", "base": "kg", "factor": 0.0283495},
        {"symbol": "ton", "pattern": r"([\d,]+\.?\d*)\s*(?:ton|tons)\b", "name": "ton", "base": "kg", "factor": 907.185},
    ]
    
    # Length unit patterns
    LENGTH_PATTERNS: list[dict[str, Any]] = [
        {"symbol": "m", "pattern": r"([\d,]+\.?\d*)\s*m\b", "name": "meter", "base": "m", "factor": 1.0},
        {"symbol": "km", "pattern": r"([\d,]+\.?\d*)\s*km\b", "name": "kilometer", "base": "m", "factor": 1000.0},
        {"symbol": "cm", "pattern": r"([\d,]+\.?\d*)\s*cm\b", "name": "centimeter", "base": "m", "factor": 0.01},
        {"symbol": "mm", "pattern": r"([\d,]+\.?\d*)\s*mm\b", "name": "millimeter", "base": "m", "factor": 0.001},
        {"symbol": "mi", "pattern": r"([\d,]+\.?\d*)\s*(?:mi|miles?)\b", "name": "mile", "base": "m", "factor": 1609.34},
        {"symbol": "ft", "pattern": r"([\d,]+\.?\d*)\s*(?:ft|feet|foot)\b", "name": "foot", "base": "m", "factor": 0.3048},
        {"symbol": "in", "pattern": r"([\d,]+\.?\d*)\s*(?:in|inch|inches)\b", "name": "inch", "base": "m", "factor": 0.0254},
        {"symbol": "yd", "pattern": r"([\d,]+\.?\d*)\s*(?:yd|yards?)\b", "name": "yard", "base": "m", "factor": 0.9144},
    ]
    
    # Volume unit patterns
    VOLUME_PATTERNS: list[dict[str, Any]] = [
        {"symbol": "L", "pattern": r"([\d,]+\.?\d*)\s*(?:L|liters?|litres?)\b", "name": "liter", "base": "L", "factor": 1.0},
        {"symbol": "mL", "pattern": r"([\d,]+\.?\d*)\s*(?:mL|ml)\b", "name": "milliliter", "base": "L", "factor": 0.001},
        {"symbol": "gal", "pattern": r"([\d,]+\.?\d*)\s*(?:gal|gallons?)\b", "name": "gallon", "base": "L", "factor": 3.78541},
    ]
    
    # Area unit patterns
    AREA_PATTERNS: list[dict[str, Any]] = [
        {"symbol": "m²", "pattern": r"([\d,]+\.?\d*)\s*(?:m²|sq\s*m|sqm)\b", "name": "square meter", "base": "m²", "factor": 1.0},
        {"symbol": "km²", "pattern": r"([\d,]+\.?\d*)\s*(?:km²|sq\s*km)\b", "name": "square kilometer", "base": "m²", "factor": 1000000.0},
        {"symbol": "ft²", "pattern": r"([\d,]+\.?\d*)\s*(?:ft²|sq\s*ft|sqft)\b", "name": "square foot", "base": "m²", "factor": 0.092903},
        {"symbol": "acre", "pattern": r"([\d,]+\.?\d*)\s*acres?\b", "name": "acre", "base": "m²", "factor": 4046.86},
    ]
    
    def __init__(self, config: Optional[UnitAwarenessConfig] = None) -> None:
        """
        Initialize UnitAwarenessService with configuration.
        
        Args:
            config: Service configuration. Uses defaults if not provided.
        """
        self._config = config or UnitAwarenessConfig()
        self._unit_registry = self._build_unit_registry()
        logger.info("UnitAwarenessService initialized")
    
    def _build_unit_registry(self) -> dict[str, UnitDefinition]:
        """Build the unit registry from patterns."""
        registry: dict[str, UnitDefinition] = {}
        
        # Register currencies
        for p in self.CURRENCY_PATTERNS:
            registry[p["symbol"]] = UnitDefinition(
                symbol=p["symbol"],
                name=p["name"],
                category=UnitCategory.CURRENCY,
            )
        
        # Register percentages
        registry["%"] = UnitDefinition(
            symbol="%",
            name="percent",
            category=UnitCategory.PERCENTAGE,
        )
        
        # Register weights
        for p in self.WEIGHT_PATTERNS:
            registry[p["symbol"]] = UnitDefinition(
                symbol=p["symbol"],
                name=p["name"],
                category=UnitCategory.WEIGHT,
                conversion_factor=p["factor"],
                base_unit=p["base"],
            )
        
        # Register lengths
        for p in self.LENGTH_PATTERNS:
            registry[p["symbol"]] = UnitDefinition(
                symbol=p["symbol"],
                name=p["name"],
                category=UnitCategory.LENGTH,
                conversion_factor=p["factor"],
                base_unit=p["base"],
            )
        
        # Register volumes
        for p in self.VOLUME_PATTERNS:
            registry[p["symbol"]] = UnitDefinition(
                symbol=p["symbol"],
                name=p["name"],
                category=UnitCategory.VOLUME,
                conversion_factor=p["factor"],
                base_unit=p["base"],
            )
        
        # Register areas
        for p in self.AREA_PATTERNS:
            registry[p["symbol"]] = UnitDefinition(
                symbol=p["symbol"],
                name=p["name"],
                category=UnitCategory.AREA,
                conversion_factor=p["factor"],
                base_unit=p["base"],
            )
        
        return registry
    
    def detect_unit(self, text: str) -> Optional[DetectedUnit]:
        """
        Detect unit and extract numeric value from text.
        
        Args:
            text: Text to analyze for units.
        
        Returns:
            DetectedUnit if a unit is found, None otherwise.
        """
        if not text or not text.strip():
            return None
        
        text = text.strip()
        
        # Try currency patterns first (highest priority)
        for pattern_info in self.CURRENCY_PATTERNS:
            match = re.search(pattern_info["pattern"], text, re.IGNORECASE)
            if match:
                try:
                    value = self._parse_number(match.group(1))
                    return DetectedUnit(
                        value=value,
                        unit=pattern_info["symbol"],
                        category=UnitCategory.CURRENCY,
                        original_text=text,
                        confidence=0.95,
                        formatted=f"{pattern_info['symbol']}{value:,.{self._config.decimal_places}f}",
                    )
                except (ValueError, InvalidOperation):
                    continue
        
        # Try suffix currency patterns
        for pattern_info in self.SUFFIX_CURRENCY_PATTERNS:
            match = re.search(pattern_info["pattern"], text, re.IGNORECASE)
            if match:
                try:
                    value = self._parse_number(match.group(1))
                    return DetectedUnit(
                        value=value,
                        unit=pattern_info["symbol"],
                        category=UnitCategory.CURRENCY,
                        original_text=text,
                        confidence=0.90,
                        formatted=f"{value:,.{self._config.decimal_places}f} {pattern_info['symbol']}",
                    )
                except (ValueError, InvalidOperation):
                    continue
        
        # Try percentage patterns
        for pattern_info in self.PERCENTAGE_PATTERNS:
            match = re.search(pattern_info["pattern"], text, re.IGNORECASE)
            if match:
                try:
                    value = self._parse_number(match.group(1))
                    return DetectedUnit(
                        value=value,
                        unit="%",
                        category=UnitCategory.PERCENTAGE,
                        original_text=text,
                        confidence=0.95,
                        formatted=f"{value:.{self._config.decimal_places}f}%",
                    )
                except (ValueError, InvalidOperation):
                    continue
        
        # Try other unit patterns
        all_patterns = [
            (self.WEIGHT_PATTERNS, UnitCategory.WEIGHT),
            (self.LENGTH_PATTERNS, UnitCategory.LENGTH),
            (self.VOLUME_PATTERNS, UnitCategory.VOLUME),
            (self.AREA_PATTERNS, UnitCategory.AREA),
        ]
        
        for patterns, category in all_patterns:
            for pattern_info in patterns:
                match = re.search(pattern_info["pattern"], text, re.IGNORECASE)
                if match:
                    try:
                        value = self._parse_number(match.group(1))
                        return DetectedUnit(
                            value=value,
                            unit=pattern_info["symbol"],
                            category=category,
                            original_text=text,
                            confidence=0.90,
                            formatted=f"{value:,.{self._config.decimal_places}f} {pattern_info['symbol']}",
                        )
                    except (ValueError, InvalidOperation):
                        continue
        
        return None
    
    def _parse_number(self, text: str) -> Decimal:
        """Parse a number string to Decimal, handling commas."""
        cleaned = text.replace(",", "").strip()
        return Decimal(cleaned)

    
    def detect_units_in_column(
        self,
        values: list[Any],
    ) -> tuple[Optional[str], UnitCategory, float]:
        """
        Detect the predominant unit in a column of values.
        
        Args:
            values: List of cell values to analyze.
        
        Returns:
            Tuple of (unit_symbol, category, confidence).
        """
        if not values:
            return None, UnitCategory.UNKNOWN, 0.0
        
        unit_counts: dict[str, int] = {}
        category_counts: dict[UnitCategory, int] = {}
        total_detected = 0
        
        for value in values:
            if value is None:
                continue
            
            detected = self.detect_unit(str(value))
            if detected:
                total_detected += 1
                unit_counts[detected.unit] = unit_counts.get(detected.unit, 0) + 1
                category_counts[detected.category] = category_counts.get(detected.category, 0) + 1
        
        if not unit_counts:
            return None, UnitCategory.UNKNOWN, 0.0
        
        # Find most common unit
        most_common_unit = max(unit_counts, key=unit_counts.get)
        most_common_category = max(category_counts, key=category_counts.get)
        
        # Calculate confidence based on consistency
        confidence = unit_counts[most_common_unit] / total_detected if total_detected > 0 else 0.0
        
        return most_common_unit, most_common_category, confidence
    
    def aggregate_with_units(
        self,
        values: list[Any],
        operation: str = "sum",
    ) -> AggregationResult:
        """
        Perform unit-aware aggregation on values.
        
        Args:
            values: List of values to aggregate.
            operation: Aggregation operation (sum, average, min, max, count).
        
        Returns:
            AggregationResult with value, unit, and any warnings.
        
        Raises:
            ValueError: If operation is not supported.
        """
        valid_operations = {"sum", "average", "avg", "min", "max", "count"}
        if operation.lower() not in valid_operations:
            raise ValueError(f"Operation must be one of {valid_operations}, got '{operation}'")
        
        warnings: list[str] = []
        detected_values: list[tuple[Decimal, str, UnitCategory]] = []
        
        for value in values:
            if value is None:
                continue
            
            detected = self.detect_unit(str(value))
            if detected:
                detected_values.append((detected.value, detected.unit, detected.category))
            else:
                # Try to parse as plain number
                try:
                    num_value = self._parse_number(str(value))
                    detected_values.append((num_value, "", UnitCategory.UNKNOWN))
                except (ValueError, InvalidOperation):
                    warnings.append(f"Could not parse value: {value}")
        
        if not detected_values:
            return AggregationResult(
                value=Decimal(0),
                unit="",
                category=UnitCategory.UNKNOWN,
                count=0,
                warnings=["No valid numeric values found"],
            )
        
        # Check for unit consistency
        units = set(v[1] for v in detected_values if v[1])
        categories = set(v[2] for v in detected_values if v[2] != UnitCategory.UNKNOWN)
        
        if len(units) > 1:
            warning_msg = f"Mixed units detected: {units}. Results may be inaccurate."
            warnings.append(warning_msg)
            if self._config.warn_on_mismatch:
                logger.warning(warning_msg)
        
        if len(categories) > 1:
            warning_msg = f"Mixed unit categories detected: {categories}. Results may be inaccurate."
            warnings.append(warning_msg)
            if self._config.warn_on_mismatch:
                logger.warning(warning_msg)
        
        # Determine result unit
        result_unit = ""
        result_category = UnitCategory.UNKNOWN
        
        if units:
            result_unit = next(iter(units))
            if result_unit in self._unit_registry:
                result_category = self._unit_registry[result_unit].category
        elif categories:
            result_category = next(iter(categories))
        
        # Perform aggregation
        numeric_values = [v[0] for v in detected_values]
        
        op = operation.lower()
        if op == "sum":
            result_value = sum(numeric_values, Decimal(0))
        elif op in ("average", "avg"):
            result_value = sum(numeric_values, Decimal(0)) / len(numeric_values)
        elif op == "min":
            result_value = min(numeric_values)
        elif op == "max":
            result_value = max(numeric_values)
        elif op == "count":
            result_value = Decimal(len(numeric_values))
            result_unit = ""
            result_category = UnitCategory.COUNT
        else:
            result_value = Decimal(0)
        
        return AggregationResult(
            value=result_value,
            unit=result_unit,
            category=result_category,
            count=len(numeric_values),
            warnings=warnings,
        )
    
    def check_unit_compatibility(
        self,
        unit1: str,
        unit2: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if two units are compatible for comparison/aggregation.
        
        Args:
            unit1: First unit symbol.
            unit2: Second unit symbol.
        
        Returns:
            Tuple of (is_compatible, warning_message).
        """
        if not unit1 or not unit2:
            return True, None
        
        if unit1 == unit2:
            return True, None
        
        # Check if same category
        def1 = self._unit_registry.get(unit1)
        def2 = self._unit_registry.get(unit2)
        
        if not def1 or not def2:
            return False, f"Unknown unit(s): {unit1 if not def1 else ''} {unit2 if not def2 else ''}".strip()
        
        if def1.category != def2.category:
            return False, f"Incompatible unit categories: {def1.category.value} vs {def2.category.value}"
        
        # Same category but different units - compatible with conversion
        return True, f"Units {unit1} and {unit2} are compatible but may require conversion"
    
    def convert_unit(
        self,
        value: Decimal,
        from_unit: str,
        to_unit: str,
    ) -> Optional[Decimal]:
        """
        Convert a value from one unit to another.
        
        Args:
            value: The numeric value to convert.
            from_unit: Source unit symbol.
            to_unit: Target unit symbol.
        
        Returns:
            Converted value, or None if conversion not possible.
        """
        if from_unit == to_unit:
            return value
        
        from_def = self._unit_registry.get(from_unit)
        to_def = self._unit_registry.get(to_unit)
        
        if not from_def or not to_def:
            logger.warning(f"Cannot convert: unknown unit(s) {from_unit}, {to_unit}")
            return None
        
        if from_def.category != to_def.category:
            logger.warning(f"Cannot convert between different categories: {from_def.category} to {to_def.category}")
            return None
        
        if from_def.base_unit != to_def.base_unit:
            logger.warning(f"Cannot convert: different base units")
            return None
        
        # Convert to base unit, then to target
        base_value = value * Decimal(str(from_def.conversion_factor))
        result = base_value / Decimal(str(to_def.conversion_factor))
        
        return result
    
    def format_with_unit(
        self,
        value: Union[int, float, Decimal],
        unit: str,
        decimal_places: Optional[int] = None,
    ) -> str:
        """
        Format a numeric value with its unit.
        
        Args:
            value: The numeric value.
            unit: The unit symbol.
            decimal_places: Number of decimal places (uses config default if None).
        
        Returns:
            Formatted string with unit.
        """
        places = decimal_places if decimal_places is not None else self._config.decimal_places
        
        if not unit:
            return f"{value:,.{places}f}"
        
        unit_def = self._unit_registry.get(unit)
        
        if unit_def and unit_def.category == UnitCategory.CURRENCY:
            return f"{unit}{value:,.{places}f}"
        elif unit_def and unit_def.category == UnitCategory.PERCENTAGE:
            return f"{value:.{places}f}{unit}"
        else:
            return f"{value:,.{places}f} {unit}"
