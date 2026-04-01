import os
import json
from typing import List, Literal, Dict
from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, Field

# Load API keys
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── Groq client (used for planning + execution) ───────────────────────
groq_client = None
if GROQ_API_KEY and "your_" not in GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)


# ── Pydantic models ──────────────────────────────────────────────────────────

class Subtask(BaseModel):
    id: int = Field(description="Unique ID for the subtask")
    description: str = Field(description="Detailed description of what needs to be done")
    assigned_model: Literal[
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "whisper-large-v3",
        "whisper-large-v3-turbo"
    ] = Field(
        description="Assigned AI model for this task. "
                    "Use 'llama-3.1-8b-instant' or 'llama-3.3-70b-versatile' for standard logical reasoning. "
                    "Use 'openai/gpt-oss-120b' or 'openai/gpt-oss-20b' for highly demanding and creative coding tasks. "
                    "Use 'whisper-large-v3' or 'whisper-large-v3-turbo' only if audio transcription processing conceptually applies."
    )
    dependencies: List[int] = Field(description="List of IDs of subtasks that must be completed before this one")

class OrchestratorPlan(BaseModel):
    plan_summary: str = Field(description="A brief summary of the overall plan")
    subtasks: List[Subtask] = Field(description="The list of decomposed subtasks")


# ── Planning ─────────────────────────────────────────────────────────────────

def plan_task(prompt: str) -> OrchestratorPlan | None:
    """Uses Groq to decompose a user prompt into an ordered subtask plan."""
    if not groq_client:
        print("⚠️  Please configure your GROQ_API_KEY in the .env file.")
        return None

    system_instruction = (
        "You are an AI Orchestrator. Your job is to take a complex user request "
        "(such as a web dev project or a research request) and break it down into a logical "
        "sequence of actionable subtasks.\n"
        "Assign each subtask to the most appropriate AI model from the available options:\n"
        "- 'llama-3.1-8b-instant', 'llama-3.3-70b-versatile': Good for logic and reasoning.\n"
        "- 'openai/gpt-oss-120b', 'openai/gpt-oss-20b': Best for deep coding and complex creative workloads.\n"
        "- 'whisper-large-v3', 'whisper-large-v3-turbo': Specialize in audio processing/transcription logic if necessary.\n"
        "Return the output as a structured JSON object according to the requested schema."
    )

    print(f"\n🔍 Orchestrating task: '{prompt}'...")
    print("🤔 Thinking...")

    try:
        schema = OrchestratorPlan.model_json_schema()
        response = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{system_instruction}\n\n"
                        f"You MUST return a valid JSON object strictly matching this schema:\n{json.dumps(schema)}"
                    )
                },
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        plan_data = json.loads(response.choices[0].message.content)
        return OrchestratorPlan(**plan_data)
    except Exception as e:
        print(f"❌ Error during orchestration: {e}")
        return None


# ── Execution ────────────────────────────────────────────────────────────────

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
    """Sends a prompt using the configured Groq client to the specified model."""
    if not groq_client:
        return "⚠️  GROQ_API_KEY not configured — skipping execution."
    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Execution error with {model}: {e}"


def execute_plan(plan: OrchestratorPlan) -> Dict[int, str]:
    """
    Executes all subtasks in dependency order.
    Returns a dict mapping subtask ID → agent response.
    """
    results: Dict[int, str] = {}
    remaining = list(plan.subtasks)

    print("\n" + "=" * 50)
    print("🚀 EXECUTING PLAN")
    print("=" * 50)

    max_iterations = len(remaining) * len(remaining) + 1  # guard against circular deps
    iteration = 0

    while remaining and iteration < max_iterations:
        iteration += 1
        progress_made = False

        for subtask in list(remaining):
            # Check all dependencies are satisfied
            if all(dep_id in results for dep_id in subtask.dependencies):
                print(f"\n▶ [{subtask.id}] 🤖 {subtask.assigned_model} | {subtask.description}")
                print("   Working...")

                prompt = _build_context_prompt(subtask, results)
                result = _execute_with_model(prompt, subtask.assigned_model)

                results[subtask.id] = result
                remaining.remove(subtask)
                progress_made = True

                print(f"   ✅ Done ({len(result)} chars)")

        if not progress_made:
            print("⚠️  Circular dependency detected — stopping execution.")
            break

    return results


# ── CLI Entry Point ──────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  🐨 Koala — Terminal AI Orchestrator")
    print("=" * 50)
    print("Breaks down complex tasks and executes them via specialized AI models.\n")
    print(f"  Planner & Executor Client: {'✅ ready' if groq_client else '❌ not configured'}")
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
                results = execute_plan(plan)

                print("\n" + "=" * 50)
                print("📦 FINAL RESULTS")
                print("=" * 50)
                for task in plan.subtasks:
                    result_text = results.get(task.id, "(not executed)")
                    print(f"\n── Subtask [{task.id}]: {task.description}")
                    print(result_text)
                print("\n" + "=" * 50)
            else:
                print("ℹ️  Plan saved — tasks were NOT executed.")

        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break


if __name__ == "__main__":
    main()
