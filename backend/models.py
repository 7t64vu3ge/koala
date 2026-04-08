from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class UserSignup(BaseModel):
    display_name: str
    email: EmailStr
    password: str

class UserSignin(BaseModel):
    email: EmailStr
    password: str

class UserSettings(BaseModel):
    display_name: Optional[str] = None
    theme: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    display_name: str
    email: str
    theme: str

class Token(BaseModel):
    access_token: str
    token_type: str

class MessageBase(BaseModel):
    role: str
    content: str
    status: str = "completed" # "completed", "pending_approval", "executing"
    subtasks: Optional[List[Dict[str, Any]]] = None
    plan: Optional[Dict[str, Any]] = None # stores the raw OrchestratorPlan data

class MessageCreate(BaseModel):
    content: str
    execute: bool = False
    parent_message_id: Optional[str] = None # For refinements

class ChatSessionResponse(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    messages: List[MessageBase] = []
