"""
Preference Manager Module

Manages user file selection preferences for query-based learning.
Stores historical selections and applies preference boost to ranking scores.
"""

import logging
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from Levenshtein import distance as levenshtein_distance

from src.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class PreferenceManager:
    """
    Manages user preferences for file selection.
    
    Features:
    - Store user file selections with query patterns
    - Query historical preferences using fuzzy matching
    - Apply exponential decay based on preference age
    - Clean up old preferences (> 30 days)
    
    Preference scoring:
    - Exact query match: 1.0
    - Similar query (Levenshtein distance): 0.5-1.0
    - Decays exponentially after 30 days
    """
    
    # Fuzzy matching threshold (0-1, lower is more similar)
    FUZZY_MATCH_THRESHOLD = 0.3
    
    # Decay parameters
    DECAY_START_DAYS = 30
    DECAY_HALF_LIFE_DAYS = 60
    
    def __init__(self, db_connection: DatabaseConnection):
        """
        Initialize PreferenceManager.
        
        Args:
            db_connection: Database connection
        """
        self.db_connection = db_connection
        logger.info("PreferenceManager initialized")
    
    def record_preference(
        self,
        query: str,
        file_id: str,
        sheet_name: Optional[str] = None
    ) -> bool:
        """
        Record a user's file selection preference.
        
        Args:
            query: User query that led to selection
            file_id: Selected file ID
            sheet_name: Optional selected sheet name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                
                # Normalize query for storage
                query_pattern = self._normalize_query(query)
                
                cursor.execute(
                    """
                    INSERT INTO user_preferences (
                        query_pattern, selected_file_id, selected_sheet_name, created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        query_pattern,
                        file_id,
                        sheet_name,
                        datetime.now().isoformat()
                    )
                )
                
                conn.commit()
                
                logger.info(
                    f"Recorded preference: query='{query_pattern[:50]}...', "
                    f"file={file_id}"
                )
                return True
                
        except Exception as e:
            logger.error(f"Error recording preference: {e}", exc_info=True)
            return False
    
    def get_preferences(
        self,
        query: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get historical preferences for similar queries.
        
        Uses fuzzy matching (Levenshtein distance) to find similar queries
        and applies exponential decay based on age.
        
        Args:
            query: User query
            max_results: Maximum number of preferences to return
            
        Returns:
            List of preferences with scores
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get all preferences (we'll filter in Python for fuzzy matching)
                cursor.execute(
                    """
                    SELECT 
                        query_pattern,
                        selected_file_id,
                        selected_sheet_name,
                        created_at
                    FROM user_preferences
                    ORDER BY created_at DESC
                    LIMIT 100
                    """
                )
                
                rows = cursor.fetchall()
                
                if not rows:
                    return []
                
                # Normalize query for matching
                query_normalized = self._normalize_query(query)
                
                # Calculate similarity and decay for each preference
                scored_preferences = []
                
                for row in rows:
                    stored_query = row[0]
                    file_id = row[1]
                    sheet_name = row[2]
                    created_at_str = row[3]
                    
                    # Calculate similarity score
                    similarity = self._calculate_similarity(
                        query_normalized,
                        stored_query
                    )
                    
                    # Skip if not similar enough
                    if similarity < (1.0 - self.FUZZY_MATCH_THRESHOLD):
                        continue
                    
                    # Parse created_at
                    created_at = datetime.fromisoformat(created_at_str)
                    
                    # Calculate decay factor
                    decay = self._calculate_decay(created_at)
                    
                    # Final score
                    score = similarity * decay
                    
                    scored_preferences.append({
                        "query_pattern": stored_query,
                        "file_id": file_id,
                        "sheet_name": sheet_name,
                        "created_at": created_at,
                        "similarity": similarity,
                        "decay": decay,
                        "score": score
                    })
                
                # Sort by score descending
                scored_preferences.sort(key=lambda x: x["score"], reverse=True)
                
                # Return top results
                result = scored_preferences[:max_results]
                
                logger.debug(
                    f"Found {len(result)} preferences for query: {query[:50]}..."
                )
                
                return result
                
        except Exception as e:
            logger.error(f"Error getting preferences: {e}", exc_info=True)
            return []
    
    def clear_old_preferences(self, days: int = 90) -> int:
        """
        Clear preferences older than specified days.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of preferences deleted
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                
                cutoff_date = datetime.now() - timedelta(days=days)
                
                cursor.execute(
                    """
                    DELETE FROM user_preferences
                    WHERE created_at < ?
                    """,
                    (cutoff_date.isoformat(),)
                )
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Cleared {deleted_count} old preferences (> {days} days)")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error clearing old preferences: {e}", exc_info=True)
            return 0
    
    def get_preference_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored preferences.
        
        Returns:
            Dictionary with statistics
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                
                # Total preferences
                cursor.execute("SELECT COUNT(*) FROM user_preferences")
                total = cursor.fetchone()[0]
                
                # Preferences by file
                cursor.execute(
                    """
                    SELECT selected_file_id, COUNT(*) as count
                    FROM user_preferences
                    GROUP BY selected_file_id
                    ORDER BY count DESC
                    LIMIT 10
                    """
                )
                top_files = [
                    {"file_id": row[0], "count": row[1]}
                    for row in cursor.fetchall()
                ]
                
                # Recent preferences (last 7 days)
                cutoff = datetime.now() - timedelta(days=7)
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM user_preferences
                    WHERE created_at >= ?
                    """,
                    (cutoff.isoformat(),)
                )
                recent = cursor.fetchone()[0]
                
                return {
                    "total_preferences": total,
                    "recent_preferences": recent,
                    "top_files": top_files
                }
                
        except Exception as e:
            logger.error(f"Error getting preference statistics: {e}")
            return {}
    
    def _normalize_query(self, query: str) -> str:
        """
        Normalize query for storage and matching.
        
        Args:
            query: User query
            
        Returns:
            Normalized query
        """
        # Convert to lowercase
        normalized = query.lower()
        
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        
        # Remove common punctuation
        for char in "?!.,;:":
            normalized = normalized.replace(char, "")
        
        return normalized
    
    def _calculate_similarity(self, query1: str, query2: str) -> float:
        """
        Calculate similarity between two queries using Levenshtein distance.
        
        Args:
            query1: First query
            query2: Second query
            
        Returns:
            Similarity score (0-1, 1 is identical)
        """
        if query1 == query2:
            return 1.0
        
        # Calculate Levenshtein distance
        distance = levenshtein_distance(query1, query2)
        
        # Normalize by max length
        max_len = max(len(query1), len(query2))
        
        if max_len == 0:
            return 0.0
        
        # Convert distance to similarity (0-1)
        similarity = 1.0 - (distance / max_len)
        
        return max(0.0, similarity)
    
    def _calculate_decay(self, created_at: datetime) -> float:
        """
        Calculate exponential decay factor based on preference age.
        
        Preferences decay exponentially after DECAY_START_DAYS:
        - 0-30 days: no decay (factor = 1.0)
        - 30-90 days: exponential decay
        - > 90 days: minimum factor (0.1)
        
        Args:
            created_at: When preference was created
            
        Returns:
            Decay factor (0.1-1.0)
        """
        now = datetime.now()
        
        # Handle timezone-aware datetime
        if created_at.tzinfo is not None:
            from datetime import timezone
            now = now.replace(tzinfo=timezone.utc)
        
        days_old = (now - created_at).days
        
        # No decay for recent preferences
        if days_old <= self.DECAY_START_DAYS:
            return 1.0
        
        # Exponential decay after DECAY_START_DAYS
        days_since_decay_start = days_old - self.DECAY_START_DAYS
        
        # Calculate decay using half-life formula
        # factor = 0.5 ^ (days_since_decay_start / half_life)
        decay_factor = math.pow(0.5, days_since_decay_start / self.DECAY_HALF_LIFE_DAYS)
        
        # Minimum decay factor
        return max(0.1, decay_factor)
