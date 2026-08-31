"""
Log Analysis Agent — Parses logs to find exact failure point.
"""

from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from tools.log_parser import LogParser
import os
import json


class LogAnalysisAgent:
    """Agent that analyzes pipeline logs to identify failures."""

    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.0):
        self.model = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        )
        self.parser = LogParser()
        
        self.system_prompt = """
You are a log analysis specialist for ETL data pipelines.

Given structured pipeline execution logs and a parsed summary, you must identify:
1. The exact timestamp when the failure occurred
2. The pipeline stage where it failed (extract|transform|load|validation)
3. The specific step within that stage
4. The error message and error type
5. Any preceding warning messages that indicated the failure

Output your analysis as a structured JSON object.
"""

    def analyze(self, logs: List[str]) -> Dict[str, Any]:
        """Analyze logs and return structured findings."""
        # Pre-process logs using our deterministic tool
        parsed_summary = self.parser.get_error_summary(logs)
        row_counts = self.parser.extract_row_counts_from_logs(logs)
        
        prompt = f"""
Analyze these pipeline logs to find the exact failure point.

Parsed Summary:
{parsed_summary}

Raw Logs (last 20 lines):
{chr(10).join(logs[-20:]) if len(logs) > 20 else chr(10).join(logs)}

Output format (JSON):
{{
  "failure_timestamp": "ISO timestamp",
  "failed_stage": "extract|transform|load|validation",
  "failed_step": "specific step name",
  "error_type": "category of error",
  "error_message": "exact error text",
  "preceding_warnings": ["list of warnings before failure"],
  "confidence": "high|medium|low",
  "analysis_summary": "Brief 1-2 sentence explanation of what went wrong based on logs"
}}

Be precise. Quote directly from the logs. Do not infer beyond what the log evidence supports.
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
            
            return {
                "log_analysis": analysis_result,
                "parsed_summary": parsed_summary,
                "row_counts": row_counts
            }
        except Exception as e:
            # Fallback to just the parser output if LLM fails
            return {
                "log_analysis": {
                    "error_message": f"Failed to parse with LLM: {str(e)}",
                    "confidence": "low"
                },
                "parsed_summary": parsed_summary,
                "row_counts": row_counts
            }
