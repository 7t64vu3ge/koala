import os
import json
import asyncio
from typing import List, Literal, Dict, Any, TypedDict
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

# Load API keys
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

chat_model = None
if GROQ_API_KEY and "your_" not in GROQ_API_KEY:
    chat_model = ChatGroq(
        api_key=GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile",
        temperature=0.7,
        max_retries=2,
    )


class Subtask(BaseModel):
    id: int = Field(description="Unique ID for the subtask")
    description: str = Field(description="Detailed description of what needs to be done")
    assigned_model: Literal[
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3-32b",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "whisper-large-v3",
        "whisper-large-v3-turbo"
    ] = Field(
        description="Assigned model for this task. "
                    "Use 'llama-3.3-70b-versatile' for complex logical reasoning and coding. "
                    "Use 'llama-3.1-8b-instant' for fast, simple or translation tasks. "
                    "Use 'openai/gpt-oss-120b' for the most demanding reasoning or long-context tasks. "
                    "Use 'openai/gpt-oss-20b' for balanced quality and speed. "
                    "Use 'qwen/qwen3-32b' for multilingual or alternative high-context reasoning. "
                    "Use 'meta-llama/llama-4-scout-17b-16e-instruct' for instruction-following and agentic tasks. "
                    "Use 'whisper-large-v3' or 'whisper-large-v3-turbo' only for audio transcription tasks."
    )
    dependencies: List[int] = Field(description="List of IDs of subtasks that must be completed before this one")

    @field_validator("assigned_model", mode="before")
    @classmethod
    def map_deprecated_models(cls, v: Any) -> str:

        MAPPING = {
            "mixtral-8x7b-32768": "qwen/qwen3-32b",
            "llama-3.1-70b-versatile": "openai/gpt-oss-20b",
            "llama-3.1-70b-instant": "llama-3.1-8b-instant",
            "distil-whisper-large-v3-en": "whisper-large-v3-turbo",
        }
        return MAPPING.get(v, v)

class OrchestratorPlan(BaseModel):
    plan_summary: str = Field(description="A brief summary of the overall plan")
    subtasks: List[Subtask] = Field(description="The list of decomposed subtasks")


def validate_plan(plan: OrchestratorPlan) -> List[str]:
    """Topological-sort check: returns a list of error strings, empty means valid."""
    errors = []
    ids = {s.id for s in plan.subtasks}

    # Check for dangling dependency references
    for subtask in plan.subtasks:
        for dep_id in subtask.dependencies:
            if dep_id not in ids:
                errors.append(f"Subtask #{subtask.id} depends on #{dep_id} which does not exist.")

    # Kahn's algorithm to detect cycles
    in_degree = {s.id: 0 for s in plan.subtasks}
    for subtask in plan.subtasks:
        for dep_id in subtask.dependencies:
            if dep_id in in_degree:
                in_degree[subtask.id] += 1

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for subtask in plan.subtasks:
            if node in subtask.dependencies:
                in_degree[subtask.id] -= 1
                if in_degree[subtask.id] == 0:
                    queue.append(subtask.id)

    if visited < len(plan.subtasks):
        errors.append("Plan contains a circular dependency and cannot be executed.")

    return errors


class OrchestrationState(TypedDict):
    original_prompt: str
    metadata: Dict[str, Any]
    history: List[Dict[str, str]]
    plan: OrchestratorPlan
    completed_results: Dict[int, str]
    final_output: str
    error: str


def plan_task(prompt: str, history: List[Dict] = None, metadata: Dict = None) -> OrchestratorPlan | None:
    """Uses LangChain to decompose a prompt into a subtask plan with session context."""
    if not chat_model:
        print("Chat model not configured.")
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
2. Assign the most appropriate model from the available options (STRICTLY USE ONLY THESE IDs):
   - 'llama-3.3-70b-versatile': Complex logic, multi-step reasoning, coding.
   - 'llama-3.1-8b-instant': Fast, simple tasks, translations.
   - 'openai/gpt-oss-120b': Most demanding reasoning or very long-context tasks.
   - 'openai/gpt-oss-20b': Balanced quality and speed.
   - 'qwen/qwen3-32b': Multilingual or alternative high-context reasoning.
   - 'meta-llama/llama-4-scout-17b-16e-instruct': Instruction-following and agentic tasks.
   - 'whisper-large-v3' or 'whisper-large-v3-turbo': Audio transcription only.

   DO NOT use deprecated models like 'mixtral-8x7b-32768', 'llama-3.1-70b-versatile', or 'distil-whisper-large-v3-en'.

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
        
        for msg in (history or []):
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        messages.append(HumanMessage(content=prompt))

        response = chat_model.with_structured_output(OrchestratorPlan).invoke(messages)
        return response
    except Exception as e:
        print(f"Error during orchestration: {e}")
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
        print(f"Error generating title: {e}")
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
        print(f"Error during plan refinement: {e}")
        return None



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

