from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from orchestrator import plan_task, execute_plan

app = FastAPI(
    title="Koala — AI Orchestrator API",
    description="Plans and executes complex tasks via specialized AI models.",
    version="0.2.0"
)

class PromptRequest(BaseModel):
    prompt: str
    execute: bool = False  # if True, also run the subtasks after planning


@app.get("/")
def read_root():
    return {"message": "🐨 Koala AI Orchestrator is running. POST /breakdown to start."}


@app.post("/breakdown")
def breakdown_task(request: PromptRequest):
    """
    Takes a complex prompt, breaks it into subtasks, and optionally executes them.
    - `execute: false` (default) → returns the plan only
    - `execute: true`            → plans + runs each subtask via its assigned agent
    """
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    plan = plan_task(request.prompt)
    if not plan:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate plan. Check GROQ_API_KEY and server logs."
        )

    response = plan.model_dump()

    if request.execute:
        results = execute_plan(plan)
        # Attach results to each subtask in the response
        for subtask in response["subtasks"]:
            subtask["result"] = results.get(subtask["id"], "(not executed)")

    return response
