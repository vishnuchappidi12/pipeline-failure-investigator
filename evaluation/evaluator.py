"""
Evaluation harness to run scenarios through baseline and agent system.
"""

import json
import glob
import time
from pathlib import Path
from typing import Dict, Any, List

from baseline.simple_baseline import BaselineInvestigator
from workflow.graph import create_investigation_graph
from evaluation.metrics import score_rca_accuracy, calculate_evidence_citation_rate, score_report_completeness


class Evaluator:
    def __init__(self):
        self.baseline = BaselineInvestigator()
        self.graph = create_investigation_graph()
        self.scenarios_dir = Path(__file__).parent.parent / "data" / "synthetic_scenarios"
        self.results_dir = Path(__file__).parent / "results"
        self.results_dir.mkdir(exist_ok=True)
        
    def load_scenarios(self) -> List[Dict[str, Any]]:
        scenarios = []
        for file in sorted(glob.glob(str(self.scenarios_dir / "*.json"))):
            with open(file, 'r') as f:
                scenarios.append(json.load(f))
        return scenarios

    def evaluate_baseline(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a scenario using the baseline."""
        start_time = time.time()
        
        # We don't have a structured parser for baseline, so we use LLM-as-a-judge 
        # or simple heuristic scoring for the baseline text output.
        # For simplicity in this implementation, we return placeholder structure.
        
        response = self.baseline.investigate({
            "logs": scenario["logs"],
            "source_schema": scenario.get("source_schema"),
            "target_schema": scenario.get("target_schema"),
            "row_counts": scenario.get("row_counts")
        })
        
        duration = time.time() - start_time
        
        # Naive scoring for baseline (in reality, use LLM judge for unstructured text)
        expected = scenario["expected_root_cause"].lower()
        score = 1.0 if expected in response.lower() else 0.0
        if score == 0.0:
            if "schema" in response.lower() and expected == "schema_drift": score = 0.5
            if "data" in response.lower() and expected == "data_quality": score = 0.5
            
        return {
            "time_seconds": duration,
            "accuracy_score": score,
            "evidence_rate": 0.0, # Baseline rarely cites properly
            "completeness": 0.3,  # Baseline is unstructured
            "raw_output": response
        }

    def evaluate_agent(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a scenario using the multi-agent system."""
        start_time = time.time()
        
        initial_state = {
            "pipeline_id": scenario["pipeline_id"],
            "failure_timestamp": scenario["failure_timestamp"],
            "logs": scenario["logs"],
            "source_schema": scenario.get("source_schema"),
            "target_schema": scenario.get("target_schema"),
            "row_counts": scenario.get("row_counts"),
        }
        
        result = self.graph.invoke(initial_state)
        duration = time.time() - start_time
        
        rca_data = result.get("rca_data", {})
        
        accuracy = score_rca_accuracy(
            scenario["expected_root_cause"],
            scenario["expected_failure_stage"],
            rca_data
        )
        
        evidence = calculate_evidence_citation_rate(rca_data)
        completeness = score_report_completeness(rca_data)
        
        return {
            "time_seconds": duration,
            "accuracy_score": accuracy,
            "evidence_rate": evidence,
            "completeness": completeness,
            "raw_output": result.get("final_report_json", "{}")
        }

    def run_full_evaluation(self):
        """Run all scenarios through both systems."""
        scenarios = self.load_scenarios()
        
        results = {
            "baseline": {},
            "agent": {}
        }
        
        for idx, scenario in enumerate(scenarios):
            print(f"Evaluating Scenario {idx+1}: {scenario['name']}")
            
            # Agent
            print("  Running Agent...")
            agent_res = self.evaluate_agent(scenario)
            results["agent"][scenario["scenario_id"]] = agent_res
            
            # Baseline (optional skip if just testing agent)
            # print("  Running Baseline...")
            # base_res = self.evaluate_baseline(scenario)
            # results["baseline"][scenario["scenario_id"]] = base_res
            
        with open(self.results_dir / "agent_results.generated.json", "w") as f:
            json.dump(results["agent"], f, indent=2)
            
        print("Evaluation complete!")
        return results

if __name__ == "__main__":
    evaluator = Evaluator()
    evaluator.run_full_evaluation()
