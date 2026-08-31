"""
Simple baseline implementation using a single GPT-4o call.
Used for comparison against the multi-agent system.
"""

import json
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
import os


class BaselineInvestigator:
    """A simple single-prompt baseline for comparison."""

    def __init__(self, model_name: str = "gpt-4o"):
        self.model = ChatOpenAI(
            model=model_name,
            temperature=0.2,
            api_key=os.getenv("OPENAI_API_KEY", "dummy"),
        )
        
        self.system_prompt = """
You are a helpful assistant. Analyze this pipeline failure and explain what went wrong.
Provide your response as a simple markdown report.
"""

    def investigate(self, data: Dict[str, Any]) -> str:
        """Run the simple baseline investigation."""
        
        # Prepare context (all raw data dumped in)
        context = []
        
        if data.get("logs"):
            context.append("Here are the pipeline logs:")
            context.append("\n".join(data["logs"]))
            
        if data.get("source_schema") and data.get("target_schema"):
            context.append("\nHere are the schemas:")
            context.append("Source:")
            context.append(json.dumps(data["source_schema"], indent=2))
            context.append("Target:")
            context.append(json.dumps(data["target_schema"], indent=2))
            
        if data.get("row_counts"):
            context.append("\nHere are the row counts by stage:")
            context.append(json.dumps(data["row_counts"], indent=2))
            
        prompt = f"""
{chr(10).join(context)}

What failed and why?
"""

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = self.model.invoke(messages)
            return response.content
        except Exception as e:
            return f"Baseline investigation failed: {str(e)}"
