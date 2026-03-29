import os
import json
from typing import List, Literal
from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, Field

# Load API keys
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Configure Groq
client = None
if GROQ_API_KEY and "your_" not in GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)

class Subtask(BaseModel):
    id: int = Field(description="Unique ID for the subtask")
    description: str = Field(description="Detailed description of what needs to be done")
    assigned_agent: Literal["gemini", "llama"] = Field(
        description="Assigned AI agent. Use 'gemini' for creative tasks, writing, UX, etc. Use 'llama' for reasoning, logic, constraints, backend code, etc."
    )
    dependencies: List[int] = Field(description="List of IDs of subtasks that must be completed before this one")

class OrchestratorPlan(BaseModel):
    plan_summary: str = Field(description="A brief summary of the overall plan")
    subtasks: List[Subtask] = Field(description="The list of decomposed subtasks")

def plan_task(prompt: str) -> OrchestratorPlan | None:
    """Takes a user prompt, breaks it down into subtasks, and assigns an agent to each."""
    if not GROQ_API_KEY or "your_" in GROQ_API_KEY:
        print("Please configure your GROQ_API_KEY in the .env file.")
        return None
    
    if not client:
        return None

    system_instruction = (
        "You are an AI Orchestrator. Your job is to take a complex user request "
        "(such as a web dev project or a research request) and break it down into a logical "
        "sequence of actionable subtasks.\n"
        "Assign each subtask to the most appropriate AI agent:\n"
        "- 'gemini': Best for creative writing, ideation, design planning, CSS/UI/UX layouts.\n"
        "- 'llama': Best for logical reasoning, breaking down code architecture, data extraction, and heavy thinking.\n"
        "Return the output as a structured JSON object according to the requested schema."
    )
    
    print(f"\nOrchestrating task: '{prompt}'...")
    print("Thinking...")
    
    try:
        schema = OrchestratorPlan.model_json_schema()
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": f"{system_instruction}\n\nYou MUST return a valid JSON object strictly matching this schema:\n{json.dumps(schema)}"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        plan_data = json.loads(response.choices[0].message.content)
        return OrchestratorPlan(**plan_data)
    except Exception as e:
        print(f"Error during orchestration: {e}")
        return None

def main():
    print("=" * 50)
    print("Welcome to the Terminal AI Orchestrator!")
    print("=" * 50)
    print("This tool breaks down your complex tasks into manageable subtasks")
    print("and assigns them to specialized AI agents.\n")
    
    while True:
        try:
            user_prompt = input("\nEnter your prompt (or type 'exit' to quit): \n> ")
            if user_prompt.lower() in ['exit', 'quit']:
                print("Exiting orchestrator. Goodbye!")
                break
            
            if not user_prompt.strip():
                continue
            
            plan = plan_task(user_prompt)
            if plan:
                print("\n" + "=" * 50)
                print("ORCHESTRATOR PLAN GENERATED")
                print("=" * 50)
                print(f"Summary: {plan.plan_summary}\n")
                print("Subtasks:")
                for task in plan.subtasks:
                    deps = f" (Depends on: {', '.join(map(str, task.dependencies))})" if task.dependencies else ""
                    print(f"[{task.id}] Agent: {task.assigned_agent.upper().ljust(6)} | {task.description}{deps}")
                print("=" * 50)
                print("Note: Tasks have NOT been executed yet. This is just the breakdown.")
                print("=" * 50)
        except KeyboardInterrupt:
            print("\nExiting orchestrator. Goodbye!")
            break

if __name__ == "__main__":
    main()
