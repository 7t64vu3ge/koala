import os
import json
from typing import List, Literal, Dict, Any, TypedDict, Annotated
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

# Load API keys
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── LangChain Chat Model ───────────────────────
chat_model = None
if GROQ_API_KEY and "your_" not in GROQ_API_KEY:
    chat_model = ChatGroq(
        api_key=GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile", # default model
        temperature=0.7,
        max_retries=2,
    )


# ── Pydantic models ──────────────────────────────────────────────────────────

class Subtask(BaseModel):
    id: int = Field(description="Unique ID for the subtask")
    description: str = Field(description="Detailed description of what needs to be done")
    assigned_model: Literal[
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "distil-whisper-large-v3-en"
    ] = Field(
        description="Assigned free AI model for this task. "
                    "Use 'llama-3.3-70b-versatile' for complex logical reasoning and coding. "
                    "Use 'llama-3.1-8b-instant' for fast, simple feedback or translations. "
                    "Use 'llama-3.1-70b-versatile' for alternative high-context reasoning. "
                    "Use 'distil-whisper-large-v3-en' only if audio transcription processing conceptually applies."
    )
    dependencies: List[int] = Field(description="List of IDs of subtasks that must be completed before this one")

    @field_validator("assigned_model", mode="before")
    @classmethod
    def map_deprecated_models(cls, v: Any) -> str:
        # Robustly map hallucinations or deprecated models to the current free tier
        MAPPING = {
            "mixtral-8x7b-32768": "llama-3.1-70b-versatile",
            "llama-3.1-70b-instant": "llama-3.1-8b-instant",
            "whisper-large-v3": "llama-3.3-70b-versatile", # Fallback for mis-assignments
            "whisper-large-v3-turbo": "llama-3.3-70b-versatile",
            "openai/gpt-oss-120b": "llama-3.3-70b-versatile",
            "openai/gpt-oss-20b": "llama-3.1-70b-versatile"
        }
        return MAPPING.get(v, v)

class OrchestratorPlan(BaseModel):
    plan_summary: str = Field(description="A brief summary of the overall plan")
    subtasks: List[Subtask] = Field(description="The list of decomposed subtasks")


# ── LangGraph State ──────────────────────────────────────────────────────────

class OrchestrationState(TypedDict):
    original_prompt: str
    metadata: Dict[str, Any]
    history: List[Dict[str, str]]
    plan: OrchestratorPlan
    completed_results: Dict[int, str]
    next_subtask_id: Annotated[int, "The ID of the subtask to execute next"]
    final_output: str
    error: str


# ── Planning ─────────────────────────────────────────────────────────────────

def plan_task(prompt: str, history: List[Dict] = None, metadata: Dict = None) -> OrchestratorPlan | None:
    """Uses LangChain to decompose a prompt into a subtask plan with session context."""
    if not chat_model:
        print("⚠️  Chat model not configured.")
        return None

    metadata = metadata or {}
    user_name = metadata.get("user_name", "User")
    topic = metadata.get("topic", "General Discussion")

    system_instruction = f'''
    You are an AI Orchestrator. Your job is to take a request from {user_name} 
    regarding the topic: '{topic}' and break it down into actionable subtasks.
    
    Maintain the existing context and optimize for the user's ultimate goal.

For each subtask:
1. Clearly describe the task.
2. Assign the most appropriate free AI model from the available options (STRICTLY USE ONLY THESE IDs):
   - 'llama-3.3-70b-versatile': Best for complex logic, multi-step reasoning, and deep coding.
   - 'llama-3.1-8b-instant', 'llama-3.1-70b-versatile': Good for general tasks and context-heavy logic.
   - 'distil-whisper-large-v3-en': For audio-related tasks.

   DO NOT use deprecated models like 'mixtral-8x7b-32768'.

3. Provide a detailed evaluation including:
   - Why this model is selected over others
   - Task complexity (low/medium/high)
   - Dependencies on previous subtasks
   - संभावित failure cases (edge cases or risks)
   - Performance considerations (latency vs quality trade-offs)

4. Suggest an alternative model (if applicable) and explain trade-offs.

After completing all subtasks:
5. Perform a global evaluation:
   - Identify bottlenecks in the workflow
   - Suggest optimisations (parallelisation, batching, etc.)
   - Highlight potential points of failure
   - Recommend improvements

6. Perform a self-critique:
   - What assumptions were made?
   - What might be incorrect or suboptimal?
   - How can the plan be made more robust?

Return the output as a structured JSON object according to the requested schema.
    '''

    try:
        schema = OrchestratorPlan.model_json_schema()
        messages = [
            SystemMessage(content=f"{system_instruction}\n\nYou MUST return a valid JSON object strictly matching this schema:\n{json.dumps(schema)}"),
        ]
        
        # Convert raw history to LangChain messages
        for msg in (history or []):
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        messages.append(HumanMessage(content=prompt))

        response = chat_model.with_structured_output(OrchestratorPlan).invoke(messages)
        return response
    except Exception as e:
        print(f"❌ Error during orchestration: {e}")
        return None


