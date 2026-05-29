from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from database import db
from models import UserSignup, UserSignin, UserSettings, UserResponse, Token, MessageCreate, ChatSessionResponse
from auth import get_password_hash, verify_password, create_access_token, get_current_user
from orchestrator import plan_task, generate_chat_title, refine_plan, validate_plan, merge_results, astream_merge_results, OrchestratorPlan, _execute_with_model_async
from bson import ObjectId
from datetime import datetime
import asyncio
import json

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
            # Debug: check if session exists at all (regardless of user_id)
            orphan = await db.chat_sessions.find_one({"_id": db_session_id})
            if orphan:
                print(f"⚠️  Session {session_id} exists but user_id mismatch: "
                      f"stored={orphan.get('user_id')!r} vs request={current_user['id']!r}")
                raise HTTPException(status_code=403, detail="Not authorized to access this session")
            else:
                print(f"❌ Session {session_id} does not exist in the database at all.")
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

    plan_errors = validate_plan(plan)
    if plan_errors:
        raise HTTPException(status_code=422, detail={"validation_errors": plan_errors})
        
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

async def _get_user_from_token_query(token: str = Query(...)):
    """Auth dependency for SSE endpoint — reads token from query param since EventSource can't set headers."""
    from auth import get_current_user
    from fastapi.security import OAuth2PasswordBearer
    # Reuse get_current_user by faking the dependency manually
    import jwt
    from auth import SECRET_KEY, ALGORITHM
    from bson import ObjectId
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    user["id"] = str(user.pop("_id"))
    return user


@app.get("/chat/sessions/{session_id}/messages/{message_index}/execute/stream")
async def execute_confirmed_plan_stream(session_id: str, message_index: int, current_user: dict = Depends(_get_user_from_token_query)):
    db_session_id = ObjectId(session_id)
    session = await db.chat_sessions.find_one({
        "_id": db_session_id,
        "user_id": current_user["id"]
    })
    if not session:
        session = await db.chat_sessions.find_one({"_id": db_session_id})
        if session and str(session.get("user_id")) != str(current_user["id"]):
            raise HTTPException(status_code=403, detail="Not authorized to access this session")
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

    messages = session.get("messages", [])
    if message_index >= len(messages):
        raise HTTPException(status_code=400, detail=f"Invalid message index: {message_index}.")

    plan_msg = messages[message_index]
    if plan_msg.get("role") != "assistant":
        raise HTTPException(status_code=400, detail="Target message is not an assistant message.")
    if plan_msg.get("status") not in ["pending_approval", "error"] or not plan_msg.get("plan"):
        raise HTTPException(status_code=400, detail=f"Message cannot be executed (status: {plan_msg.get('status')}).")

    plan = OrchestratorPlan(**plan_msg["plan"])
    original_prompt = ""
    for i in range(message_index - 1, -1, -1):
        if messages[i]["role"] == "user":
            original_prompt = messages[i]["content"]
            break

    await db.chat_sessions.update_one(
        {"_id": db_session_id},
        {"$set": {f"messages.{message_index}.status": "executing"}}
    )

    async def event_stream():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        completed_results: dict = {}
        all_subtasks = {s.id: s for s in plan.subtasks}
        remaining = set(all_subtasks.keys())

        try:
            while remaining:
                ready = [
                    all_subtasks[sid] for sid in remaining
                    if all(dep in completed_results for dep in all_subtasks[sid].dependencies)
                ]
                if not ready:
                    break  # circular dep — already caught by validate_plan

                # Emit started for every subtask in this wave
                for s in ready:
                    yield sse("subtask_started", {"id": s.id})
                    await db.chat_sessions.update_one(
                        {"_id": db_session_id},
                        {"$set": {f"messages.{message_index}.subtasks.{s.id - 1}.status": "running"}}
                    )

                # Execute wave concurrently
                wave_results = await asyncio.gather(
                    *[_execute_with_model_async(s, completed_results) for s in ready]
                )

                for subtask_id, result in wave_results:
                    completed_results[subtask_id] = result
                    remaining.discard(subtask_id)
                    # Persist result into the subtask array in MongoDB
                    subtask_index = next(i for i, st in enumerate(plan_msg["subtasks"]) if st["id"] == subtask_id)
                    await db.chat_sessions.update_one(
                        {"_id": db_session_id},
                        {"$set": {
                            f"messages.{message_index}.subtasks.{subtask_index}.result": result,
                            f"messages.{message_index}.subtasks.{subtask_index}.status": "done"
                        }}
                    )
                    yield sse("subtask_done", {"id": subtask_id, "result": result})

            # Stream synthesis final output token-by-token
            yield sse("synthesis_started", {})
            
            final_output_chunks = []
            async for chunk in astream_merge_results(original_prompt, plan, completed_results):
                final_output_chunks.append(chunk)
                yield sse("token", {"text": chunk})
                await asyncio.sleep(0.04)  # Throttle tokens for readable typing cadence
            
            final_output = "".join(final_output_chunks)
            await db.chat_sessions.update_one(
                {"_id": db_session_id},
                {"$set": {
                    f"messages.{message_index}.status": "completed",
                    f"messages.{message_index}.content": final_output,
                }}
            )
            yield sse("complete", {"final_output": final_output})

        except asyncio.CancelledError:
            print(f"🔌 Client disconnected. Stopping execution of session {session_id} message {message_index}.")
            # Set the message status to error/stopped so the UI updates accordingly and subsequent requests are clean
            await db.chat_sessions.update_one(
                {"_id": db_session_id},
                {"$set": {
                    f"messages.{message_index}.status": "error",
                    f"messages.{message_index}.content": "Execution stopped by user."
                }}
            )
            raise
        except Exception as e:
            import traceback
            print(f"❌ SSE execution error:\n{traceback.format_exc()}")
            await db.chat_sessions.update_one(
                {"_id": db_session_id},
                {"$set": {
                    f"messages.{message_index}.status": "error",
                    f"messages.{message_index}.content": f"Execution failed: {str(e)}"
                }}
            )
            yield sse("error", {"detail": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
