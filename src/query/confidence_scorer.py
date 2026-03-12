"""
Confidence scoring for query results.

This module calculates confidence scores for answers based on data completeness,
semantic similarity, query ambiguity, and file/sheet selection confidence.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from src.models.domain_models import RetrievedData, RankedFile, SheetSelection


@dataclass
class ConfidenceBreakdown:
    """Detailed breakdown of confidence score components."""
    
    data_completeness_score: float  # 0-1, weight: 40%
    semantic_similarity_score: float  # 0-1, weight: 30%
    query_ambiguity_score: float  # 0-1, weight: 20%
    selection_confidence_score: float  # 0-1, weight: 10%
    
    overall_confidence: float  # 0-1 (0-100 when displayed)
    
    # Explanations
    data_completeness_reason: str
    semantic_similarity_reason: str
    query_ambiguity_reason: str
    selection_confidence_reason: str
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary."""
        return {
            "overall_confidence": self.overall_confidence,
            "confidence_percentage": round(self.overall_confidence * 100, 1),
            "breakdown": {
                "data_completeness": {
                    "score": round(self.data_completeness_score, 2),
                    "weight": 0.40,
                    "reason": self.data_completeness_reason
                },
                "semantic_similarity": {
                    "score": round(self.semantic_similarity_score, 2),
                    "weight": 0.30,
                    "reason": self.semantic_similarity_reason
                },
                "query_ambiguity": {
                    "score": round(self.query_ambiguity_score, 2),
                    "weight": 0.20,
                    "reason": self.query_ambiguity_reason
                },
                "selection_confidence": {
                    "score": round(self.selection_confidence_score, 2),
                    "weight": 0.10,
                    "reason": self.selection_confidence_reason
                }
            }
        }


