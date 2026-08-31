"""
Schema Agent — Compares source and target schemas.
"""

from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from tools.schema_comparator import SchemaComparator
import os
import json


class SchemaAgent:
    """Agent that analyzes schema differences."""

    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.0):
        self.model = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        )
        self.comparator = SchemaComparator()
        
        self.system_prompt = """
You are a database schema analysis specialist.

Given source schema and target schema definitions and a deterministic diff, identify:
1. Columns present in source but missing in target
2. Columns present in target but missing in source
3. Data type mismatches between source and target
4. Nullable constraint differences
5. Primary key or index differences

For each difference found, assess:
- Whether it could cause a pipeline failure
- The likely impact severity (critical/warning/info)
- If it aligns with the reported failure point in logs

Output your analysis as a structured JSON object.
"""

    def analyze(self, source_schema: Dict[str, Any], target_schema: Dict[str, Any], log_context: str = "") -> Dict[str, Any]:
        """Analyze schemas and return structured findings."""
        # Pre-process using deterministic tool
        schema_diff = self.comparator.compare_schemas(source_schema, target_schema)
        
        prompt = f"""
Analyze these schemas and the computed differences to determine if schema drift caused the pipeline failure.

Computed Differences:
{json.dumps(schema_diff, indent=2)}

Log Context (what failed):
{log_context}

Output format (JSON):
{{
  "missing_in_target": ["list of issues with severity and explanation"],
  "missing_in_source": ["list of issues with severity and explanation"],
  "type_mismatches": ["list of issues with severity and explanation"],
  "constraint_differences": ["list of issues with severity and explanation"],
  "pipeline_impact": "critical|warning|none",
  "most_likely_cause_of_failure": "description or null",
  "confidence": "high|medium|low"
}}

Provide specific explanations connecting any schema differences to the pipeline failure described in the log context.
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
            
            # Combine LLM analysis with deterministic diff
            return {
                **schema_diff,
                "llm_analysis": analysis_result,
                "most_likely_cause_of_failure": analysis_result.get("most_likely_cause_of_failure") or schema_diff.get("most_likely_cause_of_failure")
            }
        except Exception as e:
            # Fallback to just the comparator output if LLM fails
            return schema_diff
