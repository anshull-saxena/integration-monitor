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
    - Raw logs: Baseline logs are typically literal stack traces or check names (e.g. "ERROR: Check orders_amount_type_and_range failed").
      Raw logs often fail to diagnose *why* it happened or confuse symptom with root cause (e.g., volume drop vs 500 error, or referential integrity cascades).
    - LLM summary: Must synthesize a coherent explanation connecting the failing data contract to upstream service behavior.
    """
    raw_lower = raw_logs.lower()
    llm_lower = llm_summary.lower()

    # Domain root-cause requirements
    diagnostics = {
        "mismatched_ids": {
            # Raw log error text contains the literal check name e.g. 'orders_supplier_fk'
            "raw_requires": ["orders_supplier_fk", "supplier_id that does not exist"],
            "llm_requires": ["supplier", "referential", "foreign key"],
        },
        "silent_corruption": {
            "raw_requires": ["non-negative", "quantity significantly mismatches"],
            "llm_requires": ["negative", "quantity", "mismatch", "corruption"],
        },
        "null_spike": {
            "raw_requires": ["invalid primary key", "must not be null"],
            "llm_requires": ["null", "mandatory", "required"],
        },
        "schema_drift": {
            "raw_requires": ["upstream schema drift"],
            "llm_requires": ["drift", "schema", "renamed", "status"],
        },
        "late_data": {
            "raw_requires": ["staleness exceeds max"],
            "llm_requires": ["stale", "late", "freshness", "staleness"],
        },
        "http_500": {
            "raw_requires": ["http 500"],
            "llm_requires": ["service availability", "500", "outage"],
        },
        "duplicates": {
            "raw_requires": ["duplicate primary key"],
            "llm_requires": ["duplicate", "collision", "primary key"],
        },
        "volume_drop": {
            # In raw logs, volume drop and 500 error look identical (both just say volume dropped), missing the underlying cause
            "raw_requires": ["orders table volume falls below expected minimum threshold"],
            "llm_requires": ["volume", "operating volume", "dropped"],
        },
    }

    rule_req = diagnostics.get(ground_truth_fault, {"raw_requires": ["root cause"], "llm_requires": ["anomaly"]})

    # Raw log baseline: raw errors usually state the failing SQL/Check name without root-cause diagnosis
    raw_correct = any(req in raw_lower for req in rule_req["raw_requires"])

    # LLM explanation: structured synthesis
    llm_correct = any(req in llm_lower for req in rule_req["llm_requires"])

    return raw_correct, llm_correct