class ConfidenceScorer:
    """
    Calculates confidence scores for query results.
    
    Combines multiple factors including data completeness, semantic similarity,
    query clarity, and selection confidence to produce an overall confidence score.
    """
    
    # Weights for different components
    WEIGHT_DATA_COMPLETENESS = 0.40
    WEIGHT_SEMANTIC_SIMILARITY = 0.30
    WEIGHT_QUERY_AMBIGUITY = 0.20
    WEIGHT_SELECTION_CONFIDENCE = 0.10
    
    def __init__(self, language: str = "en"):
        """
        Initialize the confidence scorer.
        
        Args:
            language: Language code ('en' or 'th')
        """
        self.language = language
    
    def calculate_confidence(
        self,
        query: str,
        retrieved_data: List[RetrievedData],
        ranked_files: Optional[List[RankedFile]] = None,
        sheet_selection: Optional[SheetSelection] = None,
        expected_data_points: Optional[int] = None,
        query_entities: Optional[List[str]] = None
    ) -> ConfidenceBreakdown:
        """
        Calculate overall confidence score with detailed breakdown.
        
        Args:
            query: The user's query
            retrieved_data: Data retrieved for the answer
            ranked_files: Ranked file candidates
            sheet_selection: Sheet selection result
            expected_data_points: Expected number of data points (if known)
            query_entities: Entities extracted from query
            
        Returns:
            ConfidenceBreakdown with scores and explanations
        """
        # Calculate each component
        data_score, data_reason = self._calculate_data_completeness(
            retrieved_data, expected_data_points
        )
        
        semantic_score, semantic_reason = self._calculate_semantic_similarity(
            ranked_files
        )
        
        ambiguity_score, ambiguity_reason = self._calculate_query_ambiguity(
            query, query_entities, ranked_files
        )
        
        selection_score, selection_reason = self._calculate_selection_confidence(
            ranked_files, sheet_selection
        )
        
        # Calculate weighted overall confidence
        overall = (
            data_score * self.WEIGHT_DATA_COMPLETENESS +
            semantic_score * self.WEIGHT_SEMANTIC_SIMILARITY +
            ambiguity_score * self.WEIGHT_QUERY_AMBIGUITY +
            selection_score * self.WEIGHT_SELECTION_CONFIDENCE
        )
        
        return ConfidenceBreakdown(
            data_completeness_score=data_score,
            semantic_similarity_score=semantic_score,
            query_ambiguity_score=ambiguity_score,
            selection_confidence_score=selection_score,
            overall_confidence=overall,
            data_completeness_reason=data_reason,
            semantic_similarity_reason=semantic_reason,
            query_ambiguity_reason=ambiguity_reason,
            selection_confidence_reason=selection_reason
        )
    
    def _calculate_data_completeness(
        self,
        retrieved_data: List[RetrievedData],
        expected_data_points: Optional[int]
    ) -> Tuple[float, str]:
        """
        Calculate data completeness score (40% weight).
        
        Args:
            retrieved_data: Retrieved data
            expected_data_points: Expected number of data points
            
        Returns:
            Tuple of (score, reason)
        """
        if not retrieved_data:
            if self.language == "th":
                return 0.0, "ไม่พบข้อมูลที่เกี่ยวข้อง"
            return 0.0, "No relevant data found"
        
        # Count actual data points
        actual_data_points = len(retrieved_data)
        
        # If expected is known, compare
        if expected_data_points:
            completeness = min(1.0, actual_data_points / expected_data_points)
            
            if completeness >= 1.0:
                if self.language == "th":
                    reason = f"พบข้อมูลครบถ้วน ({actual_data_points} จุดข้อมูล)"
                else:
                    reason = f"All expected data found ({actual_data_points} data points)"
            elif completeness >= 0.7:
                if self.language == "th":
                    reason = f"พบข้อมูลส่วนใหญ่ ({actual_data_points}/{expected_data_points} จุดข้อมูล)"
                else:
                    reason = f"Most data found ({actual_data_points}/{expected_data_points} data points)"
            else:
                if self.language == "th":
                    reason = f"พบข้อมูลบางส่วน ({actual_data_points}/{expected_data_points} จุดข้อมูล)"
                else:
                    reason = f"Partial data found ({actual_data_points}/{expected_data_points} data points)"
            
            return completeness, reason
        
        # If expected is unknown, use heuristics
        # More data points generally means better completeness
        if actual_data_points >= 5:
            score = 1.0
            if self.language == "th":
                reason = f"พบข้อมูลหลายจุด ({actual_data_points} จุดข้อมูล)"
            else:
                reason = f"Multiple data points found ({actual_data_points} data points)"
        elif actual_data_points >= 3:
            score = 0.8
            if self.language == "th":
                reason = f"พบข้อมูลเพียงพอ ({actual_data_points} จุดข้อมูล)"
            else:
                reason = f"Sufficient data found ({actual_data_points} data points)"
        elif actual_data_points >= 2:
            score = 0.6
            if self.language == "th":
                reason = f"พบข้อมูลจำกัด ({actual_data_points} จุดข้อมูล)"
            else:
                reason = f"Limited data found ({actual_data_points} data points)"
        else:
            score = 0.4
            if self.language == "th":
                reason = "พบข้อมูลเพียงจุดเดียว"
            else:
                reason = "Single data point found"
        
        return score, reason
    
    def _calculate_semantic_similarity(
        self,
        ranked_files: Optional[List[RankedFile]]
    ) -> Tuple[float, str]:
        """
        Calculate semantic similarity score (30% weight).
        
        Args:
            ranked_files: Ranked file candidates
            
        Returns:
            Tuple of (score, reason)
        """
        if not ranked_files:
            if self.language == "th":
                return 0.5, "ไม่มีข้อมูลความคล้ายคลึงทางความหมาย"
            return 0.5, "No semantic similarity data available"
        
        # Use the top file's semantic score
        top_file = ranked_files[0]
        semantic_score = top_file.semantic_score
        
        # Generate reason based on score
        if semantic_score >= 0.9:
            if self.language == "th":
                reason = f"ความคล้ายคลึงสูงมาก ({semantic_score:.2f})"
            else:
                reason = f"Very high semantic similarity ({semantic_score:.2f})"
        elif semantic_score >= 0.75:
            if self.language == "th":
                reason = f"ความคล้ายคลึงสูง ({semantic_score:.2f})"
            else:
                reason = f"High semantic similarity ({semantic_score:.2f})"
        elif semantic_score >= 0.6:
            if self.language == "th":
                reason = f"ความคล้ายคลึงปานกลาง ({semantic_score:.2f})"
            else:
                reason = f"Moderate semantic similarity ({semantic_score:.2f})"
        else:
            if self.language == "th":
                reason = f"ความคล้ายคลึงต่ำ ({semantic_score:.2f})"
            else:
                reason = f"Low semantic similarity ({semantic_score:.2f})"
        
        return semantic_score, reason
    
    def _calculate_query_ambiguity(
        self,
        query: str,
        query_entities: Optional[List[str]],
        ranked_files: Optional[List[RankedFile]]
    ) -> Tuple[float, str]:
        """
        Calculate query ambiguity score (20% weight).
        Higher score means less ambiguous (clearer query).
        
        Args:
            query: The user's query
            query_entities: Entities extracted from query
            ranked_files: Ranked file candidates
            
        Returns:
            Tuple of (score, reason)
        """
        # Start with base score
        score = 0.7
        reasons = []
        
        # Check query length (very short queries are often ambiguous)
        query_words = query.split()
        if len(query_words) < 3:
            score -= 0.2
            if self.language == "th":
                reasons.append("คำถามสั้นเกินไป")
            else:
                reasons.append("Query is very short")
        elif len(query_words) >= 5:
            score += 0.1
            if self.language == "th":
                reasons.append("คำถามมีรายละเอียด")
            else:
                reasons.append("Query is detailed")
        
        # Check for specific entities
        if query_entities and len(query_entities) >= 2:
            score += 0.1
            if self.language == "th":
                reasons.append(f"ระบุเอนทิตีชัดเจน ({len(query_entities)} เอนทิตี)")
            else:
                reasons.append(f"Specific entities mentioned ({len(query_entities)} entities)")
        
        # Check file ranking spread (if top files have similar scores, query is ambiguous)
        if ranked_files and len(ranked_files) >= 2:
            top_score = ranked_files[0].relevance_score
            second_score = ranked_files[1].relevance_score
            score_diff = top_score - second_score
            
            if score_diff >= 0.2:
                score += 0.1
                if self.language == "th":
                    reasons.append("ไฟล์ที่เกี่ยวข้องชัดเจน")
                else:
                    reasons.append("Clear file match")
            elif score_diff < 0.1:
                score -= 0.2
                if self.language == "th":
                    reasons.append("มีไฟล์ที่เป็นไปได้หลายไฟล์")
                else:
                    reasons.append("Multiple possible file matches")
        
        # Clamp score to [0, 1]
        score = max(0.0, min(1.0, score))
        
        # Generate reason
        if not reasons:
            if self.language == "th":
                reason = "คำถามมีความชัดเจนปานกลาง"
            else:
                reason = "Query clarity is moderate"
        else:
            reason = "; ".join(reasons)
        
        return score, reason
    
    def _calculate_selection_confidence(
        self,
        ranked_files: Optional[List[RankedFile]],
        sheet_selection: Optional[SheetSelection]
    ) -> Tuple[float, str]:
        """
        Calculate file/sheet selection confidence (10% weight).
        
        Args:
            ranked_files: Ranked file candidates
            sheet_selection: Sheet selection result
            
        Returns:
            Tuple of (score, reason)
        """
        scores = []
        reasons = []
        
        # File selection confidence
        if ranked_files:
            top_file = ranked_files[0]
            file_score = top_file.relevance_score
            scores.append(file_score)
            
            if file_score >= 0.9:
                if self.language == "th":
                    reasons.append("เลือกไฟล์ได้อย่างมั่นใจ")
                else:
                    reasons.append("High file selection confidence")
            elif file_score >= 0.7:
                if self.language == "th":
                    reasons.append("เลือกไฟล์ได้ดี")
                else:
                    reasons.append("Good file selection confidence")
            else:
                if self.language == "th":
                    reasons.append("เลือกไฟล์ได้ปานกลาง")
                else:
                    reasons.append("Moderate file selection confidence")
        
        # Sheet selection confidence
        if sheet_selection:
            sheet_score = sheet_selection.relevance_score
            scores.append(sheet_score)
            
            if sheet_score >= 0.9:
                if self.language == "th":
                    reasons.append("เลือกชีตได้อย่างมั่นใจ")
                else:
                    reasons.append("High sheet selection confidence")
            elif sheet_score >= 0.7:
                if self.language == "th":
                    reasons.append("เลือกชีตได้ดี")
                else:
                    reasons.append("Good sheet selection confidence")
            else:
                if self.language == "th":
                    reasons.append("เลือกชีตได้ปานกลาง")
                else:
                    reasons.append("Moderate sheet selection confidence")
        
        # Calculate average score
        if scores:
            avg_score = sum(scores) / len(scores)
        else:
            avg_score = 0.5
            if self.language == "th":
                reasons.append("ไม่มีข้อมูลการเลือก")
            else:
                reasons.append("No selection data available")
        
        reason = "; ".join(reasons) if reasons else "N/A"
        
        return avg_score, reason
    
    def format_confidence_explanation(
        self,
        breakdown: ConfidenceBreakdown,
        include_details: bool = True
    ) -> str:
        """
        Format confidence explanation for display.
        
        Args:
            breakdown: Confidence breakdown
            include_details: Whether to include detailed breakdown
            
        Returns:
            Formatted explanation string
        """
        lines = []
        
        # Overall confidence
        confidence_pct = round(breakdown.overall_confidence * 100, 1)
        
        if self.language == "th":
            lines.append(f"**ความมั่นใจ:** {confidence_pct}%")
            
            if confidence_pct >= 90:
                lines.append("(มั่นใจสูงมาก)")
            elif confidence_pct >= 75:
                lines.append("(มั่นใจสูง)")
            elif confidence_pct >= 60:
                lines.append("(มั่นใจปานกลาง)")
            else:
                lines.append("(มั่นใจต่ำ)")
        else:
            lines.append(f"**Confidence:** {confidence_pct}%")
            
            if confidence_pct >= 90:
                lines.append("(Very High)")
            elif confidence_pct >= 75:
                lines.append("(High)")
            elif confidence_pct >= 60:
                lines.append("(Moderate)")
            else:
                lines.append("(Low)")
        
        # Detailed breakdown
        if include_details:
            lines.append("")
            if self.language == "th":
                lines.append("**รายละเอียด:**")
            else:
                lines.append("**Breakdown:**")
            
            components = [
                ("Data Completeness" if self.language == "en" else "ความสมบูรณ์ของข้อมูล",
                 breakdown.data_completeness_score,
                 breakdown.data_completeness_reason),
                ("Semantic Similarity" if self.language == "en" else "ความคล้ายคลึงทางความหมาย",
                 breakdown.semantic_similarity_score,
                 breakdown.semantic_similarity_reason),
                ("Query Clarity" if self.language == "en" else "ความชัดเจนของคำถาม",
                 breakdown.query_ambiguity_score,
                 breakdown.query_ambiguity_reason),
                ("Selection Confidence" if self.language == "en" else "ความมั่นใจในการเลือก",
                 breakdown.selection_confidence_score,
                 breakdown.selection_confidence_reason),
            ]
            
            for name, score, reason in components:
                score_pct = round(score * 100, 1)
                lines.append(f"- {name}: {score_pct}% - {reason}")
        
        return "\n".join(lines)
    
    def get_confidence_level(self, confidence: float) -> str:
        """
        Get confidence level label.
        
        Args:
            confidence: Confidence score (0-1)
            
        Returns:
            Confidence level label
        """
        if confidence >= 0.9:
            return "very_high" if self.language == "en" else "สูงมาก"
        elif confidence >= 0.75:
            return "high" if self.language == "en" else "สูง"
        elif confidence >= 0.6:
            return "moderate" if self.language == "en" else "ปานกลาง"
        elif confidence >= 0.4:
            return "low" if self.language == "en" else "ต่ำ"
        else:
            return "very_low" if self.language == "en" else "ต่ำมาก"
