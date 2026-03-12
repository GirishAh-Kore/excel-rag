"""
Intelligence Module

Provides intelligent data analysis capabilities for the Excel Query Pipeline:
- DateParser: Natural language date parsing with fiscal year support
- UnitAwarenessService: Unit and currency detection and handling
- AnomalyDetector: Statistical anomaly and outlier detection
- RelationshipDetector: Cross-file relationship detection

These components enhance query processing with domain-specific intelligence.
"""

from src.intelligence.date_parser import DateParser, DateParserConfig, ParsedDateRange
from src.intelligence.unit_awareness import UnitAwarenessService, UnitAwarenessConfig, DetectedUnit
from src.intelligence.anomaly_detector import AnomalyDetector, AnomalyDetectorConfig, DetectedAnomaly
from src.intelligence.relationship_detector import (
    RelationshipDetector,
    RelationshipDetectorConfig,
    DetectedRelationship,
)

__all__ = [
    "DateParser",
    "DateParserConfig",
    "ParsedDateRange",
    "UnitAwarenessService",
    "UnitAwarenessConfig",
    "DetectedUnit",
    "AnomalyDetector",
    "AnomalyDetectorConfig",
    "DetectedAnomaly",
    "RelationshipDetector",
    "RelationshipDetectorConfig",
    "DetectedRelationship",
]