def generate_chat_title(prompt: str) -> str:
    """Uses LangChain to generate a concise 3-5 word title for a chat session."""
    if not chat_model:
        return "New Chat"
    
    system_instruction = "You are a helpful assistant that generates a concise, 3-5 word title for a chat session based on the user's first message. Respond ONLY with the title text, no quotes or extra characters."
    
    try:
        response = chat_model.invoke([
            SystemMessage(content=system_instruction),
            HumanMessage(content=prompt)
        ])
        return response.content.strip().strip('"').strip("'")
    except Exception as e:
        print(f"❌ Error generating title: {e}")
        return "New Chat"


def refine_plan(original_prompt: str, current_plan: OrchestratorPlan, feedback: str, history: List[Dict] = None, metadata: Dict = None) -> OrchestratorPlan | None:
    """Uses LangChain to refine an existing plan based on feedback and history."""
    if not chat_model:
        return None

    metadata = metadata or {}
    user_name = metadata.get("user_name", "User")
    topic = metadata.get("topic", "General Discussion")

    system_instruction = f'''
    You are an AI Orchestrator working with {user_name} on '{topic}'.
    A user has provided feedback on a plan you generated.
    
    ORIGINAL GOAL: {original_prompt}
    CURRENT PLAN: {current_plan.model_dump_json()}
    
    Your job is to update the subtasks to incorporate this feedback.
    '''

    try:
        schema = OrchestratorPlan.model_json_schema()
        messages = [
            SystemMessage(content=f"{system_instruction}\n\nYou MUST return a valid JSON object strictly matching this schema:\n{json.dumps(schema)}"),
        ]
        
        for msg in (history or []):
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
                
        messages.append(HumanMessage(content=f"Refine the plan based on my feedback: {feedback}"))

        response = chat_model.with_structured_output(OrchestratorPlan).invoke(messages)
        return response
    except Exception as e:
        print(f"❌ Error during plan refinement: {e}")
        return None


# ── Helper Functions ─────────────────────────────────────────────────────────

def _build_context_prompt(subtask: Subtask, completed_results: Dict[int, str]) -> str:
    """Builds a rich prompt that includes results from dependency subtasks."""
    context_parts = []
    for dep_id, dep_result in completed_results.items():
        if dep_id in subtask.dependencies:
            context_parts.append(f"[Result of Subtask #{dep_id}]:\n{dep_result}")

    context_block = "\n\n".join(context_parts)
    if context_block:
        prompt = (
            f"You are working on a step in a larger project.\n\n"
            f"Context from previous steps:\n{context_block}\n\n"
            f"Your current task:\n{subtask.description}"
        )
    else:
        prompt = subtask.description
    return prompt

def _execute_with_model(prompt: str, model: str) -> str:
    """Sends a prompt Using LangChain for cleaner subtask execution."""
    if not chat_model:
        return "⚠️  Chat model not configured."
    try:
        response = chat_model.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as e:
        return f"❌ Execution error: {e}"

def merge_results(original_prompt: str, plan: OrchestratorPlan, execution_results: Dict[int, str]) -> str:
    """Synthesizes final output from all results."""
    if not chat_model:
        return "⚠️  Chat model not configured."
    context_parts = []
    for subtask in plan.subtasks:
        result = execution_results.get(subtask.id, "(no result)")
        context_parts.append(f"--- Subtask [{subtask.id}]: {subtask.description} ---\n{result}")
    context_block = "\n\n".join(context_parts)
    try:
        system_instruction = (
            "You are an expert AI Synthesizer. Your job is to read a user's original goal, "
            "the subtasks that were planned to achieve this goal, and the actual raw output from those subtasks. "
            "synthesize them naturally into a final polished artifact or answer."
        )
        prompt_block = (
            f"USER'S ORIGINAL REQUEST: {original_prompt}\n\n"
            f"PLAN SUMMARY: {plan.plan_summary}\n\n"
            f"SUBTASK RESULTS:\n{context_block}\n\n"
            "Now, please synthesize the final response based on the above information."
        )
        response = chat_model.invoke([
            SystemMessage(content=system_instruction),
            HumanMessage(content=prompt_block)
        ])
        return response.content.strip()
    except Exception as e:
        return f"❌ Error during merge: {e}"

# ── LangGraph Nodes ──────────────────────────────────────────────────────────

