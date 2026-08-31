"""
Data Quality Agent — Analyzes row counts, nulls, duplicates.
"""

from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from tools.data_validator import DataValidator
import os
import json


class DataQualityAgent:
    """Agent that analyzes data quality metrics."""

    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.0):
        self.model = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        )
        self.validator = DataValidator()
        
        self.system_prompt = """
You are a data quality analysis specialist for ETL pipelines.

Given row count metrics across pipeline stages and other validation data, identify:
1. Where data loss occurred (stage with significant drop)
2. Percentage of records lost at each stage
3. Null rate violations
4. Duplicate record patterns

Calculate and evaluate:
- Data loss percentage between each stage
- Acceptable threshold: less than 0.1% loss is normal
- Greater than 1% loss requires explanation
- Greater than 10% loss is a critical failure

Output your analysis as a structured JSON object.
"""

    def analyze(self, row_counts: Dict[str, int], log_context: str = "") -> Dict[str, Any]:
        """Analyze data quality metrics and return structured findings."""
        # Pre-process using deterministic tool
        validation_results = self.validator.validate_row_counts(row_counts)
        quality_summary = self.validator.generate_quality_summary(row_counts)
        
        prompt = f"""
Analyze these data quality metrics to determine if a data issue caused the pipeline failure.

Validation Summary:
{quality_summary}

Raw Row Counts:
{json.dumps(row_counts, indent=2)}

Log Context (what failed):
{log_context}

Output format (JSON):
{{
  "stage_counts": {{"stage_name": count}},
  "data_loss_points": ["list of significant drops with percentages and stages"],
  "null_violations": ["any null violations inferred from context"],
  "duplicate_findings": ["any duplicate issues inferred from context"],
  "most_likely_cause_of_failure": "description or null",
  "confidence": "high|medium|low"
}}

Provide specific explanations connecting any data quality issues to the pipeline failure described in the log context.
Return ONLY valid JSON.
"""

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = self.model.invoke(messages)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:-3]
            elif content.startswith("```"):
                content = content[3:-3]
                
            analysis_result = json.loads(content)
            
            # Combine LLM analysis with deterministic validation
            return {
                **validation_results,
                "llm_analysis": analysis_result,
                "most_likely_cause_of_failure": analysis_result.get("most_likely_cause_of_failure") or validation_results.get("most_likely_cause_of_failure")
            }
        except Exception as e:
            # Fallback to just the validator output if LLM fails
            return validation_results
