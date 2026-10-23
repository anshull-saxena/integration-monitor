import yaml
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.validation.rules import ValidationRule, ValidationViolation

logger = logging.getLogger(__name__)


class ValidationEngine:
    """Evaluates YAML-defined data quality & integration integrity checks on PostgreSQL warehouse."""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.rules: List[ValidationRule] = self._load_rules()

    def _load_rules(self) -> List[ValidationRule]:
        with open(self.config_path, "r") as f:
            data = yaml.safe_load(f)
        rules = [ValidationRule(**r) for r in data.get("rules", [])]
        logger.info(f"Loaded {len(rules)} validation rules from {self.config_path}")
        return rules

    def run_all_checks(self, session: Session) -> List[ValidationViolation]:
        """Runs all loaded rules and returns a list of detected violations."""
        violations: List[ValidationViolation] = []
        for rule in self.rules:
            try:
                violation = self._evaluate_rule(session, rule)
                if violation:
                    violations.append(violation)
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.id} ({rule.name}): {e}", exc_info=True)
        return violations

    def _evaluate_rule(self, session: Session, rule: ValidationRule) -> Optional[ValidationViolation]:
        if rule.category in ("schema_and_type", "null_and_required") and rule.condition:
            return self._eval_condition_rule(session, rule)
        elif rule.category == "referential_integrity":
            return self._eval_referential_integrity(session, rule)
        elif rule.category == "cross_system_reconciliation":
            return self._eval_cross_system_rule(session, rule)
        elif rule.category == "duplicate_detection":
            return self._eval_duplicate_rule(session, rule)
        elif rule.category == "freshness_and_volume":
            return self._eval_anomaly_rule(session, rule)
        return None

    def _eval_condition_rule(self, session: Session, rule: ValidationRule) -> Optional[ValidationViolation]:
        query = text(f"SELECT * FROM {rule.target_table} WHERE {rule.condition}")
        rows = session.execute(query).mappings().all()
        if not rows:
            return None

        sample_records = [dict(r) for r in rows[:5]]
        id_col = f"{rule.target_table[:-1]}_id" if rule.target_table.endswith("s") else "id"
        affected_ids = [str(r.get(id_col) or r.get("id")) for r in rows if r.get(id_col) or r.get("id")]

        return ValidationViolation(
            rule_id=rule.id,
            rule_name=rule.name,
            category=rule.category,
            severity=rule.severity,
            description=rule.description,
            violation_count=len(rows),
            affected_ids=affected_ids[:50],
            sample_records=sample_records,
        )

    def _eval_referential_integrity(self, session: Session, rule: ValidationRule) -> Optional[ValidationViolation]:
        query = text(
            f"SELECT t.* FROM {rule.target_table} t "
            f"LEFT JOIN {rule.foreign_table} f ON t.{rule.foreign_key} = f.{rule.primary_key} "
            f"WHERE f.{rule.primary_key} IS NULL"
        )
        rows = session.execute(query).mappings().all()
        if not rows:
            return None

        sample_records = [dict(r) for r in rows[:5]]
        id_col = f"{rule.target_table[:-1]}_id" if rule.target_table.endswith("s") else "id"
        affected_ids = [str(r.get(id_col) or r.get("id")) for r in rows if r.get(id_col) or r.get("id")]

        return ValidationViolation(
            rule_id=rule.id,
            rule_name=rule.name,
            category=rule.category,
            severity=rule.severity,
            description=rule.description,
            violation_count=len(rows),
            affected_ids=affected_ids[:50],
            sample_records=sample_records,
        )

    def _eval_cross_system_rule(self, session: Session, rule: ValidationRule) -> Optional[ValidationViolation]:
        query = text(
            f"SELECT {rule.table_a}.*, {rule.table_b}.* FROM {rule.table_a} "
            f"JOIN {rule.table_b} ON {rule.table_a}.{rule.join_key_a} = {rule.table_b}.{rule.join_key_b} "
            f"WHERE {rule.condition}"
        )
        rows = session.execute(query).mappings().all()
        if not rows:
            return None

        sample_records = [dict(r) for r in rows[:5]]
        id_col = f"{rule.table_a[:-1]}_id" if rule.table_a.endswith("s") else "id"
        affected_ids = [str(r.get(id_col) or r.get("id")) for r in rows if r.get(id_col) or r.get("id")]

        return ValidationViolation(
            rule_id=rule.id,
            rule_name=rule.name,
            category=rule.category,
            severity=rule.severity,
            description=rule.description,
            violation_count=len(rows),
            affected_ids=affected_ids[:50],
            sample_records=sample_records,
        )

    def _eval_duplicate_rule(self, session: Session, rule: ValidationRule) -> Optional[ValidationViolation]:
        cols = ", ".join(rule.key_columns)
        query = text(
            f"SELECT {cols}, COUNT(*) as dup_count FROM {rule.target_table} "
            f"GROUP BY {cols} HAVING COUNT(*) > 1"
        )
        rows = session.execute(query).mappings().all()
        if not rows:
            return None

        sample_records = [dict(r) for r in rows[:5]]
        affected_ids = [str(r.get(rule.key_columns[0])) for r in rows]

        return ValidationViolation(
            rule_id=rule.id,
            rule_name=rule.name,
            category=rule.category,
            severity=rule.severity,
            description=rule.description,
            violation_count=len(rows),
            affected_ids=affected_ids[:50],
            sample_records=sample_records,
        )

    def _eval_anomaly_rule(self, session: Session, rule: ValidationRule) -> Optional[ValidationViolation]:
        if rule.rule_type == "freshness":
            cutoff = datetime.utcnow() - timedelta(days=rule.max_staleness_days or 30)
            query = text(
                f"SELECT * FROM {rule.target_table} "
                f"WHERE {rule.timestamp_column} < :cutoff"
            )
            rows = session.execute(query, {"cutoff": cutoff}).mappings().all()
            if not rows:
                return None
            sample_records = [dict(r) for r in rows[:5]]
            id_col = f"{rule.target_table[:-1]}_id" if rule.target_table.endswith("s") else "id"
            affected_ids = [str(r.get(id_col) or r.get("id")) for r in rows if r.get(id_col) or r.get("id")]
            return ValidationViolation(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                severity=rule.severity,
                description=rule.description,
                violation_count=len(rows),
                affected_ids=affected_ids[:50],
                sample_records=sample_records,
            )

        elif rule.rule_type == "volume_drop":
            count_query = text(f"SELECT COUNT(*) as total FROM {rule.target_table}")
            cnt = session.execute(count_query).scalar()
            if cnt < (rule.min_expected_count or 1):
                return ValidationViolation(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    category=rule.category,
                    severity=rule.severity,
                    description=f"{rule.description} (Found {cnt} rows, expected >= {rule.min_expected_count})",
                    violation_count=1,
                    affected_ids=[],
                    sample_records=[{"table": rule.target_table, "count": cnt, "expected_min": rule.min_expected_count}],
                )
        return None
