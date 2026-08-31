"""
Streamlit UI for the Pipeline Failure Investigator.
"""

import streamlit as st
import json
import os
import sys
import glob
import time
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from api.main import InvestigationRequest
from workflow.graph import create_investigation_graph
from baseline.simple_baseline import BaselineInvestigator

# Page config
st.set_page_config(
    page_title="ETL Pipeline Failure Investigator",
    page_icon="🔍",
    layout="wide"
)

# Initialize session state
if "scenarios" not in st.session_state:
    st.session_state.scenarios = {}
    scenario_files = glob.glob(str(Path(__file__).parent.parent / "data" / "synthetic_scenarios" / "*.json"))
    for file in sorted(scenario_files):
        with open(file, 'r') as f:
            data = json.load(f)
            st.session_state.scenarios[data["name"]] = data

if "current_scenario" not in st.session_state:
    st.session_state.current_scenario = None

# Sidebar
with st.sidebar:
    st.title("⚙️ Settings")
    
    api_key = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
        
    model = st.selectbox(
        "Model Selection",
        ["gpt-4o", "gpt-3.5-turbo", "claude-3-5-sonnet-20240620"]
    )
    
    mode = st.radio(
        "Investigation Mode",
        ["Full Agent", "Baseline only", "Compare"]
    )
    
    st.markdown("---")
    st.markdown("""
    ### About
    This agent automatically investigates ETL pipeline failures by:
    1. Parsing execution logs
    2. Comparing schemas
    3. Checking data quality
    4. Generating a Root Cause Analysis
    """)

# Main Content
st.title("🔍 ETL Pipeline Failure Investigator")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Investigate", "Load Scenario", "Evaluation", "Trajectories"])

with tab2:
    st.header("Load Synthetic Scenario")
    
    selected_scenario_name = st.selectbox(
        "Select a scenario to investigate:",
        ["-- Select a scenario --"] + list(st.session_state.scenarios.keys())
    )
    
    if selected_scenario_name != "-- Select a scenario --":
        scenario = st.session_state.scenarios[selected_scenario_name]
        st.session_state.current_scenario = scenario
        
        st.subheader("Scenario Details")
        st.markdown(f"**Description:** {scenario['description']}")
        st.markdown(f"**Expected Root Cause:** `{scenario['expected_root_cause']}`")
        
        st.info("Inputs have been loaded into the Investigate tab.")

with tab1:
    st.header("Investigation Inputs")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Pipeline Logs")
        default_logs = ""
        if st.session_state.current_scenario:
            default_logs = "\n".join(st.session_state.current_scenario["logs"])
            
        logs_text = st.text_area("Paste raw logs here", value=default_logs, height=300)
        
    with col2:
        st.subheader("Context (Optional)")
        
        default_source = "{}"
        default_target = "{}"
        default_counts = "{}"
        
        if st.session_state.current_scenario:
            default_source = json.dumps(st.session_state.current_scenario.get("source_schema", {}), indent=2)
            default_target = json.dumps(st.session_state.current_scenario.get("target_schema", {}), indent=2)
            default_counts = json.dumps(st.session_state.current_scenario.get("row_counts", {}), indent=2)
            
        st.write("Source Schema:")
        source_text = st.text_area("Source JSON", value=default_source, height=100)
        
        st.write("Target Schema:")
        target_text = st.text_area("Target JSON", value=default_target, height=100)
        
        st.write("Row Counts:")
        counts_text = st.text_area("Row Counts JSON", value=default_counts, height=100)

    if st.button("🚀 Investigate Failure", type="primary"):
        if not logs_text.strip():
            st.error("Please provide pipeline logs.")
            st.stop()
            
        if not api_key:
            st.error("Please provide an OpenAI API Key in the sidebar.")
            st.stop()
            
        # Parse inputs
        logs_list = logs_text.strip().split("\n")
        try:
            source_schema = json.loads(source_text) if source_text.strip() else None
            target_schema = json.loads(target_text) if target_text.strip() else None
            row_counts = json.loads(counts_text) if counts_text.strip() else None
        except json.JSONDecodeError:
            st.error("Invalid JSON provided in context fields.")
            st.stop()
            
        pipeline_id = "manual_input"
        failure_ts = "unknown"
        if st.session_state.current_scenario:
            pipeline_id = st.session_state.current_scenario.get("pipeline_id", pipeline_id)
            failure_ts = st.session_state.current_scenario.get("failure_timestamp", failure_ts)

        # Run Baseline if selected
        if mode in ["Baseline only", "Compare"]:
            st.subheader("🤖 Baseline Output (Single Prompt)")
            with st.spinner("Running simple baseline..."):
                start_time = time.time()
                baseline = BaselineInvestigator(model_name=model)
                baseline_result = baseline.investigate({
                    "logs": logs_list,
                    "source_schema": source_schema,
                    "target_schema": target_schema,
                    "row_counts": row_counts
                })
                baseline_time = time.time() - start_time
                
                st.markdown(f"*(Completed in {baseline_time:.2f} seconds)*")
                st.markdown(baseline_result)
                
        # Run Agent if selected
        if mode in ["Full Agent", "Compare"]:
            st.subheader("🕵️ Agentic Investigation Report")
            
            # Status container for streaming
            status_container = st.empty()
            
            with st.spinner("Initializing Agent Graph..."):
                start_time = time.time()
                graph = create_investigation_graph()
                
                initial_state = {
                    "pipeline_id": pipeline_id,
                    "failure_timestamp": failure_ts,
                    "logs": logs_list,
                    "source_schema": source_schema,
                    "target_schema": target_schema,
                    "row_counts": row_counts,
                }
                
                # Stream the steps
                for event in graph.stream(initial_state):
                    for node_name, state_update in event.items():
                        if node_name == "analyze_logs":
                            status_container.info("📄 Log Agent: Parsing logs and finding error point...")
                        elif node_name == "analyze_schema":
                            status_container.info("🔄 Schema Agent: Comparing source and target schemas...")
                        elif node_name == "analyze_data_quality":
                            status_container.info("📊 Data Quality Agent: Analyzing row counts and nulls...")
                        elif node_name == "generate_rca":
                            status_container.info("📝 RCA Agent: Synthesizing findings...")
                        elif node_name == "verify_and_format":
                            v_res = state_update.get("verification_result", {})
                            if v_res.get("passed"):
                                status_container.success("✅ Verification: Report is complete and actionable!")
                            else:
                                status_container.warning(f"⚠️ Verification Failed: {', '.join(v_res.get('missing_elements', []))}. Sending back to RCA Agent...")
                
                # Get final state
                final_state = event[list(event.keys())[0]] # Get state from last event
                if 'final_report_md' not in final_state:
                    # Fallback if streaming ended weirdly
                    final_state = graph.invoke(initial_state)
                    
                agent_time = time.time() - start_time
                status_container.empty() # Clear status
                
                st.markdown(f"*(Completed in {agent_time:.2f} seconds)*")
                st.markdown(final_state.get("final_report_md", "Report generation failed."))
                
                with st.expander("View Raw JSON Report"):
                    st.code(final_state.get("final_report_json", "{}"), language="json")

with tab3:
    st.header("Evaluation Results")
    st.markdown("Run the full evaluation harness to compare the baseline against the agent system across all 10 synthetic scenarios.")
    
    if st.button("Run Full Evaluation"):
        st.warning("This will take approximately 5-10 minutes and consume OpenAI credits. View the pre-computed results in the README instead.")

with tab4:
    st.header("Agent Trajectories")
    st.markdown("View execution traces in `trajectories/example_trajectory.md` after running the system.")
