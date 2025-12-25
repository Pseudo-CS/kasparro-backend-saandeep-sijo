"""Schema drift detection service with fuzzy matching and confidence scoring."""
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from core.models import SchemaDriftLog
from core.database import get_db
from services.etl_utils import utc_now

logger = logging.getLogger(__name__)


class SchemaDriftDetector:
    """Detects schema changes using fuzzy matching and confidence scoring."""
    
    def __init__(self, db: Session, source_name: str):
        self.db = db
        self.source_name = source_name
        self.expected_schema: Optional[Dict[str, type]] = None
        self.field_history: Dict[str, List[str]] = {}  # field -> [seen values types]
        
    def set_expected_schema(self, schema: Dict[str, type]):
        """Set the expected schema for comparison."""
        self.expected_schema = schema
        logger.info(f"[{self.source_name}] Expected schema set with {len(schema)} fields")
        
    def detect_drift(
        self, 
        actual_data: Dict[str, Any],
        record_id: str
    ) -> Dict[str, Any]:
        """
        Detect schema drift in a data record.
        
        Returns:
            dict with keys:
                - has_drift: bool
                - confidence: float (0-1)
                - missing_fields: list
                - extra_fields: list
                - type_mismatches: list of dicts
                - fuzzy_matches: list of dicts with field suggestions
        """
        if not self.expected_schema:
            logger.warning(f"[{self.source_name}] No expected schema set, cannot detect drift")
            return {
                "has_drift": False,
                "confidence": 0.0,
                "missing_fields": [],
                "extra_fields": [],
                "type_mismatches": [],
                "fuzzy_matches": []
            }
            
        expected_fields = set(self.expected_schema.keys())
        actual_fields = set(actual_data.keys())
        
        # Find missing and extra fields
        missing_fields = list(expected_fields - actual_fields)
        extra_fields = list(actual_fields - expected_fields)
        
        # Type mismatches
        type_mismatches = []
        for field in expected_fields & actual_fields:
            expected_type = self.expected_schema[field]
            actual_value = actual_data[field]
            
            # Skip None values
            if actual_value is None:
                continue
                
            actual_type = type(actual_value)
            
            # Allow some flexibility (e.g., int can be float)
            if not self._types_compatible(expected_type, actual_type):
                type_mismatches.append({
                    "field": field,
                    "expected_type": expected_type.__name__,
                    "actual_type": actual_type.__name__,
                    "value": str(actual_value)[:50]  # Truncate long values
                })
        
        # Fuzzy matching for missing fields
        fuzzy_matches = []
        for missing_field in missing_fields:
            best_match = self._find_fuzzy_match(missing_field, extra_fields)
            if best_match:
                fuzzy_matches.append(best_match)
        
        # Calculate confidence score
        has_drift = bool(missing_fields or extra_fields or type_mismatches)
        confidence = self._calculate_confidence(
            len(expected_fields),
            len(missing_fields),
            len(extra_fields),
            len(type_mismatches)
        )
        
        result = {
            "has_drift": has_drift,
            "confidence": confidence,
            "missing_fields": missing_fields,
            "extra_fields": extra_fields,
            "type_mismatches": type_mismatches,
            "fuzzy_matches": fuzzy_matches
        }
        
        # Log if drift detected
        if has_drift:
            self._log_drift(record_id, result)
            
        return result
    
    def _types_compatible(self, expected: type, actual: type) -> bool:
        """Check if two types are compatible."""
        # Exact match
        if expected == actual:
            return True
            
        # Allow int/float compatibility
        if expected in (int, float) and actual in (int, float):
            return True
            
        # Allow str for most types (string representation)
        if expected == str:
            return True
            
        return False
    
    def _find_fuzzy_match(
        self, 
        missing_field: str, 
        extra_fields: List[str],
        threshold: float = 0.6
    ) -> Optional[Dict[str, Any]]:
        """Find fuzzy matches for missing fields in extra fields."""
        best_match = None
        best_ratio = threshold
        
        for extra_field in extra_fields:
            ratio = SequenceMatcher(None, missing_field, extra_field).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = {
                    "missing_field": missing_field,
                    "suggested_field": extra_field,
                    "similarity": round(ratio, 3)
                }
        
        return best_match
    
    def _calculate_confidence(
        self,
        total_fields: int,
        missing_count: int,
        extra_count: int,
        type_mismatch_count: int
    ) -> float:
        """
        Calculate confidence score (0-1) for drift detection.
        Higher score = more confident there is drift.
        """
        if total_fields == 0:
            return 0.0
            
        # Weights for different drift types
        missing_weight = 0.4
        extra_weight = 0.3
        type_weight = 0.3
        
        missing_score = min(1.0, (missing_count / total_fields) * 2)
        extra_score = min(1.0, (extra_count / total_fields) * 2)
        type_score = min(1.0, (type_mismatch_count / total_fields) * 2)
        
        confidence = (
            missing_score * missing_weight +
            extra_score * extra_weight +
            type_score * type_weight
        )
        
        return round(confidence, 3)
    
    def _log_drift(self, record_id: str, drift_result: Dict[str, Any]):
        """Log schema drift to database and logger."""
        log_level = "WARNING" if drift_result["confidence"] > 0.5 else "INFO"
        
        message = (
            f"[{self.source_name}] Schema drift detected for record {record_id} "
            f"(confidence: {drift_result['confidence']})"
        )
        
        if drift_result["missing_fields"]:
            message += f" | Missing: {', '.join(drift_result['missing_fields'])}"
        if drift_result["extra_fields"]:
            message += f" | Extra: {', '.join(drift_result['extra_fields'])}"
        if drift_result["type_mismatches"]:
            message += f" | Type mismatches: {len(drift_result['type_mismatches'])}"
        if drift_result["fuzzy_matches"]:
            suggestions = [
                f"{m['missing_field']}→{m['suggested_field']}({m['similarity']})"
                for m in drift_result["fuzzy_matches"]
            ]
            message += f" | Suggestions: {', '.join(suggestions)}"
        
        if log_level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)
        
        # Save to database
        try:
            drift_log = SchemaDriftLog(
                source_name=self.source_name,
                record_id=record_id,
                confidence_score=drift_result["confidence"],
                missing_fields=drift_result["missing_fields"],
                extra_fields=drift_result["extra_fields"],
                type_mismatches=[str(m) for m in drift_result["type_mismatches"]],
                fuzzy_suggestions=[str(m) for m in drift_result["fuzzy_matches"]],
                detected_at=utc_now()
            )
            self.db.add(drift_log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to save schema drift log: {e}")
            self.db.rollback()


def get_schema_detector(db: Session, source_name: str) -> SchemaDriftDetector:
    """Factory function to create schema drift detector."""
    return SchemaDriftDetector(db, source_name)
