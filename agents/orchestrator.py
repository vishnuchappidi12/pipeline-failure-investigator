"""
Orchestrator Agent — Coordinates the investigation workflow.
"""

from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
import os
import json


class OrchestratorAgent:
    """Agent that coordinates the investigation and decides next steps."""

    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.1):
        self.model = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        )
        
        self.system_prompt = """
You are the master orchestrator for an ETL pipeline failure investigation system.

Your job is to review the current state of the investigation and decide what to do next.
Available agents to route to:
- log_agent: Always run this first to parse logs and find the error point
- schema_agent: Run if logs suggest schema drift, missing columns, or type mismatches
- data_quality_agent: Run if logs suggest row count drops, null violations, or duplicate records
- rca_agent: Run to synthesize all findings into a final report (always run last)
- FINISH: Return this when the RCA report is complete and verified

You must decide the most logical next step based on the findings so far.
"""

    def decide_next_step(self, state: Dict[str, Any]) -> str:
        """Decide the next agent to route to based on the current state."""
        
        # State information to help decision
        has_logs = bool(state.get("logs"))
        has_schema = bool(state.get("source_schema")) and bool(state.get("target_schema"))
        has_row_counts = bool(state.get("row_counts"))
        
        log_findings = state.get("log_findings", {})
        schema_findings = state.get("schema_findings", {})
        dq_findings = state.get("data_quality_findings", {})
        rca_data = state.get("rca_data", {})
        verification = state.get("verification_result", {})
        
        # Logic rules (could be handled purely by LLM, but adding explicit routing for reliability)
        if not log_findings and has_logs:
            return "log_agent"
            
        if rca_data and verification.get("passed", False):
            return "FINISH"
            
        if rca_data and not verification.get("passed", True):
            # Failed verification, need to re-run RCA
            return "rca_agent"
            
        # If we have log findings but haven't run specialist agents yet
        prompt = f"""
Review the current investigation state and decide the next step.

State:
- Log analysis completed: {bool(log_findings)}
- Schema analysis completed: {bool(schema_findings)}
- Data quality analysis completed: {bool(dq_findings)}
- RCA completed: {bool(rca_data)}
- Has schema data available: {has_schema}
- Has row count data available: {has_row_counts}

Log Findings Summary:
{json.dumps(log_findings.get('log_analysis', {}), indent=2) if log_findings else 'None'}

Available next steps:
- "schema_agent": If error implies schema drift, missing columns, or type mismatch, AND schema data is available
- "data_quality_agent": If error implies data loss, row counts, null constraints, or duplicates, AND row count data is available
- "rca_agent": If we have gathered enough evidence and are ready to write the report

Return ONLY the string of the next step to take. No other text.
"""

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = self.model.invoke(messages)
            content = response.content.strip().lower()
            
            valid_routes = ["schema_agent", "data_quality_agent", "rca_agent", "log_agent", "FINISH"]
            for route in valid_routes:
                if route in content:
                    return route
                    
            # Default fallback
            return "rca_agent" if log_findings else "log_agent"
        except Exception:
            # Fallback routing
            return "rca_agent"
