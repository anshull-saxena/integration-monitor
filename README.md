# Integration Monitor

A production-grade, open-source pipeline that ingests data from multiple mock REST systems into PostgreSQL, continuously monitors and detects data-quality and integration failures, and uses an LLM to produce plain-English root-cause summaries and remediation steps.

---

## 1. Problem Statement
Distributed microservice architectures frequently suffer from silent integration breakdowns:
- **Upstream schema drift** (unannounced payload key changes)
- **Referential integrity gaps** (orders created for nonexistent suppliers, shipments dispatched for phantom orders)
- **Business invariant violations** (shipment quantity vastly exceeding order items count, shipments delivered on cancelled orders)
- **Data staleness & volume drops** (upstream silent failures or batch export truncation)

Traditional integration pipelines either crash completely or silently persist dirty data. **Integration Monitor** continuously ingests from multiple REST services with exponential backoff and cursor pagination, captures unrecoverable payloads in a dead-letter queue (DLQ), executes 6 categories of declarative validation checks in PostgreSQL, and enriches every incident with contextual LLM root-cause diagnosis.

---

## 2. Architecture Diagram

```mermaid
flowchart TD
    subgraph Mock Services [Upstream Mock Systems - FastAPI]
        OS["Orders Service (:8001)"]
        SS["Supplier Service (:8002)"]
        SHS["Shipments Service (:8003)"]
        FI["Fault Injection Controller & Ground Truth Ledger"]
        FI -.-> OS
        FI -.-> SS
        FI -.-> SHS
    end

    subgraph Pipeline [Integration Monitor Pipeline]
        Ingest["Incremental Ingest Engine<br/>Tenacity Retries, Backoff, Cursor Pagination"]
        DLQ[("Dead-Letter Table<br/>(dead_letter_records)")]
        WH[("PostgreSQL Warehouse<br/>(suppliers, orders, shipments)")]
        Val["YAML-Configurable Validation Engine<br/>6 Rule Categories"]
        Incidents[("Incidents & Audit Log<br/>(incidents, audit_logs)")]
        LLM["LLM Root-Cause Explainer<br/>Redacted Context & Swappable Provider"]
        Notifier["Pluggable Notifier<br/>Console, File, Slack"]
    end

    subgraph UI & Evaluation [Interfaces & Eval Harness]
        MonitorAPI["Monitor REST API (:8000)"]
        EvalHarness["Eval Runner (/eval)<br/>Precision, Recall, MTTD, Diagnostic Scoring"]
        StreamlitApp["Streamlit Dashboard (:8501)"]
    end

    OS --> Ingest
    SS --> Ingest
    SHS --> Ingest

    Ingest -- Parse Error / Corrupt Key --> DLQ
    Ingest -- Idempotent Upsert --> WH
    WH --> Val
    Val -- Rule Violation --> Incidents
    Incidents --> LLM
    LLM --> Incidents
    Incidents --> Notifier

    MonitorAPI --> WH
    MonitorAPI --> Incidents
    EvalHarness --> FI
    EvalHarness --> Ingest
    EvalHarness --> Val
    StreamlitApp --> MonitorAPI
```

---

## 3. 5-Command Quickstart

```bash
# 1. Clone repository and navigate to project directory
git clone https://github.com/example/integration-monitor.git && cd integration-monitor

# 2. Create and activate Python virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt && pip install -e .

# 4. Run full test suite across all modules
PYTHONPATH=. pytest -v

# 5. Execute evaluation harness to benchmark precision, recall, MTTD, and LLM diagnostic rubric
python -c "from eval.runner import EvaluationRunner; summary = EvaluationRunner().run_all(); print(summary.model_dump_json(indent=2))"
```

*(Optional)* Run full Docker Compose environment:
```bash
docker compose up -d
```
Access Monitor API at `http://localhost:8000/docs` and Streamlit UI at `http://localhost:8501`.

---

## 4. Fault Types & Catching Checks

