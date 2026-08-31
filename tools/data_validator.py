"""
Data Validator — Checks row counts, null rates, and duplicate patterns.

This tool performs data quality validation across pipeline stages:
- Row count consistency checks between stages
- Data loss detection and quantification
- Null rate analysis against thresholds
- Duplicate detection based on key columns
"""

from typing import Dict, List, Any, Optional


class DataValidator:
    """Validates data quality across ETL pipeline stages."""

    # Default thresholds
    ACCEPTABLE_LOSS_THRESHOLD = 0.001  # 0.1%
    WARNING_LOSS_THRESHOLD = 0.01      # 1%
    CRITICAL_LOSS_THRESHOLD = 0.10     # 10%

    def validate_row_counts(
        self,
        row_counts: Dict[str, int],
        expected_counts: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Validate row counts across pipeline stages.

        Args:
            row_counts: Dictionary mapping stage names to row counts
            expected_counts: Optional expected counts for comparison

        Returns:
            Dictionary containing validation results
        """
        result = {
            "stage_counts": row_counts,
            "data_loss_points": [],
            "total_input": 0,
            "total_output": 0,
            "overall_loss_pct": 0.0,
            "overall_assessment": "healthy",
            "most_likely_cause_of_failure": None,
        }

        # Find the logical order of stages
        ordered_stages = self._order_stages(row_counts)

        if not ordered_stages:
            result["overall_assessment"] = "insufficient_data"
            return result

        result["total_input"] = row_counts[ordered_stages[0]]
        result["total_output"] = row_counts[ordered_stages[-1]]

        # Calculate loss between consecutive stages
        for i in range(1, len(ordered_stages)):
            prev_stage = ordered_stages[i - 1]
            curr_stage = ordered_stages[i]
            prev_count = row_counts[prev_stage]
            curr_count = row_counts[curr_stage]

            if prev_count == 0:
                continue

            loss = prev_count - curr_count
            loss_pct = loss / prev_count if prev_count > 0 else 0

            if loss > 0:
                severity = self._classify_loss(loss_pct)
                loss_point = {
                    "from_stage": prev_stage,
                    "to_stage": curr_stage,
                    "from_count": prev_count,
                    "to_count": curr_count,
                    "records_lost": loss,
                    "loss_percentage": round(loss_pct * 100, 2),
                    "severity": severity,
                    "description": (
                        f"Lost {loss:,} records ({loss_pct*100:.1f}%) "
                        f"between {prev_stage} and {curr_stage}"
                    ),
                }
                result["data_loss_points"].append(loss_point)

        # Calculate overall loss
        if result["total_input"] > 0:
            overall_loss = result["total_input"] - result["total_output"]
            result["overall_loss_pct"] = round(
                (overall_loss / result["total_input"]) * 100, 2
            )

        # Determine overall assessment
        if any(lp["severity"] == "critical" for lp in result["data_loss_points"]):
            result["overall_assessment"] = "critical"
        elif any(lp["severity"] == "warning" for lp in result["data_loss_points"]):
            result["overall_assessment"] = "warning"
        elif result["data_loss_points"]:
            result["overall_assessment"] = "acceptable"
        else:
            result["overall_assessment"] = "healthy"

        # Determine most likely cause
        if result["data_loss_points"]:
            worst = max(result["data_loss_points"], key=lambda x: x["loss_percentage"])
            if worst["severity"] in ("critical", "warning"):
                result["most_likely_cause_of_failure"] = (
                    f"Significant data loss detected: {worst['records_lost']:,} records "
                    f"({worst['loss_percentage']}%) lost between "
                    f"{worst['from_stage']} and {worst['to_stage']} stages. "
                    f"This exceeds the acceptable threshold of {self.WARNING_LOSS_THRESHOLD*100}%."
                )

        # Compare with expected counts if provided
        if expected_counts:
            result["expected_vs_actual"] = []
            for stage, expected in expected_counts.items():
                actual = row_counts.get(stage, 0)
                if actual != expected:
                    result["expected_vs_actual"].append({
                        "stage": stage,
                        "expected": expected,
                        "actual": actual,
                        "difference": actual - expected,
                        "description": f"Stage '{stage}': expected {expected:,} rows, got {actual:,} rows",
                    })

        return result

    def check_null_rates(
        self,
        null_counts: Dict[str, int],
        total_rows: int,
        not_null_columns: Optional[List[str]] = None,
        threshold: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Check null rates for each column against thresholds.

        Args:
            null_counts: Dictionary mapping column names to null counts
            total_rows: Total number of rows
            not_null_columns: Columns that should have zero nulls
            threshold: Maximum acceptable null rate (default 5%)

        Returns:
            Dictionary containing null rate analysis
        """
        result = {
            "total_rows": total_rows,
            "null_violations": [],
            "null_rates": {},
            "overall_assessment": "healthy",
        }

        not_null_set = set(not_null_columns or [])

        for column, null_count in null_counts.items():
            null_rate = null_count / total_rows if total_rows > 0 else 0
            result["null_rates"][column] = {
                "null_count": null_count,
                "null_rate": round(null_rate * 100, 2),
            }

            is_violation = False
            severity = "info"

            if column in not_null_set and null_count > 0:
                is_violation = True
                severity = "critical"
            elif null_rate > threshold:
                is_violation = True
                severity = "warning"

            if is_violation:
                violation = {
                    "column": column,
                    "null_count": null_count,
                    "null_rate_pct": round(null_rate * 100, 2),
                    "severity": severity,
                    "is_not_null_column": column in not_null_set,
                    "description": (
                        f"Column '{column}': {null_count:,} nulls ({null_rate*100:.1f}%)"
                        + (" — violates NOT NULL constraint" if column in not_null_set else f" — exceeds {threshold*100}% threshold")
                    ),
                }
                result["null_violations"].append(violation)

        if any(v["severity"] == "critical" for v in result["null_violations"]):
            result["overall_assessment"] = "critical"
        elif result["null_violations"]:
            result["overall_assessment"] = "warning"

        return result

    def check_duplicates(
        self,
        total_rows: int,
        unique_key_count: int,
        key_name: str = "primary_key",
        expected_unique_pct: float = 100.0,
    ) -> Dict[str, Any]:
        """
        Check for duplicate records based on key counts.

        Args:
            total_rows: Total number of rows
            unique_key_count: Number of unique key values
            key_name: Name of the key being checked
            expected_unique_pct: Expected percentage of unique rows

        Returns:
            Dictionary containing duplicate analysis
        """
        duplicate_count = total_rows - unique_key_count
        duplicate_pct = (duplicate_count / total_rows * 100) if total_rows > 0 else 0

        severity = "info"
        if duplicate_pct > 10:
            severity = "critical"
        elif duplicate_pct > 1:
            severity = "warning"
        elif duplicate_pct > 0:
            severity = "info"

        result = {
            "key_name": key_name,
            "total_rows": total_rows,
            "unique_keys": unique_key_count,
            "duplicate_count": duplicate_count,
            "duplicate_percentage": round(duplicate_pct, 2),
            "severity": severity,
            "description": (
                f"Key '{key_name}': {duplicate_count:,} duplicates found "
                f"({duplicate_pct:.1f}%) out of {total_rows:,} total rows"
            ),
        }

        return result

    def _order_stages(self, row_counts: Dict[str, int]) -> List[str]:
        """Order stage names in logical pipeline order."""
        stage_priority = {
            "extract": 0,
            "transform": 1,
            "load": 2,
            "validation": 3,
        }

        # Sort by known stage names first, then by any substages
        def sort_key(stage_name: str) -> tuple:
            lower = stage_name.lower()
            for known, priority in stage_priority.items():
                if lower.startswith(known):
                    # Sub-sort by step number if present
                    import re
                    step_match = re.search(r"(\d+)", lower)
                    sub = int(step_match.group(1)) if step_match else 0
                    return (priority, sub)
            return (999, 0)

        return sorted(row_counts.keys(), key=sort_key)

    def _classify_loss(self, loss_pct: float) -> str:
        """Classify data loss severity."""
        if loss_pct >= self.CRITICAL_LOSS_THRESHOLD:
            return "critical"
        elif loss_pct >= self.WARNING_LOSS_THRESHOLD:
            return "warning"
        elif loss_pct >= self.ACCEPTABLE_LOSS_THRESHOLD:
            return "acceptable"
        return "negligible"

    def generate_quality_summary(
        self,
        row_counts: Dict[str, int],
        null_info: Optional[Dict] = None,
        duplicate_info: Optional[Dict] = None,
    ) -> str:
        """Generate a comprehensive data quality summary."""
        parts = []

        # Row count analysis
        rc_result = self.validate_row_counts(row_counts)
        parts.append("=== Row Count Analysis ===")
        parts.append(f"Input: {rc_result['total_input']:,} rows")
        parts.append(f"Output: {rc_result['total_output']:,} rows")
        parts.append(f"Overall loss: {rc_result['overall_loss_pct']}%")
        parts.append(f"Assessment: {rc_result['overall_assessment'].upper()}")

        if rc_result["data_loss_points"]:
            parts.append("\nData loss points:")
            for lp in rc_result["data_loss_points"]:
                parts.append(f"  [{lp['severity'].upper()}] {lp['description']}")

        if rc_result.get("most_likely_cause_of_failure"):
            parts.append(f"\nLikely cause: {rc_result['most_likely_cause_of_failure']}")

        return "\n".join(parts)
