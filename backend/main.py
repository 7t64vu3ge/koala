from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from database import db
from models import UserSignup, UserSignin, UserSettings, UserResponse, Token, MessageCreate, ChatSessionResponse
from auth import get_password_hash, verify_password, create_access_token, get_current_user
from orchestrator import plan_task, merge_results, generate_chat_title, refine_plan, OrchestratorPlan, orchestration_graph, OrchestrationState
from bson import ObjectId
from datetime import datetime

app = FastAPI(
    title="Koala — AI Orchestrator API",
    description="Fullstack backend with Mongo and Orchestrator",
    version="0.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "🐨 Koala AI Orchestrator Backend is running."}

# --- AUTH ROUTES ---
@app.post("/auth/signup", response_model=UserResponse)
async def signup(user: UserSignup):
    if await db.users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_dict = user.model_dump()
    user_dict["hashed_password"] = get_password_hash(user_dict.pop("password"))
    user_dict["theme"] = "dark" # default theme
    
    result = await db.users.insert_one(user_dict)
    
    created_user = await db.users.find_one({"_id": result.inserted_id})
    if created_user:
        created_user["id"] = str(created_user.pop("_id"))
    return created_user

@app.post("/auth/signin", response_model=Token)
async def signin(user: UserSignin):
    db_user = await db.users.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = create_access_token(data={"sub": str(db_user["_id"])})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

# --- SETTINGS ROUTES ---
@app.put("/users/settings", response_model=UserResponse)
async def update_settings(settings: UserSettings, current_user: dict = Depends(get_current_user)):
    update_data = {k: v for k, v in settings.model_dump().items() if v is not None}
    if update_data:
        await db.users.update_one(
            {"_id": ObjectId(current_user["id"])},
            {"$set": update_data}
        )
    updated_user = await db.users.find_one({"_id": ObjectId(current_user["id"])})
    if updated_user:
        updated_user["id"] = str(updated_user.pop("_id"))
    return updated_user

# --- CHAT ROUTES ---
@app.get("/chat/sessions")
async def get_sessions(current_user: dict = Depends(get_current_user)):
    # Only return sessions that have messages
    cursor = db.chat_sessions.find({
        "user_id": current_user["id"],
        "messages": {"$not": {"$size": 0}}
    }).sort("created_at", -1)
    sessions = await cursor.to_list(length=100)
    for s in sessions:
        s["id"] = str(s.pop("_id"))
    return sessions

@app.post("/chat/sessions")
async def create_session(current_user: dict = Depends(get_current_user)):
    # We now handle creation inside send_message if it's a new chat,
    # but we'll keep this endpoint for compatibility, returning a dummy ID
    # that send_message will recognize.
    return {"id": "new"}

@app.delete("/chat/sessions")
async def clear_all_sessions(current_user: dict = Depends(get_current_user)):
    await db.chat_sessions.delete_many({"user_id": current_user["id"]})
    return {"message": "All sessions deleted"}

@app.post("/chat/sessions/{session_id}/messages")
async def send_message(session_id: str, message: MessageCreate, current_user: dict = Depends(get_current_user)):
    db_session_id = None
    
    if session_id == "new":
        new_session = {
            "user_id": current_user["id"],
            "title": "Generating title...",
            "created_at": datetime.utcnow(),
            "messages": []
        }
        result = await db.chat_sessions.insert_one(new_session)
        db_session_id = result.inserted_id
    else:
        db_session_id = ObjectId(session_id)
        session = await db.chat_sessions.find_one({"_id": db_session_id, "user_id": current_user["id"]})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

    user_msg = {
        "role": "user", 
        "content": message.content,
        "status": "completed"
    }
    await db.chat_sessions.update_one(
        {"_id": db_session_id},
        {"$push": {"messages": user_msg}}
    )
    
    session = await db.chat_sessions.find_one({"_id": db_session_id})
    
    # Initialize metadata if it's the first message
    if not session.get("metadata"):
        metadata = {
            "user_name": current_user.get("display_name", "User"),
            "topic": "General Discussion",
            "initialized": True
        }
        await db.chat_sessions.update_one(
            {"_id": db_session_id},
            {"$set": {"metadata": metadata}}
        )
        session["metadata"] = metadata

    if len(session.get("messages", [])) == 1:
        title = generate_chat_title(message.content)
        # Update both title and topic metadata for optimization
        await db.chat_sessions.update_one(
            {"_id": db_session_id},
            {"$set": {"title": title, "metadata.topic": title}}
        )
    
    # Logic: Check if we are REFINING a previous plan
    # If the second to last message is 'assistant' and has 'pending_approval' status
    messages = session.get("messages", [])
    last_plan_msg = None
    original_prompt = ""
    
    # Look back for the most recent user prompt and any pending plan
    for i in range(len(messages) - 2, -1, -1):
        msg = messages[i]
        if msg["role"] == "assistant" and msg.get("status") == "pending_approval" and not last_plan_msg:
            last_plan_msg = msg
        if msg["role"] == "user" and not original_prompt:
            # We want the prompt that triggered the first plan, not the current feedback
            if i > 0 and messages[i-1].get("role") != "assistant":
                 original_prompt = msg["content"]
            elif i == 0:
                 original_prompt = msg["content"]

    if not original_prompt:
        original_prompt = message.content

    # Context-Aware Upgrades: Build history for the planner
    history = []
    # Take up to the last 10 messages for context, excluding the latest user message
    # which is handled separately
    lookback = messages[:-1] # excludes the user message just added
    for m in lookback[-10:]:
        # Only pass completed messages to avoid confusing the planner with pending ones
        if m.get("status") == "completed":
            history.append({"role": m["role"], "content": m["content"]})
    
    plan = None
    if last_plan_msg and last_plan_msg.get("plan"):
        prev_plan = OrchestratorPlan(**last_plan_msg["plan"])
        plan = refine_plan(original_prompt, prev_plan, message.content, history=history, metadata=session.get("metadata"))
    else:
        plan = plan_task(message.content, history=history, metadata=session.get("metadata"))

    if not plan:
        raise HTTPException(status_code=500, detail="Failed to generate/refine plan.")
        
    plan_dict = plan.model_dump()
    ai_msg = {
        "role": "assistant",
        "content": "I've structured a plan for your request. Please review the subtasks below.",
        "status": "pending_approval",
        "subtasks": plan_dict["subtasks"],
        "plan": plan_dict
    }
        
    await db.chat_sessions.update_one(
        {"_id": db_session_id},
        {"$push": {"messages": ai_msg}}
    )
    
    session_out = await db.chat_sessions.find_one({"_id": db_session_id})
    if session_out:
        session_out["id"] = str(session_out.pop("_id"))
    return session_out

@app.post("/chat/sessions/{session_id}/messages/{message_index}/execute")
async def execute_confirmed_plan(session_id: str, message_index: int, current_user: dict = Depends(get_current_user)):
    db_session_id = ObjectId(session_id)
    # Always pull the absolute latest state from DB
    session = await db.chat_sessions.find_one({"_id": db_session_id, "user_id": current_user["id"]})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    messages = session.get("messages", [])
    if message_index >= len(messages):
        raise HTTPException(status_code=400, detail=f"Invalid message index: {message_index}. Session has {len(messages)} messages.")
        
    plan_msg = messages[message_index]
    
    # Debug info (will show in server logs)
    print(f"Executing plan at index {message_index}. Role: {plan_msg.get('role')}, Status: {plan_msg.get('status')}")
    
    if plan_msg.get("role") != "assistant":
        raise HTTPException(status_code=400, detail=f"Message at index {message_index} is not an assistant message (role is {plan_msg.get('role')}).")
        
    # Allow retrying if the status is pending_approval OR error
    if plan_msg.get("status") not in ["pending_approval", "error"] or not plan_msg.get("plan"):
        raise HTTPException(status_code=400, detail=f"Message at index {message_index} cannot be executed (status is {plan_msg.get('status')}).")
    
    # Mark as executing in the DB
    await db.chat_sessions.update_one(
        {"_id": db_session_id},
        {"$set": {f"messages.{message_index}.status": "executing"}}
    )
    
    try:
        # Re-fetch or use the plan metadata
        plan_data = plan_msg["plan"]
        plan = OrchestratorPlan(**plan_data)
        
        # Find the user prompt that triggered this plan
        original_prompt = ""
        for i in range(message_index - 1, -1, -1):
            if messages[i]["role"] == "user":
                original_prompt = messages[i]["content"]
                break
        
        # Build history for context-aware synthesis
        history = []
        for m in session.get("messages", [])[:message_index]:
            if m.get("status") == "completed":
                history.append({"role": m["role"], "content": m["content"]})

        print(f"🚀 Graph Execution started for prompt: {original_prompt[:50]}...")
        
        # Initialize Graph State
        initial_state = {
            "original_prompt": original_prompt,
            "metadata": session.get("metadata", {}),
            "history": history, # History built in send_message, but let's just use current session logic
            "plan": plan,
            "completed_results": {},
            "next_subtask_id": -1,
            "final_output": "",
            "error": ""
        }
        
        # Execute the Graph
        final_state = orchestration_graph.invoke(initial_state)
        
        if final_state.get("error"):
            raise Exception(final_state["error"])
            
        results = final_state["completed_results"]
        final_output = final_state["final_output"]
        
        # Update subtasks with results for UI feedback
        updated_subtasks = plan_msg["subtasks"]
        for st in updated_subtasks:
            st["result"] = results.get(st["id"], "(not executed)")
            
        # Atomically update the message to completed
        await db.chat_sessions.update_one(
            {"_id": db_session_id},
            {"$set": {
                f"messages.{message_index}.status": "completed",
                f"messages.{message_index}.content": final_output,
                f"messages.{message_index}.subtasks": updated_subtasks
            }}
        )
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ CRITICAL EXECUTION FAILURE at index {message_index}:\n{error_detail}")
        await db.chat_sessions.update_one(
            {"_id": db_session_id},
            {"$set": {f"messages.{message_index}.status": "error", f"messages.{message_index}.content": f"Execution failed: {str(e)}"}}
        )
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")
        
    # Return the fully updated session
    session_out = await db.chat_sessions.find_one({"_id": db_session_id})
    if session_out:
        session_out["id"] = str(session_out.pop("_id"))
    return session_out