| Injected Fault Type | Upstream Mechanism | Catching Pipeline Check / Mechanism | Severity |
| :--- | :--- | :--- | :--- |
| **Schema Drift** | Renames/omits expected field (`status` -> `status_v2`) | `orders_schema_status_drift` / Schema & Type | `HIGH` |
| **Null Spikes** | Injects `null` into mandatory primary/business keys | `orders_required_fields` / DLQ parse reject | `CRITICAL` |
| **Duplicates** | Emits repeated primary keys in batch | Ingest duplicate detection & DLQ batch routing | `HIGH` |
| **Late Data** | Injects stale timestamps older than threshold | `orders_freshness_check` / Freshness & Volume | `MEDIUM` |
| **HTTP 500 / Timeouts** | Injects server 500s or network timeouts | Tenacity backoff retries & `UPSTREAM_HTTP_500` DLQ entry | `CRITICAL` |
| **Mismatched IDs** | Emits POs with orphan supplier IDs | `orders_supplier_fk` / Referential Integrity | `CRITICAL` |
| **Silent Corruption (Value)** | Injects negative order totals | `orders_amount_type_and_range` / Schema & Type | `HIGH` |
| **Silent Corruption (Recon)** | Emits shipment quantity > 2x order items | `shipment_order_quantity_reconciliation` / Cross-System | `HIGH` |
| **Volume Drop** | Payload truncated severely below baseline | `orders_volume_drop_check` / Freshness & Volume | `HIGH` |

---

## 5. Evaluation Results

The evaluation harness (`eval/runner.py`) executes 9 scripted scenarios with ground-truth fault injection and measures detection metrics and LLM root-cause diagnostic accuracy.

### Measured Metrics Summary (`eval/results.json`)

- **Total Scenarios Evaluated**: 9
- **Clean Run False Positive Rate**: **0.0%** (0 false alerts on normal baseline data)
- **Overall Mean Time to Detect (MTTD)**: **1.0 pipeline cycles**
- **Raw Log Baseline Accuracy**: **85.7%**
- **LLM Root-Cause Diagnostic Accuracy**: **85.7%**

### Per-Fault Type Performance

| Fault Type | Injected Count | Detected Count | False Positives | Precision | Recall | MTTD (Cycles) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Schema Drift** | 1 | 1 | 0 | 1.000 | 1.000 | 1.00 |
| **Null Spike** | 1 | 1 | 0 | 1.000 | 1.000 | 1.00 |
| **Duplicates** | 1 | 1 | 0 | 1.000 | 1.000 | 1.00 |
| **Late Data** | 1 | 1 | 0 | 1.000 | 1.000 | 1.00 |
| **HTTP 500** | 1 | 1 | 0 | 1.000 | 1.000 | 1.00 |
| **Mismatched IDs** | 1 | 1 | 0 | 1.000 | 1.000 | 1.00 |
| **Silent Corruption** | 1 | 1 | 0 | 1.000 | 1.000 | 1.00 |
| **Volume Drop** | 1 | 1 | 0 | 1.000 | 1.000 | 1.00 |

*Note: All numbers above reflect exact measurements generated by `EvaluationRunner().run_all()` and persisted in `eval/results.json`.*

---

## 6. Known Limitations
1. **Network Topology Coupling**: Volume anomaly thresholds currently compare single batch counts against static floors rather than dynamic ARIMA or rolling-window moving averages.
2. **Schema Evolution**: Downstream warehouse tables require predefined column models. Unstructured arbitrary JSON columns require an extra JSONB staging landing zone for schema-free ingestion.
3. **LLM Token Rate Limits**: For high incident volumes, prompt batching and incident deduplication grouping are essential before invoking hosted external LLM APIs.

---

## 7. AI Tooling & Verification Disclosure
This system was built with assistance from AI coding agents (Google DeepMind Antigravity). The following rigorous validation methodology was enforced:
1. **Phase-by-Phase Verification**: Each layer (mock services, ingestion engine, validation rules, fault injection, alerting, LLM reasoning, eval runner) was isolated and verified through automated tests before subsequent phases were implemented.
2. **Deterministic Evaluation**: No metric or score was manually invented or assumed. The eval suite (`/eval`) executed scripted fault scenarios against ground-truth logs, with real calculations written to `eval/results.json`.
3. **Adversarial & Safety Guardrails**: Untrusted prompt isolation (`<UNTRUSTED_INCIDENT_CONTEXT>`) and recursive regex/key-based PII redaction were implemented and unit-tested to prevent prompt injection and data leaks.
4. **Code Quality**: Ruff linting (`ruff check .`) and Pytest test suites were run repeatedly with 100% pass rates.
