"""
Metrics and scoring functions for evaluation.
"""

from typing import Dict, Any, List


def score_rca_accuracy(expected_root_cause: str, expected_failure_stage: str, agent_output_rca: Dict[str, Any]) -> float:
    """
    Score if the agent correctly identified the root cause and stage.
    1.0 = Perfect match
    0.5 = Partial match (got stage right, cause wrong, or vice versa)
    0.0 = Completely wrong
    """
    score = 0.0
    
    # Check category match
    output_category = agent_output_rca.get("root_cause", {}).get("category", "").lower()
    if expected_root_cause.lower() in output_category or output_category in expected_root_cause.lower():
        score += 0.5
    # Handle "multiple" case
    elif expected_root_cause == "multiple" and output_category != "unknown":
        score += 0.5
        
    # Check stage match in log evidence
    output_stage = agent_output_rca.get("log_evidence", {}).get("failure_point", {}).get("stage", "").lower()
    if expected_failure_stage.lower() in output_stage or output_stage in expected_failure_stage.lower():
        score += 0.5
    # Handle "multiple" case
    elif expected_failure_stage == "multiple" and output_stage != "unknown":
        score += 0.5
        
    return score


def calculate_evidence_citation_rate(agent_output_rca: Dict[str, Any]) -> float:
    """Calculate percentage of claims backed by evidence (0.0 to 1.0)."""
    has_log = bool(agent_output_rca.get("log_evidence", {}).get("failure_point"))
    has_schema = bool(agent_output_rca.get("schema_evidence", {}).get("all_differences"))
    has_data = bool(agent_output_rca.get("data_evidence", {}).get("data_loss_points"))
    
    possible_evidence = 3
    provided = sum([has_log, has_schema, has_data])
    
    return provided / possible_evidence if provided > 0 else 0.0


def score_report_completeness(agent_output_rca: Dict[str, Any]) -> float:
    """Score the completeness of the report structure (0.0 to 1.0)."""
    checks = [
        bool(agent_output_rca.get("root_cause", {}).get("primary_cause")),
        bool(agent_output_rca.get("root_cause", {}).get("confidence")),
        bool(agent_output_rca.get("remediation", [])),
        bool(agent_output_rca.get("impact", {}).get("data_affected")),
        bool(agent_output_rca.get("time_with_report"))
    ]
    
    return sum(checks) / len(checks)
