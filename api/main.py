"""
FastAPI endpoints to expose the pipeline investigation workflow.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import uuid
import asyncio

from workflow.graph import create_investigation_graph


app = FastAPI(
    title="Pipeline Failure Investigator API",
    description="Agentic ETL Pipeline Failure Investigator",
    version="1.0.0"
)

# In-memory storage for simple async job tracking
# In production, use Redis or database
jobs = {}

# Initialize workflow graph
graph = create_investigation_graph()


class InvestigationRequest(BaseModel):
    pipeline_id: str = Field(..., description="ID of the failed pipeline")
    failure_timestamp: str = Field(..., description="ISO timestamp of failure")
    logs: List[str] = Field(..., description="List of raw log lines")
    source_schema: Optional[Dict[str, Any]] = Field(None, description="Source schema definition")
    target_schema: Optional[Dict[str, Any]] = Field(None, description="Target schema definition")
    row_counts: Optional[Dict[str, int]] = Field(None, description="Row counts by stage")


class InvestigationResponse(BaseModel):
    job_id: str
    status: str
    message: str


def run_investigation_job(job_id: str, request: InvestigationRequest):
    """Background task to run the investigation."""
    try:
        jobs[job_id]["status"] = "running"
        
        # Prepare initial state
        initial_state = {
            "pipeline_id": request.pipeline_id,
            "failure_timestamp": request.failure_timestamp,
            "logs": request.logs,
            "source_schema": request.source_schema,
            "target_schema": request.target_schema,
            "row_counts": request.row_counts,
            "log_findings": None,
            "schema_findings": None,
            "data_quality_findings": None,
            "rca_data": None,
            "verification_result": None,
            "final_report_md": None,
            "final_report_json": None,
        }
        
        # Run workflow
        result = graph.invoke(initial_state)
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = result
        
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)


@app.post("/api/investigate", response_model=InvestigationResponse)
async def start_investigation(request: InvestigationRequest, background_tasks: BackgroundTasks):
    """Start an asynchronous pipeline investigation."""
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = {
        "status": "pending",
        "job_id": job_id
    }
    
    background_tasks.add_task(run_investigation_job, job_id, request)
    
    return InvestigationResponse(
        job_id=job_id,
        status="pending",
        message="Investigation started"
    )


@app.get("/api/investigate/{job_id}")
async def get_investigation_status(job_id: str):
    """Get the status and results of an investigation."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job_data = jobs[job_id]
    
    if job_data["status"] == "completed":
        result = job_data["result"]
        return {
            "job_id": job_id,
            "status": "completed",
            "report_md": result.get("final_report_md"),
            "report_json": result.get("final_report_json"),
            "rca_data": result.get("rca_data")
        }
        
    return {
        "job_id": job_id,
        "status": job_data["status"],
        "error": job_data.get("error")
    }


@app.post("/api/investigate/sync")
async def investigate_sync(request: InvestigationRequest):
    """Run an investigation synchronously and return results."""
    # Prepare initial state
    initial_state = {
        "pipeline_id": request.pipeline_id,
        "failure_timestamp": request.failure_timestamp,
        "logs": request.logs,
        "source_schema": request.source_schema,
        "target_schema": request.target_schema,
        "row_counts": request.row_counts,
    }
    
    try:
        # Run workflow
        result = graph.invoke(initial_state)
        
        return {
            "status": "completed",
            "report_md": result.get("final_report_md"),
            "report_json": result.get("final_report_json"),
            "rca_data": result.get("rca_data")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Investigation failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
