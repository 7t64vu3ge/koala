from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from orchestrator import plan_task

app = FastAPI(
    title="AI Orchestrator API",
    description="API for breaking down and managing AI tasks",
    version="0.1.0"
)

class PromptRequest(BaseModel):
    prompt: str

@app.get("/")
def read_root():
    return {"message": "Welcome to the AI Orchestrator API!"}

@app.post("/breakdown")
def breakdown_task(request: PromptRequest):
    """
    Takes a complex prompt and uses the AI Orchestrator to break it down 
    into subtasks assigned to specialized AI agents.
    """
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        
    plan = plan_task(request.prompt)
    if not plan:
        raise HTTPException(status_code=500, detail="Failed to generate plan. Please check API keys (GROQ_API_KEY) and logs.")
        
    return plan.model_dump()
