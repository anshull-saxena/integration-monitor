import json
import logging
from src.llm.base import BaseLLMClient, LLMResponse

logger = logging.getLogger(__name__)


class MockLLMClient(BaseLLMClient):
    """Deterministic Mock LLM client providing accurate, reproducible root causes for tests & evaluation."""

    def generate_explanation(self, prompt: str) -> LLMResponse:
        prompt_lower = prompt.lower()
        if "orders_schema_status_drift" in prompt_lower or "schema_drift" in prompt_lower:
            return LLMResponse(
                root_cause_summary="Upstream schema drift detected: expected status column was omitted or renamed (e.g., status_v2).",
                suggested_fix="Update schema mapping or coordinate upstream service deployment to preserve contract backwards compatibility.",
                raw_response="[MockLLM] Schema drift detected.",
            )
        elif "orders_freshness_check" in prompt_lower or "staleness" in prompt_lower or "late_data" in prompt_lower:
            return LLMResponse(
                root_cause_summary="Late or stale data anomaly: records have timestamps significantly older than the maximum freshness threshold.",
                suggested_fix="Investigate delayed upstream event emission, dead-letter re-delivery queues, or timezone conversion bugs.",
                raw_response="[MockLLM] Late data / freshness breach.",
            )
        elif "orders_volume_drop_check" in prompt_lower or "volume_drop" in prompt_lower or "volume falls below" in prompt_lower:
            if "upstream_http_500" in prompt_lower or "500" in prompt_lower:
                return LLMResponse(
                    root_cause_summary="Upstream 500 outage: orders service experienced internal server errors resulting in uningested batches and zero warehouse volume.",
                    suggested_fix="Inspect upstream orders microservice error logs, check upstream database connections, and review recent API deployments.",
                    raw_response="[MockLLM] Upstream 500 outage leading to volume drop.",
                )
            return LLMResponse(
                root_cause_summary="Data volume anomaly: ingested record count dropped drastically below expected operating volume threshold.",
                suggested_fix="Verify upstream service availability, network connectivity, and check upstream database replication queues.",
                raw_response="[MockLLM] Volume anomaly.",
            )
        elif "orders_supplier_fk" in prompt_lower or "shipments_order_fk" in prompt_lower or "referential_integrity" in prompt_lower:
            return LLMResponse(
                root_cause_summary="Referential integrity failure: ingested entity references an upstream ID (supplier_id or order_id) that does not exist in the warehouse.",
                suggested_fix="Audit upstream entity lifecycle ordering to enforce referential consistency and backfill missing master records.",
                raw_response="[MockLLM] Referential integrity failure.",
            )
        elif "shipment_order_quantity_reconciliation" in prompt_lower or "delivered_shipment_on_cancelled_order" in prompt_lower:
            return LLMResponse(
                root_cause_summary="Cross-system reconciliation mismatch detected: discrepancies found between shipment status/quantity and purchase order records.",
                suggested_fix="Align order cancellation webhooks with dispatch management to prevent deliveries on cancelled orders and reconcile quantities.",
                raw_response="[MockLLM] Cross-system reconciliation mismatch.",
            )
        elif "orders_required_fields" in prompt_lower or "null_and_required" in prompt_lower or "null" in prompt_lower:
            return LLMResponse(
                root_cause_summary="Mandatory fields were emitted with null values, violating schema nullability constraints.",
                suggested_fix="Enforce strict non-null validation at upstream API boundaries and reject payloads missing mandatory business keys.",
                raw_response="[MockLLM] Null constraint violation.",
            )
        elif "orders_amount_type_and_range" in prompt_lower or "negative" in prompt_lower:
            return LLMResponse(
                root_cause_summary="Silent value corruption: numerical values violated valid business domain ranges (e.g., negative order total_amount).",
                suggested_fix="Audit billing calculation logic in upstream orders service to reject negative financial amounts.",
                raw_response="[MockLLM] Silent corruption detected.",
            )
        elif "duplicate" in prompt_lower:
            return LLMResponse(
                root_cause_summary="Duplicate key collision: multiple identical records or primary keys received in a single batch.",
                suggested_fix="Implement upstream publisher deduplication and ensure idempotent consumers.",
                raw_response="[MockLLM] Duplicate key collision.",
            )
        else:
            return LLMResponse(
                root_cause_summary="Integration anomaly observed across upstream REST systems.",
                suggested_fix="Review upstream change logs, contract specifications, and verify schema conformance.",
                raw_response="[MockLLM] Generic anomaly.",
            )


class OpenAILLMClient(BaseLLMClient):
    """Production LLM client calling OpenAI or OpenAI-compatible REST endpoints."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def generate_explanation(self, prompt: str) -> LLMResponse:
        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an automated data platform incident diagnostics assistant. Always output JSON."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        resp = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return LLMResponse(
            root_cause_summary=parsed.get("root_cause_summary", "No summary provided"),
            suggested_fix=parsed.get("suggested_fix", "No fix provided"),
            raw_response=content,
        )