def subtask_selector_node(state: OrchestrationState) -> Dict:
    """Nodes that decides which subtask to run next based on dependencies."""
    plan = state["plan"]
    results = state["completed_results"]
    
    # Simple logic: find the first subtask that isn't done and whose deps are satisfied
    for subtask in plan.subtasks:
        if subtask.id not in results:
            if all((dep_id in results for dep_id in subtask.dependencies)):
                return {"next_subtask_id": subtask.id}
    
    # If no subtask can be run, we are either done or stuck
    return {"next_subtask_id": -1}

def executor_node(state: OrchestrationState) -> Dict:
    """Executes the specific subtask identified by subtask_selector."""
    subtask_id = state["next_subtask_id"]
    if subtask_id == -1:
        return {}
        
    plan = state["plan"]
    results = state["completed_results"]
    
    # Find the subtask object
    subtask = next((s for s in plan.subtasks if s.id == subtask_id), None)
    if not subtask:
        return {"error": f"Subtask #{subtask_id} not found in plan."}

    print(f"\n▶ [{subtask.id}] 🤖 {subtask.assigned_model} | {subtask.description}")
    
    prompt = _build_context_prompt(subtask, results)
    result = _execute_with_model(prompt, subtask.assigned_model)
    
    # Update results
    new_results = results.copy()
    new_results[subtask.id] = result
    
    return {"completed_results": new_results}

def synthesizer_node(state: OrchestrationState) -> Dict:
    """Merges all results into the final output."""
    print("\n" + "=" * 50)
    print("🧠 MERGING RESULTS (Graph Mode)")
    print("=" * 50)
    
    final_response = merge_results(
        state["original_prompt"],
        state["plan"],
        state["completed_results"]
    )
    return {"final_output": final_response}

# ── Router Logic ─────────────────────────────────────────────────────────────

def route_next_subtask(state: OrchestrationState) -> Literal["executor", "synthesizer", END]:
    """Router that decides whether to continue execution or synthesize."""
    if state.get("error"):
        return END
    
    if state["next_subtask_id"] != -1:
        return "executor"
    else:
        # All subtasks likely completed, verify
        plan = state["plan"]
        results = state["completed_results"]
        if len(results) >= len(plan.subtasks):
            return "synthesizer"
        else:
            return END # Stuck (circular dependency)

# ── Graph Construction ───────────────────────────────────────────────────────

builder = StateGraph(OrchestrationState)

builder.add_node("selector", subtask_selector_node)
builder.add_node("executor", executor_node)
builder.add_node("synthesizer", synthesizer_node)

builder.add_edge(START, "selector")
builder.add_conditional_edges("selector", route_next_subtask)
builder.add_edge("executor", "selector")
builder.add_edge("synthesizer", END)

orchestration_graph = builder.compile()


# ── CLI Entry Point ──────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  🐨 Koala — Terminal AI Orchestrator")
    print("=" * 50)
    print("Breaks down complex tasks and executes them via specialized AI models.\n")
    print(f"  Planner & Executor Client: {'✅ ready' if chat_model else '❌ not configured'}")
    print()

    while True:
        try:
            user_prompt = input("\nEnter your prompt (or type 'exit' to quit):\n> ")
            if user_prompt.lower() in ["exit", "quit"]:
                print("Goodbye! 👋")
                break

            if not user_prompt.strip():
                continue

            # Step 1: Plan
            plan = plan_task(user_prompt)
            if not plan:
                continue

            print("\n" + "=" * 50)
            print("📋 ORCHESTRATOR PLAN")
            print("=" * 50)
            print(f"Summary: {plan.plan_summary}\n")
            print("Subtasks:")
            for task in plan.subtasks:
                deps = f" (depends on: {', '.join(map(str, task.dependencies))})" if task.dependencies else ""
                print(f"  [{task.id}] 🤖 {task.assigned_model} | {task.description}{deps}")
            print("=" * 50)

            # Step 2: Ask whether to execute
            choice = input("\n⚡ Execute this plan now? [y/N]: ").strip().lower()
            if choice == "y":
                # Execute using the Graph
                initial_state = {
                    "original_prompt": user_prompt,
                    "metadata": {},
                    "history": [],
                    "plan": plan,
                    "completed_results": {},
                    "next_subtask_id": -1,
                    "final_output": "",
                    "error": ""
                }
                
                final_state = orchestration_graph.invoke(initial_state)
                
                if final_state.get("error"):
                    print(f"\n❌ Execution Failed: {final_state['error']}")
                else:
                    print("\n" + "=" * 50)
                    print("📦 FINAL SYNTHESIS (Graph Generated)")
                    print("=" * 50)
                    print(final_state["final_output"])
            else:
                print("ℹ️  Plan saved — tasks were NOT executed.")

        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break


if __name__ == "__main__":
    main()