async def _execute_with_model_async(subtask: Subtask, completed_results: Dict[int, str]) -> tuple[int, str]:
    """Async execution of a single subtask against its assigned model."""
    if not GROQ_API_KEY:
        return subtask.id, "Chat model not configured."
    try:
        subtask_model = ChatGroq(
            api_key=GROQ_API_KEY,
            model_name=subtask.assigned_model,
            temperature=0.7,
            max_retries=2,
        )
        prompt = _build_context_prompt(subtask, completed_results)
        response = await subtask_model.ainvoke([HumanMessage(content=prompt)])
        return subtask.id, response.content.strip()
    except Exception as e:
        return subtask.id, f"Execution error: {e}"

def merge_results(original_prompt: str, plan: OrchestratorPlan, execution_results: Dict[int, str]) -> str:
    """Synthesizes final output from all results."""
    if not chat_model:
        return "Chat model not configured."
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
        return f"Error during merge: {e}"


async def astream_merge_results(original_prompt: str, plan: OrchestratorPlan, execution_results: Dict[int, str]):
    """Synthesizes final output from all results and streams the tokens in real time."""
    if not chat_model:
        yield "Chat model not configured."
        return
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
        async for chunk in chat_model.astream([
            SystemMessage(content=system_instruction),
            HumanMessage(content=prompt_block)
        ]):
            if chunk.content:
                yield chunk.content
    except Exception as e:
        yield f"Error during merge: {e}"


async def parallel_executor_node(state: OrchestrationState) -> Dict:
    """Collects all ready subtasks in this wave and executes them concurrently."""
    plan = state["plan"]
    results = state["completed_results"]

    ready = [
        s for s in plan.subtasks
        if s.id not in results and all(dep in results for dep in s.dependencies)
    ]

    if not ready:
        return {}

    print(f"\n Parallel wave: {[s.id for s in ready]}")
    for s in ready:
        print(f"[{s.id}] 🤖 {s.assigned_model} | {s.description}")

    wave_results = await asyncio.gather(*[_execute_with_model_async(s, results) for s in ready])

    new_results = results.copy()
    for subtask_id, result in wave_results:
        new_results[subtask_id] = result

    return {"completed_results": new_results}

def synthesizer_node(state: OrchestrationState) -> Dict:
    """Merges all results into the final output."""
    print("\n" + "=" * 50)
    print("MERGING RESULTS (Graph Mode)")
    print("=" * 50)
    
    final_response = merge_results(
        state["original_prompt"],
        state["plan"],
        state["completed_results"]
    )
    return {"final_output": final_response}



def route_after_wave(state: OrchestrationState) -> Literal["parallel_executor", "synthesizer", END]:
    """Routes to another wave, synthesizer, or END (stuck = circular dep caught by validate_plan)."""
    if state.get("error"):
        return END
    plan = state["plan"]
    results = state["completed_results"]
    if len(results) >= len(plan.subtasks):
        return "synthesizer"
    has_ready = any(
        s.id not in results and all(dep in results for dep in s.dependencies)
        for s in plan.subtasks
    )
    return "parallel_executor" if has_ready else END


builder = StateGraph(OrchestrationState)

builder.add_node("parallel_executor", parallel_executor_node)
builder.add_node("synthesizer", synthesizer_node)

builder.add_edge(START, "parallel_executor")
builder.add_conditional_edges("parallel_executor", route_after_wave)
builder.add_edge("synthesizer", END)

orchestration_graph = builder.compile()


def main():
    print("=" * 50)
    print("Koala — Terminal AI Orchestrator")
    print("=" * 50)
    print("Breaks down complex tasks and executes them via specialized AI models.\n")
    print(f"  Planner & Executor Client: {'ready' if chat_model else 'not configured'}")
    print()

    while True:
        try:
            user_prompt = input("\nEnter your prompt (or type 'exit' to quit):\n> ")
            if user_prompt.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            if not user_prompt.strip():
                continue

            # Step 1: Plan
            plan = plan_task(user_prompt)
            if not plan:
                continue

            # Step 1b: Validate plan before offering execution
            plan_errors = validate_plan(plan)
            if plan_errors:
                print("\n Plan validation failed — cannot execute:")
                for err in plan_errors:
                    print(f"   • {err}")
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
            choice = input("\nExecute this plan now? [y/N]: ").strip().lower()
            if choice == "y":
                # Execute using the Graph
                initial_state = {
                    "original_prompt": user_prompt,
                    "metadata": {},
                    "history": [],
                    "plan": plan,
                    "completed_results": {},
                    "final_output": "",
                    "error": ""
                }
                
                final_state = orchestration_graph.invoke(initial_state)
                
                if final_state.get("error"):
                    print(f"\nExecution Failed: {final_state['error']}")
                else:
                    print("\n" + "=" * 50)
                    print("FINAL SYNTHESIS (Graph Generated)")
                    print("=" * 50)
                    print(final_state["final_output"])
            else:
                print("Plan saved — tasks were NOT executed.")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
