"""
Report Generator — Formats investigation findings into structured reports.

Generates both Markdown and JSON formatted RCA reports from
investigation findings collected by the specialist agents.
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime


class ReportGenerator:
    """Generates formatted Root Cause Analysis reports."""

    def generate_markdown_report(self, findings: Dict[str, Any]) -> str:
        """
        Generate a Markdown-formatted RCA report.

        Args:
            findings: Dictionary containing all investigation findings

        Returns:
            Formatted Markdown string
        """
        sections = []

        # Header
        sections.append("# Pipeline Failure Root Cause Analysis")
        sections.append(f"\n*Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}*\n")

        # Incident Summary
        sections.append("## Incident Summary")
        sections.append(f"- **Pipeline ID:** {findings.get('pipeline_id', 'Unknown')}")
        sections.append(f"- **Failure Time:** {findings.get('failure_timestamp', 'Unknown')}")
        sections.append(f"- **Pipeline Duration:** {findings.get('pipeline_duration', 'Unknown')}")
        sections.append(f"- **Pipeline Status:** {findings.get('pipeline_status', 'FAILED')}")
        sections.append("")

        # Root Cause
        sections.append("## Root Cause")
        rca = findings.get("root_cause", {})
        sections.append(f"- **Primary Root Cause:** {rca.get('primary_cause', 'Under investigation')}")
        sections.append(f"- **Root Cause Category:** {rca.get('category', 'Unknown')}")
        sections.append(f"- **Confidence Level:** {rca.get('confidence', 'medium')}")
        if rca.get("secondary_causes"):
            sections.append(f"- **Contributing Factors:**")
            for cause in rca["secondary_causes"]:
                sections.append(f"  - {cause}")
        sections.append("")

        # Evidence
        sections.append("## Evidence")

        log_evidence = findings.get("log_evidence", {})
        if log_evidence:
            sections.append("### Log Evidence")
            if log_evidence.get("failure_point"):
                fp = log_evidence["failure_point"]
                sections.append(f"- **Failure Stage:** {fp.get('stage', 'Unknown')}")
                sections.append(f"- **Failure Timestamp:** {fp.get('timestamp', 'Unknown')}")
                sections.append(f"- **Error Message:**")
                sections.append(f"  ```")
                sections.append(f"  {fp.get('message', 'No error message')}")
                sections.append(f"  ```")
                if fp.get("error_code"):
                    sections.append(f"- **Error Code:** {fp['error_code']}")

            if log_evidence.get("preceding_warnings"):
                sections.append(f"\n**Preceding Warnings:**")
                for warning in log_evidence["preceding_warnings"]:
                    if isinstance(warning, dict):
                        ts = warning.get("timestamp", "")
                        msg = warning.get("message", "")
                        sections.append(f"- `[{ts}]` {msg}")
                    else:
                        sections.append(f"- {warning}")

        schema_evidence = findings.get("schema_evidence", {})
        if schema_evidence:
            sections.append("\n### Schema Evidence")
            if schema_evidence.get("all_differences"):
                for diff in schema_evidence["all_differences"]:
                    severity = diff.get("severity", "info").upper()
                    sections.append(f"- **[{severity}]** {diff.get('description', '')}")
            if schema_evidence.get("most_likely_cause_of_failure"):
                sections.append(f"\n**Schema Analysis Conclusion:** {schema_evidence['most_likely_cause_of_failure']}")

        data_evidence = findings.get("data_evidence", {})
        if data_evidence:
            sections.append("\n### Data Quality Evidence")
            if data_evidence.get("data_loss_points"):
                for lp in data_evidence["data_loss_points"]:
                    severity = lp.get("severity", "info").upper()
                    sections.append(f"- **[{severity}]** {lp.get('description', '')}")
            if data_evidence.get("null_violations"):
                for nv in data_evidence["null_violations"]:
                    severity = nv.get("severity", "info").upper()
                    sections.append(f"- **[{severity}]** {nv.get('description', '')}")
            if data_evidence.get("most_likely_cause_of_failure"):
                sections.append(f"\n**Data Quality Conclusion:** {data_evidence['most_likely_cause_of_failure']}")

        sections.append("")

        # Timeline
        sections.append("## Timeline")
        timeline = findings.get("timeline", [])
        if timeline:
            for event in timeline:
                sections.append(f"1. **{event.get('time', '')}** — {event.get('event', '')}")
        else:
            sections.append("*Timeline not available*")
        sections.append("")

        # Impact
        sections.append("## Impact")
        impact = findings.get("impact", {})
        sections.append(f"- **Data Affected:** {impact.get('data_affected', 'Unknown')}")
        sections.append(f"- **Records Impacted:** {impact.get('records_impacted', 'Unknown')}")
        if impact.get("downstream_systems"):
            sections.append(f"- **Downstream Systems:** {', '.join(impact['downstream_systems'])}")
        sections.append("")

        # Remediation Steps
        sections.append("## Remediation Steps")
        remediation = findings.get("remediation", [])
        if remediation:
            for i, step in enumerate(remediation, 1):
                step_type = step.get("type", "action")
                sections.append(f"### Step {i}: {step.get('title', f'Action {i}')} ({step_type})")
                sections.append(f"{step.get('description', '')}")
                if step.get("command"):
                    sections.append(f"```sql\n{step['command']}\n```")
                sections.append("")
        else:
            sections.append("*Remediation steps pending investigation completion*")
        sections.append("")

        # Estimated Time to Resolution
        sections.append("## Estimated Time to Resolution")
        sections.append(f"- **With this report:** {findings.get('time_with_report', '15-30 minutes')}")
        sections.append(f"- **Without this report (manual investigation):** 2-4 hours")
        sections.append(f"- **Time saved:** ~{findings.get('time_saved', '1.5-3.5 hours')}")
        sections.append("")

        return "\n".join(sections)

    def generate_json_report(self, findings: Dict[str, Any]) -> str:
        """
        Generate a JSON-formatted RCA report.

        Args:
            findings: Dictionary containing all investigation findings

        Returns:
            JSON string of the report
        """
        report = {
            "report_type": "pipeline_failure_rca",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "incident": {
                "pipeline_id": findings.get("pipeline_id", "Unknown"),
                "failure_timestamp": findings.get("failure_timestamp", "Unknown"),
                "pipeline_duration": findings.get("pipeline_duration", "Unknown"),
                "pipeline_status": findings.get("pipeline_status", "FAILED"),
            },
            "root_cause": findings.get("root_cause", {}),
            "evidence": {
                "log_evidence": findings.get("log_evidence", {}),
                "schema_evidence": findings.get("schema_evidence", {}),
                "data_evidence": findings.get("data_evidence", {}),
            },
            "timeline": findings.get("timeline", []),
            "impact": findings.get("impact", {}),
            "remediation": findings.get("remediation", []),
            "resolution_estimate": {
                "with_report": findings.get("time_with_report", "15-30 minutes"),
                "without_report": "2-4 hours",
                "time_saved": findings.get("time_saved", "1.5-3.5 hours"),
            },
            "verification": findings.get("verification", {}),
        }

        return json.dumps(report, indent=2, default=str)

    def verify_report_completeness(self, findings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify that the RCA report meets minimum completeness requirements.

        Returns:
            Dictionary with verification results and any missing elements
        """
        checks = {
            "failure_point_identified": False,
            "evidence_cited": False,
            "remediation_actionable": False,
            "confidence_stated": False,
            "resolution_time_included": False,
        }
        missing = []

        # Check 1: Is failure point specifically identified?
        rca = findings.get("root_cause", {})
        if rca.get("primary_cause") and rca["primary_cause"] != "Under investigation":
            checks["failure_point_identified"] = True
        else:
            missing.append("Failure point is not specifically identified. Provide a clear primary root cause statement.")

        # Check 2: Is evidence cited?
        has_log_evidence = bool(findings.get("log_evidence", {}).get("failure_point"))
        has_schema_evidence = bool(findings.get("schema_evidence", {}).get("all_differences"))
        has_data_evidence = bool(findings.get("data_evidence", {}).get("data_loss_points"))
        if has_log_evidence or has_schema_evidence or has_data_evidence:
            checks["evidence_cited"] = True
        else:
            missing.append("No evidence cited. Include specific log lines, schema diffs, or data quality metrics.")

        # Check 3: Are remediation steps actionable?
        remediation = findings.get("remediation", [])
        if remediation and any(
            step.get("command") or step.get("description")
            for step in remediation
        ):
            checks["remediation_actionable"] = True
        else:
            missing.append("Remediation steps are missing or too generic. Include specific commands or actions.")

        # Check 4: Is confidence level stated?
        if rca.get("confidence"):
            checks["confidence_stated"] = True
        else:
            missing.append("Confidence level not stated. Add 'high', 'medium', or 'low' confidence assessment.")

        # Check 5: Is resolution time included?
        if findings.get("time_with_report"):
            checks["resolution_time_included"] = True
        else:
            missing.append("Resolution time estimate not included.")

        all_passed = all(checks.values())

        return {
            "passed": all_passed,
            "checks": checks,
            "missing_elements": missing,
            "score": sum(checks.values()) / len(checks),
        }
