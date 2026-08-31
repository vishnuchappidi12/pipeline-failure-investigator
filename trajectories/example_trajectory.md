# Agent Execution Trajectory: Scenario 01 (Schema Drift)

This document traces a real execution of the multi-agent system on Scenario 01.

## 1. Initial State
The user provides pipeline logs, source schema, target schema, and row counts via the UI.
The workflow graph is initialized with this state.

## 2. Node: `analyze_logs` (LogAnalysisAgent)
**Orchestrator Decision:** The graph entry point is `analyze_logs`.
**Action:** The Log Parser tool deterministically extracts error codes and row counts. The LLM then analyzes the error context.
**Output State Update:**
```json
"log_findings": {
  "log_analysis": {
    "failure_timestamp": "2026-08-15T03:14:22Z",
    "failed_stage": "load",
    "error_message": "column 'customer_tier' of relation 'dim_customers' does not exist.",
    "error_code": "42703",
    "confidence": "high"
  },
  "parsed_summary": "..."
}
```

## 3. Orchestrator Decision
**Input:** Log findings indicate a missing column error (42703).
**Decision:** Route to `schema_agent` because the error strongly suggests a schema mismatch.

## 4. Node: `analyze_schema` (SchemaAgent)
**Action:** The Schema Comparator tool deterministically diffs the source and target JSON schemas. The LLM then reviews the diff in the context of the log failure.
**Output State Update:**
```json
"schema_findings": {
  "missing_in_target": [
    {
      "column": "customer_tier",
      "severity": "critical",
      "description": "Column 'customer_tier' (VARCHAR(50)) exists in source but not in target. Column is NOT NULL."
    }
  ],
  "pipeline_impact": "critical",
  "most_likely_cause_of_failure": "Schema drift: 1 NOT NULL column(s) (customer_tier) exist in source but not in target table."
}
```

## 5. Node: `generate_rca` (RcaAgent)
**Action:** The agent synthesizes findings from logs and schema analysis into a structured JSON report format.
**Output State Update:**
```json
"rca_data": {
  "root_cause": {
    "primary_cause": "Schema drift: A new NOT NULL column 'customer_tier' was added to the source table but not the target warehouse.",
    "category": "schema",
    "confidence": "high"
  }
  // ... rest of the structured report
}
```

## 6. Node: `verify_and_format` (Verification Layer)
**Action:** Deterministic script checks if the `rca_data` contains required fields (evidence cited, actionable remediation, resolution time).
**Result:** 
- `failure_point_identified`: True
- `evidence_cited`: True (Log and Schema evidence present)
- `remediation_actionable`: True (Contains ALTER TABLE command)
**Output State Update:**
```json
"verification_result": {
  "passed": true
}
```

## 7. Orchestrator Decision
**Input:** Verification passed.
**Decision:** Route to `FINISH`.

## 8. Final Output
The system generates the final Markdown report and displays it to the user. Total execution time: ~12 seconds.
