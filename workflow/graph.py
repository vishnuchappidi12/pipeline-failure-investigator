"""
LangGraph workflow for the Pipeline Investigation system.
"""

from typing import Dict, Any, List, TypedDict, Optional
from langgraph.graph import StateGraph, END
from tools.report_generator import ReportGenerator
from agents.orchestrator import OrchestratorAgent
from agents.log_analysis_agent import LogAnalysisAgent
from agents.schema_agent import SchemaAgent
from agents.data_quality_agent import DataQualityAgent
from agents.rca_agent import RcaAgent


class InvestigationState(TypedDict):
    """State for the pipeline investigation workflow."""
    pipeline_id: str
    failure_timestamp: str
    logs: List[str]
    source_schema: Optional[Dict[str, Any]]
    target_schema: Optional[Dict[str, Any]]
    row_counts: Optional[Dict[str, int]]
    
    # Findings
    log_findings: Optional[Dict[str, Any]]
    schema_findings: Optional[Dict[str, Any]]
    data_quality_findings: Optional[Dict[str, Any]]
    rca_data: Optional[Dict[str, Any]]
    
    # Verification and Reports
    verification_result: Optional[Dict[str, Any]]
    final_report_md: Optional[str]
    final_report_json: Optional[str]
    rca_retries: Optional[int]


def create_investigation_graph():
    """Create and compile the LangGraph workflow."""
    
    # Initialize agents and tools
    orchestrator = OrchestratorAgent()
    log_agent = LogAnalysisAgent()
    schema_agent = SchemaAgent()
    dq_agent = DataQualityAgent()
    rca_agent = RcaAgent()
    report_gen = ReportGenerator()
    
    # Node functions
    def analyze_logs(state: InvestigationState) -> Dict:
        findings = log_agent.analyze(state["logs"])
        return {"log_findings": findings}
        
    def analyze_schema(state: InvestigationState) -> Dict:
        findings = schema_agent.analyze(
            state["source_schema"], 
            state["target_schema"],
            log_context=str(state.get("log_findings", {}))
        )
        return {"schema_findings": findings}
        
    def analyze_data_quality(state: InvestigationState) -> Dict:
        findings = dq_agent.analyze(
            state["row_counts"],
            log_context=str(state.get("log_findings", {}))
        )
        return {"data_quality_findings": findings}
        
    def generate_rca(state: InvestigationState) -> Dict:
        feedback = ""
        if state.get("verification_result") and not state["verification_result"].get("passed"):
            feedback = "\n".join(state["verification_result"].get("missing_elements", []))
            
        rca = rca_agent.synthesize(state, feedback)
        retries = state.get("rca_retries", 0) + 1
        return {"rca_data": rca, "rca_retries": retries}
        
    def verify_and_format(state: InvestigationState) -> Dict:
        rca_data = state["rca_data"]
        
        # Verify completeness
        verification = report_gen.verify_report_completeness(rca_data)
        
        # If passed or if we hit the max retries, generate final reports
        if verification["passed"] or state.get("rca_retries", 0) >= 3:
            md_report = report_gen.generate_markdown_report(rca_data)
            json_report = report_gen.generate_json_report(rca_data)
            return {
                "verification_result": verification,
                "final_report_md": md_report,
                "final_report_json": json_report
            }
        
        # If failed and retries left, just update verification result so orchestrator can route back to RCA
        return {"verification_result": verification}
        
    # Routing function
    def decide_next_node(state: InvestigationState) -> str:
        decision = orchestrator.decide_next_step(state)
        
        # Map orchestrator decisions to node names
        routes = {
            "log_agent": "analyze_logs",
            "schema_agent": "analyze_schema",
            "data_quality_agent": "analyze_data_quality",
            "rca_agent": "generate_rca",
            "FINISH": END
        }
        
        return routes.get(decision, "generate_rca")
        
    def verify_routing(state: InvestigationState) -> str:
        """Route from verify node back to RCA if failed, or END if passed."""
        if state.get("verification_result", {}).get("passed", False):
            return END
        if state.get("rca_retries", 0) >= 3:
            return END
        return "generate_rca"
        
    # Build graph
    workflow = StateGraph(InvestigationState)
    
    # Add nodes
    workflow.add_node("analyze_logs", analyze_logs)
    workflow.add_node("analyze_schema", analyze_schema)
    workflow.add_node("analyze_data_quality", analyze_data_quality)
    workflow.add_node("generate_rca", generate_rca)
    workflow.add_node("verify_and_format", verify_and_format)
    
    # Add edges
    workflow.set_entry_point("analyze_logs")
    
    # From analyze_logs, orchestrator decides
    workflow.add_conditional_edges("analyze_logs", decide_next_node)
    
    # From schema/dq agents, go to RCA
    workflow.add_edge("analyze_schema", "generate_rca")
    workflow.add_edge("analyze_data_quality", "generate_rca")
    
    # From RCA, always verify
    workflow.add_edge("generate_rca", "verify_and_format")
    
    # From verify, check if passed
    workflow.add_conditional_edges("verify_and_format", verify_routing)
    
    return workflow.compile()
