from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from .database import db
from .models import UserSignup, UserSignin, UserSettings, UserResponse, Token, MessageCreate, ChatSessionResponse
from .auth import get_password_hash, verify_password, create_access_token, get_current_user
from .orchestrator import plan_task, execute_plan, merge_results
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
    cursor = db.chat_sessions.find({"user_id": current_user["id"]}).sort("created_at", -1)
    sessions = await cursor.to_list(length=100)
    for s in sessions:
        s["id"] = str(s.pop("_id"))
    return sessions

@app.post("/chat/sessions")
async def create_session(current_user: dict = Depends(get_current_user)):
    session = {
        "user_id": current_user["id"],
        "title": "New Chat",
        "created_at": datetime.utcnow(),
        "messages": []
    }
    result = await db.chat_sessions.insert_one(session)
    session_out = await db.chat_sessions.find_one({"_id": result.inserted_id})
    if session_out:
        session_out["id"] = str(session_out.pop("_id"))
    return session_out

@app.delete("/chat/sessions")
async def clear_all_sessions(current_user: dict = Depends(get_current_user)):
    await db.chat_sessions.delete_many({"user_id": current_user["id"]})
    return {"message": "All sessions deleted"}

@app.post("/chat/sessions/{session_id}/messages")
async def send_message(session_id: str, message: MessageCreate, current_user: dict = Depends(get_current_user)):
    # Verify session
    session = await db.chat_sessions.find_one({"_id": ObjectId(session_id), "user_id": current_user["id"]})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    user_msg = {"role": "user", "content": message.content}
    await db.chat_sessions.update_one(
        {"_id": ObjectId(session_id)},
        {"$push": {"messages": user_msg}}
    )
    
    # Generate a simple title if it's the first message
    if len(session.get("messages", [])) == 0 and session.get("title") == "New Chat":
        title = message.content[:30] + "..." if len(message.content) > 30 else message.content
        await db.chat_sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"title": title}}
        )
    
    # Run Orchestrator
    plan = plan_task(message.content)
    if not plan:
        raise HTTPException(status_code=500, detail="Failed to generate plan.")
        
    plan_dict = plan.model_dump()
    
    if message.execute:
        results = execute_plan(plan)
        for subtask in plan_dict["subtasks"]:
            subtask["result"] = results.get(subtask["id"], "(not executed)")
        final_output = merge_results(message.content, plan, results)
        
        ai_msg = {
            "role": "assistant",
            "content": final_output,
            "subtasks": plan_dict["subtasks"]
        }
    else:
        ai_msg = {
            "role": "assistant",
            "content": "Here is the plan.",
            "subtasks": plan_dict["subtasks"]
        }
        
    await db.chat_sessions.update_one(
        {"_id": ObjectId(session_id)},
        {"$push": {"messages": ai_msg}}
    )
    
    session_out = await db.chat_sessions.find_one({"_id": ObjectId(session_id)})
    if session_out:
        session_out["id"] = str(session_out.pop("_id"))
    return session_out
