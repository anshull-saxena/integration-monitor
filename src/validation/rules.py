from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class ValidationRule(BaseModel):
    id: str
    name: str
    category: str  # schema_and_type, null_and_required, duplicate_detection, referential_integrity, cross_system_reconciliation, freshness_and_volume
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    description: str

    # Direct query condition rules
    target_table: Optional[str] = None
    condition: Optional[str] = None

    # Duplicate rules
    rule_type: Optional[str] = None  # duplicate, cross_system, freshness, volume_drop
    key_columns: Optional[List[str]] = None

    # Referential integrity rules
    foreign_table: Optional[str] = None
    foreign_key: Optional[str] = None
    primary_key: Optional[str] = None

    # Cross system reconciliation rules
    table_a: Optional[str] = None
    table_b: Optional[str] = None
    join_key_a: Optional[str] = None
    join_key_b: Optional[str] = None

    # Freshness and volume rules
    timestamp_column: Optional[str] = None
    max_staleness_days: Optional[int] = None
    min_expected_count: Optional[int] = None


class ValidationViolation(BaseModel):
    rule_id: str
    rule_name: str
    category: str
    severity: str
    description: str
    violation_count: int
    affected_ids: List[str]
    sample_records: List[Dict[str, Any]]
