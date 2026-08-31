# Reproduction Guide

This guide will walk you through setting up and running the Agentic ETL Pipeline Failure Investigator from a clean environment.

## Prerequisites
- Python 3.11+
- Docker and docker-compose (optional, for containerized run)
- An OpenAI API Key

## Option 1: Run with Docker Compose (Recommended)

1. Clone the repository and navigate to the root directory.
2. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
3. Add your OpenAI API key to the `.env` file:
   ```
   OPENAI_API_KEY=sk-your-actual-api-key
   ```
4. Build and run the containers:
   ```bash
   docker-compose up --build
   ```
5. Open your browser and navigate to `http://localhost:8501` to access the UI.

## Option 2: Run Locally (Python Virtual Environment)

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your API key:
   ```bash
   export OPENAI_API_KEY="sk-your-actual-api-key"
   ```
4. Run the Streamlit UI:
   ```bash
   streamlit run ui/app.py
   ```

## Running the Evaluation Harness

To reproduce the exact metrics shown in the README, you can run the evaluation harness directly.

1. Ensure your virtual environment is active and `OPENAI_API_KEY` is set.
2. Set the PYTHONPATH to the project root:
   ```bash
   export PYTHONPATH=$(pwd)  # On Windows: set PYTHONPATH=%cd%
   ```
3. Run the evaluator:
   ```bash
   python evaluation/evaluator.py
   ```
   
This will process all 10 synthetic scenarios in `data/synthetic_scenarios/` through both the baseline and the agent system, scoring the results and saving them to `evaluation/results/agent_results.generated.json`.

**Note:** Running the full evaluation requires calling the OpenAI API for all 10 scenarios (often multiple times per scenario due to the multi-agent orchestration). This will take ~5-10 minutes and consume a small amount of API credits.

## Expected Output

When running the UI and loading Scenario 01 (Schema Drift):
1. The orchestrator will route to the Log Agent.
2. The Log Agent will identify a failure at the `LOAD` stage due to a missing column `customer_tier`.
3. The orchestrator will route to the Schema Agent.
4. The Schema Agent will confirm that `customer_tier` exists in the source but not the target schema, and note the `NOT NULL` constraint.
5. The orchestrator will route to the RCA Agent.
6. The RCA Agent will synthesize a report.
7. The Verification Layer will check the report. If successful, the final markdown report is displayed to the user within ~45 seconds.
