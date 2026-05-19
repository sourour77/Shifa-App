from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Optional
from ai_module.Chatbot import chatbot_response

app = FastAPI()

class ChatRequest(BaseModel):
    question: str
    age: int | None = None
    user_id: str | None = None
    height: float | None = None
    weight: float | None = None
    goals: list[str] | None = None
    preferences: str | None = None
    activity_info: str | None = None
    history: str | None = None
    chat_history: Optional[List[Dict[str, str]]] = None

@app.get("/")
def root():
    return {"message": "ShifaChatbot API is running"}

@app.post("/chat")
def chat(req: ChatRequest):
    user_profile = {
        "age": req.age,
        "user_id": req.user_id or "demo_user",
        "weight": req.weight,
        "goals": req.goals,
        "height": req.height,
        "preferences": req.preferences,
        "activity_info": req.activity_info,
        "history": req.history,
    }

    result = chatbot_response(
        question=req.question,
        user_profile=user_profile,
        chat_history=req.chat_history or []
    )

    return {
        "response": result["answer"],
        "intent": result["intent"],
        "detected_product": result["detected_product"],
        "recommended_product": result["recommended_product"],
        "recommendation_reason": result["recommendation_reason"],
        "meal_suggestion": result["meal_suggestion"],
        "calorie_info": result["calorie_info"],
        "usage_info": result["usage_info"],
        "benefits_info": result["benefits_info"],
        "precautions": result["precautions"],
        "lifestyle_suggestion": result["lifestyle_suggestion"],
        "follow_up_question": result["follow_up_question"],
        "price_info": result["price_info"],
        "offer_info": result["offer_info"],
    }