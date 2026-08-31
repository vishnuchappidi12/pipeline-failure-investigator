"""
Log Parser — Extracts structured information from raw ETL pipeline logs.

This tool parses pipeline execution logs to identify:
- Error messages and their timestamps
- Warning messages that preceded errors
- Pipeline stages (extract, transform, load, validation)
- Row counts at each stage
- Duration and performance metrics
"""

import re
import json
from typing import Dict, List, Optional, Any
from datetime import datetime


class LogParser:
    """Parses ETL pipeline execution logs into structured findings."""

    # Patterns for log parsing
    TIMESTAMP_PATTERN = re.compile(
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?)"
    )
    LOG_LEVEL_PATTERN = re.compile(
        r"\[(INFO|WARNING|ERROR|DEBUG|CRITICAL)\]"
    )
    STAGE_PATTERN = re.compile(
        r"\[(EXTRACT|TRANSFORM|LOAD|VALIDATION|AUTH)\]"
    )
    ROW_COUNT_PATTERN = re.compile(
        r"(?:Rows?|rows?|Records?|records?)[\s:]*(\d[\d,]*)"
    )
    ERROR_CODE_PATTERN = re.compile(
        r"SQLSTATE:\s*(\w+)"
    )
    STEP_PATTERN = re.compile(
        r"Step\s+(\d+/\d+):\s+(\w+)"
    )
    BATCH_PATTERN = re.compile(
        r"Batch\s+(\d+/\d+)"
    )

    def parse_logs(self, logs: List[str]) -> Dict[str, Any]:
        """
        Parse a list of log lines into structured findings.

        Args:
            logs: List of log line strings

        Returns:
            Dictionary containing structured log analysis
        """
        result = {
            "total_lines": len(logs),
            "errors": [],
            "warnings": [],
            "info_lines": [],
            "stages_found": [],
            "row_counts": {},
            "error_codes": [],
            "timeline": [],
            "failure_point": None,
            "pipeline_duration": None,
            "pipeline_status": None,
        }

        for i, line in enumerate(logs):
            parsed = self._parse_line(line, i)
            result["timeline"].append(parsed)

            if parsed["level"] == "ERROR":
                result["errors"].append(parsed)
            elif parsed["level"] == "WARNING":
                result["warnings"].append(parsed)
            else:
                result["info_lines"].append(parsed)

            if parsed["stage"] and parsed["stage"] not in result["stages_found"]:
                result["stages_found"].append(parsed["stage"])

            if parsed["row_count"] is not None:
                stage_key = parsed["stage"] or "unknown"
                step_key = parsed.get("step_name", "")
                key = f"{stage_key}_{step_key}".strip("_").lower()
                result["row_counts"][key] = parsed["row_count"]

            if parsed["error_code"]:
                result["error_codes"].append(parsed["error_code"])

        # Identify failure point
        if result["errors"]:
            first_error = result["errors"][0]
            result["failure_point"] = {
                "timestamp": first_error["timestamp"],
                "stage": first_error["stage"],
                "message": first_error["message"],
                "line_number": first_error["line_number"],
                "error_code": first_error["error_code"],
            }

        # Extract pipeline duration and status
        result["pipeline_duration"] = self._extract_duration(logs)
        result["pipeline_status"] = self._extract_status(logs)

        # Get preceding warnings before first error
        if result["errors"]:
            first_error_idx = result["errors"][0]["line_number"]
            result["preceding_warnings"] = [
                w for w in result["warnings"]
                if w["line_number"] < first_error_idx
            ]
        else:
            result["preceding_warnings"] = []

        return result

    def _parse_line(self, line: str, line_number: int) -> Dict[str, Any]:
        """Parse a single log line into structured data."""
        parsed = {
            "line_number": line_number,
            "raw": line,
            "timestamp": None,
            "level": None,
            "stage": None,
            "message": line,
            "row_count": None,
            "error_code": None,
            "step_name": None,
            "batch_info": None,
        }

        # Extract timestamp
        ts_match = self.TIMESTAMP_PATTERN.search(line)
        if ts_match:
            parsed["timestamp"] = ts_match.group(1)

        # Extract log level
        level_match = self.LOG_LEVEL_PATTERN.search(line)
        if level_match:
            parsed["level"] = level_match.group(1)

        # Extract stage
        stage_match = self.STAGE_PATTERN.search(line)
        if stage_match:
            parsed["stage"] = stage_match.group(1)

        # Extract row count
        row_match = self.ROW_COUNT_PATTERN.search(line)
        if row_match:
            parsed["row_count"] = int(row_match.group(1).replace(",", ""))

        # Extract error code
        code_match = self.ERROR_CODE_PATTERN.search(line)
        if code_match:
            parsed["error_code"] = code_match.group(1)

        # Extract step info
        step_match = self.STEP_PATTERN.search(line)
        if step_match:
            parsed["step_name"] = step_match.group(2)

        # Extract batch info
        batch_match = self.BATCH_PATTERN.search(line)
        if batch_match:
            parsed["batch_info"] = batch_match.group(1)

        # Clean message (remove timestamp and level prefix)
        msg = line
        if ts_match:
            msg = msg[ts_match.end():].strip()
        if level_match:
            idx = msg.find(level_match.group(0))
            if idx >= 0:
                msg = msg[idx + len(level_match.group(0)):].strip()
        if stage_match:
            idx = msg.find(stage_match.group(0))
            if idx >= 0:
                msg = msg[idx + len(stage_match.group(0)):].strip()
        parsed["message"] = msg

        return parsed

    def _extract_duration(self, logs: List[str]) -> Optional[str]:
        """Extract pipeline duration from logs."""
        for line in reversed(logs):
            duration_match = re.search(r"Duration:\s*(\S+)", line)
            if duration_match:
                return duration_match.group(1)
        return None

    def _extract_status(self, logs: List[str]) -> Optional[str]:
        """Extract pipeline final status from logs."""
        for line in reversed(logs):
            status_match = re.search(r"status:\s*(\w+)", line)
            if status_match:
                return status_match.group(1)
        return None

    def get_error_summary(self, logs: List[str]) -> str:
        """Get a human-readable error summary from logs."""
        parsed = self.parse_logs(logs)

        summary_parts = []
        summary_parts.append(f"Pipeline Status: {parsed['pipeline_status'] or 'UNKNOWN'}")
        summary_parts.append(f"Duration: {parsed['pipeline_duration'] or 'UNKNOWN'}")
        summary_parts.append(f"Total log lines: {parsed['total_lines']}")
        summary_parts.append(f"Errors found: {len(parsed['errors'])}")
        summary_parts.append(f"Warnings found: {len(parsed['warnings'])}")
        summary_parts.append(f"Stages: {', '.join(parsed['stages_found'])}")

        if parsed["failure_point"]:
            fp = parsed["failure_point"]
            summary_parts.append(f"\nFailure Point:")
            summary_parts.append(f"  Timestamp: {fp['timestamp']}")
            summary_parts.append(f"  Stage: {fp['stage']}")
            summary_parts.append(f"  Error: {fp['message']}")
            if fp["error_code"]:
                summary_parts.append(f"  SQL State: {fp['error_code']}")

        if parsed["preceding_warnings"]:
            summary_parts.append(f"\nPreceding Warnings ({len(parsed['preceding_warnings'])}):")
            for w in parsed["preceding_warnings"]:
                summary_parts.append(f"  [{w['timestamp']}] {w['message']}")

        return "\n".join(summary_parts)

    def extract_row_counts_from_logs(self, logs: List[str]) -> Dict[str, int]:
        """Extract row counts mentioned in logs, organized by stage."""
        parsed = self.parse_logs(logs)
        return parsed["row_counts"]
