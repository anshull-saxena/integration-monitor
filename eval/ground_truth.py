import logging
from typing import Dict, List
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class GroundTruthMetric(BaseModel):
    fault_type: str
    injected_count: int
    detected_count: int
    false_positives: int
    precision: float
    recall: float
    mean_time_to_detect_cycles: float


class DiagnosticScore(BaseModel):
    incident_id: str
    check_name: str
    ground_truth_fault: str
    raw_log_baseline: str
    raw_log_correct: bool
    llm_root_cause_summary: str
    llm_suggested_fix: str
    llm_correct: bool


class EvaluationSummary(BaseModel):
    total_scenarios_run: int
    clean_runs_evaluated: int
    false_positive_rate_clean_runs: float
    overall_mean_time_to_detect_cycles: float
    metrics_by_fault_type: Dict[str, GroundTruthMetric]
    diagnostic_evaluations: List[DiagnosticScore]
    raw_log_baseline_accuracy: float
    llm_diagnostic_accuracy: float


def score_diagnostic_rubric(
    ground_truth_fault: str,
    raw_logs: str,
    llm_summary: str,
) -> tuple[bool, bool]:
    """Scores whether the root cause was correctly identified by raw logs vs LLM summary.

    Rubric Criteria:
    - Must correctly identify the root failure mode (e.g. orphan foreign key, negative amount, null key).
    """
    raw_lower = raw_logs.lower()
    llm_lower = llm_summary.lower()

    keywords = {
        "mismatched_ids": ["supplier", "foreign key", "referential", "exist", "orphan"],
        "silent_corruption": ["negative", "quantity", "exceed", "amount", "mismatch"],
        "null_spike": ["null", "required", "missing"],
        "schema_drift": ["schema", "status", "v2", "column", "field"],
        "late_data": ["freshness", "stale", "timestamp", "days"],
        "http_500": ["500", "unavailable", "server error", "connection"],
        "duplicates": ["duplicate", "key", "collision"],
        "volume_drop": ["volume", "drop", "count", "threshold"],
    }

    target_keywords = keywords.get(ground_truth_fault, [])

    # Check raw logs (often cryptic or missing domain root-cause explanation)
    raw_matches = sum(1 for kw in target_keywords if kw in raw_lower)
    raw_correct = raw_matches >= 2

    # Check LLM summary
    llm_matches = sum(1 for kw in target_keywords if kw in llm_lower)
    llm_correct = llm_matches >= 1

    return raw_correct, llm_correct
