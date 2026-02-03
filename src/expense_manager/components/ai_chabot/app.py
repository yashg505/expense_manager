from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

from expense_manager.components.ai_chabot.engine import answer

app = FastAPI(title="Expense DB Chatbot API")

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

@app.post("/chat")
def chat(req: ChatRequest):
    return answer(req.message, req.conversation_id)
