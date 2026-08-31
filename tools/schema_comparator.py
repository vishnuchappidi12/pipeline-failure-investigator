"""
Schema Comparator — Compares source and target schemas to find differences.

This tool performs detailed schema comparison including:
- Missing columns in either direction
- Data type mismatches
- Nullable constraint differences
- Primary key differences
- Column length mismatches for string types
"""

import re
from typing import Dict, List, Any, Optional, Tuple


class SchemaComparator:
    """Compares source and target database schemas to identify differences."""

    # Map of compatible type families
    TYPE_FAMILIES = {
        "integer": {"INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "SERIAL", "BIGSERIAL"},
        "decimal": {"DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "REAL", "DOUBLE PRECISION"},
        "string": {"VARCHAR", "CHAR", "TEXT", "STRING", "CHARACTER VARYING", "NVARCHAR"},
        "datetime": {"TIMESTAMP", "DATETIME", "DATE", "TIME", "TIMESTAMPTZ"},
        "boolean": {"BOOLEAN", "BOOL", "BIT"},
        "uuid": {"UUID"},
        "json": {"JSON", "JSONB"},
    }

    def compare_schemas(
        self,
        source_schema: Dict[str, Any],
        target_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compare source and target schemas and return detailed differences.

        Args:
            source_schema: Dictionary with 'table_name' and 'columns' list
            target_schema: Dictionary with 'table_name' and 'columns' list

        Returns:
            Dictionary containing all identified schema differences
        """
        source_cols = {col["name"]: col for col in source_schema.get("columns", [])}
        target_cols = {col["name"]: col for col in target_schema.get("columns", [])}

        source_names = set(source_cols.keys())
        target_names = set(target_cols.keys())

        result = {
            "source_table": source_schema.get("table_name", "unknown"),
            "target_table": target_schema.get("table_name", "unknown"),
            "source_column_count": len(source_cols),
            "target_column_count": len(target_cols),
            "missing_in_target": [],
            "missing_in_source": [],
            "type_mismatches": [],
            "nullable_differences": [],
            "primary_key_differences": [],
            "length_mismatches": [],
            "all_differences": [],
            "compatible": True,
            "pipeline_impact": "none",
            "most_likely_cause_of_failure": None,
            "summary": "",
        }

        # 1. Find missing columns
        missing_in_target = source_names - target_names
        missing_in_source = target_names - source_names

        for col_name in sorted(missing_in_target):
            col = source_cols[col_name]
            diff = {
                "column": col_name,
                "issue": "missing_in_target",
                "source_type": col["type"],
                "source_nullable": col.get("nullable", True),
                "severity": "critical" if not col.get("nullable", True) else "warning",
                "description": f"Column '{col_name}' ({col['type']}) exists in source but not in target"
                               + (". Column is NOT NULL — will cause insert failures." if not col.get("nullable", True) else "."),
            }
            result["missing_in_target"].append(diff)
            result["all_differences"].append(diff)

        for col_name in sorted(missing_in_source):
            col = target_cols[col_name]
            diff = {
                "column": col_name,
                "issue": "missing_in_source",
                "target_type": col["type"],
                "target_nullable": col.get("nullable", True),
                "severity": "critical" if not col.get("nullable", True) else "warning",
                "description": f"Column '{col_name}' ({col['type']}) exists in target but not in source"
                               + (". Column is NOT NULL — inserts will fail without a default value." if not col.get("nullable", True) else "."),
            }
            result["missing_in_source"].append(diff)
            result["all_differences"].append(diff)

        # 2. Compare shared columns
        shared_cols = source_names & target_names
        for col_name in sorted(shared_cols):
            s_col = source_cols[col_name]
            t_col = target_cols[col_name]

            # Check type compatibility
            s_type = s_col["type"].upper()
            t_type = t_col["type"].upper()

            if not self._types_compatible(s_type, t_type):
                diff = {
                    "column": col_name,
                    "issue": "type_mismatch",
                    "source_type": s_col["type"],
                    "target_type": t_col["type"],
                    "severity": "critical",
                    "description": f"Column '{col_name}': source type {s_col['type']} is incompatible with target type {t_col['type']}",
                }
                result["type_mismatches"].append(diff)
                result["all_differences"].append(diff)

            # Check string length compatibility
            s_length = self._extract_length(s_type)
            t_length = self._extract_length(t_type)
            if s_length and t_length and s_length > t_length:
                diff = {
                    "column": col_name,
                    "issue": "length_mismatch",
                    "source_type": s_col["type"],
                    "target_type": t_col["type"],
                    "source_length": s_length,
                    "target_length": t_length,
                    "severity": "critical",
                    "description": f"Column '{col_name}': source allows {s_length} chars but target only allows {t_length} chars. Data truncation will occur.",
                }
                result["length_mismatches"].append(diff)
                result["all_differences"].append(diff)

            # Check nullable differences
            s_nullable = s_col.get("nullable", True)
            t_nullable = t_col.get("nullable", True)
            if s_nullable != t_nullable:
                severity = "critical" if s_nullable and not t_nullable else "info"
                diff = {
                    "column": col_name,
                    "issue": "nullable_difference",
                    "source_nullable": s_nullable,
                    "target_nullable": t_nullable,
                    "severity": severity,
                    "description": f"Column '{col_name}': source is {'nullable' if s_nullable else 'NOT NULL'} "
                                   f"but target is {'nullable' if t_nullable else 'NOT NULL'}"
                                   + (". Source nulls will violate target NOT NULL constraint." if s_nullable and not t_nullable else "."),
                }
                result["nullable_differences"].append(diff)
                result["all_differences"].append(diff)

            # Check primary key differences
            s_pk = s_col.get("primary_key", False)
            t_pk = t_col.get("primary_key", False)
            if s_pk != t_pk:
                diff = {
                    "column": col_name,
                    "issue": "primary_key_difference",
                    "source_is_pk": s_pk,
                    "target_is_pk": t_pk,
                    "severity": "warning",
                    "description": f"Column '{col_name}': {'IS' if s_pk else 'is NOT'} a primary key in source "
                                   f"but {'IS' if t_pk else 'is NOT'} a primary key in target.",
                }
                result["primary_key_differences"].append(diff)
                result["all_differences"].append(diff)

        # Determine overall impact
        critical_count = sum(1 for d in result["all_differences"] if d.get("severity") == "critical")
        warning_count = sum(1 for d in result["all_differences"] if d.get("severity") == "warning")

        if critical_count > 0:
            result["pipeline_impact"] = "critical"
            result["compatible"] = False
        elif warning_count > 0:
            result["pipeline_impact"] = "warning"
        else:
            result["pipeline_impact"] = "none"

        # Determine most likely cause
        if result["missing_in_target"]:
            critical_missing = [d for d in result["missing_in_target"] if d["severity"] == "critical"]
            if critical_missing:
                result["most_likely_cause_of_failure"] = (
                    f"Schema drift: {len(critical_missing)} NOT NULL column(s) "
                    f"({', '.join(d['column'] for d in critical_missing)}) "
                    f"exist in source but not in target table. "
                    f"Load will fail because these columns cannot be mapped."
                )
        elif result["type_mismatches"]:
            result["most_likely_cause_of_failure"] = (
                f"Type mismatch: {len(result['type_mismatches'])} column(s) have incompatible types "
                f"between source and target. Data cannot be loaded without type conversion."
            )
        elif result["length_mismatches"]:
            result["most_likely_cause_of_failure"] = (
                f"String length mismatch: {len(result['length_mismatches'])} column(s) have longer "
                f"values in source than target allows. Data truncation errors will occur."
            )
        elif result["nullable_differences"]:
            critical_null = [d for d in result["nullable_differences"] if d["severity"] == "critical"]
            if critical_null:
                result["most_likely_cause_of_failure"] = (
                    f"Nullable constraint mismatch: {len(critical_null)} column(s) are nullable in "
                    f"source but NOT NULL in target. Null values will violate target constraints."
                )

        # Generate summary
        result["summary"] = self._generate_summary(result)

        return result

    def _types_compatible(self, source_type: str, target_type: str) -> bool:
        """Check if two column types are compatible."""
        s_base = self._extract_base_type(source_type)
        t_base = self._extract_base_type(target_type)

        if s_base == t_base:
            return True

        # Check if they belong to the same type family
        for family_types in self.TYPE_FAMILIES.values():
            if s_base in family_types and t_base in family_types:
                return True

        return False

    def _extract_base_type(self, type_str: str) -> str:
        """Extract base type without length/precision specifiers."""
        # Remove NOT NULL, DEFAULT, etc.
        type_str = re.sub(r"\s+(NOT\s+NULL|NULL|DEFAULT\s+.+)$", "", type_str, flags=re.IGNORECASE)
        # Remove length/precision: VARCHAR(50) -> VARCHAR
        base = re.sub(r"\(.*\)", "", type_str).strip().upper()
        return base

    def _extract_length(self, type_str: str) -> Optional[int]:
        """Extract length from type like VARCHAR(50)."""
        match = re.search(r"\((\d+)\)", type_str)
        if match:
            return int(match.group(1))
        return None

    def _generate_summary(self, result: Dict[str, Any]) -> str:
        """Generate a human-readable summary of schema comparison."""
        parts = []
        parts.append(f"Schema Comparison: {result['source_table']} → {result['target_table']}")
        parts.append(f"Source columns: {result['source_column_count']}, Target columns: {result['target_column_count']}")
        parts.append(f"Overall compatibility: {'COMPATIBLE' if result['compatible'] else 'INCOMPATIBLE'}")
        parts.append(f"Pipeline impact: {result['pipeline_impact'].upper()}")

        if result["all_differences"]:
            parts.append(f"\nTotal differences found: {len(result['all_differences'])}")
            for diff in result["all_differences"]:
                parts.append(f"  [{diff['severity'].upper()}] {diff['description']}")

        if result["most_likely_cause_of_failure"]:
            parts.append(f"\nMost likely cause of failure: {result['most_likely_cause_of_failure']}")

        return "\n".join(parts)
