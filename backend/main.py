from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Optional

from ai_module.Chatbot import chatbot_response
from ai_module.checkin_agent import build_daily_checkin_output
from ai_module.recommendation_agent import build_recommendation_agent_output
from ai_module.user_memory_db import (
    create_daily_checkin,
    log_daily_meal,
    log_daily_activity,
    update_user_memory,
    get_recent_checkins,
)
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
    medical_conditions: list[str] | None = None


class CheckinRequest(BaseModel):
    user_id: str
    meals_today: str
    activity_today: str
    mood: str | None = None
    age: int | None = None
    weight: float | None = None
    height: float | None = None
    sex: str | None = None
    goals: list[str] | None = None
    language: str = "ar"
    medical_conditions: list[str] | None = None
    daily_steps: int | None = None


class RecommendRequest(BaseModel):
    user_id: str
    age: int | None = None
    weight: float | None = None
    height: float | None = None
    sex: str | None = None
    goals: list[str] | None = None
    language: str = "ar"
    activity_info: str | None = None
    medical_conditions: list[str] | None = None


@app.get("/")
def root():
    return {"message": "ShifaChatbot API is running"}


@app.post("/chat")
def chat(req: ChatRequest):
    user_profile = {
        "age": req.age,
        "user_id": req.user_id or "demo_user",
        "weight": req.weight,
        "goals": req.goals or [],
        "height": req.height,
        "preferences": req.preferences,
        "activity_info": req.activity_info,
        "history": req.history,
        "medical_conditions": req.medical_conditions or [],

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


@app.post("/checkin")
def checkin(req: CheckinRequest):
    user_profile = {
        "user_id": req.user_id,
        "age": req.age,
        "weight": req.weight,
        "height": req.height,
        "sex": req.sex,
        "goals": req.goals or [],
        "language": req.language,
        "medical_conditions": req.medical_conditions or [],
    }

    result = build_daily_checkin_output(
        user_profile=user_profile,
        meals_today=req.meals_today,
        activity_today=req.activity_today,
        mood=req.mood or "",
    )

    checkin = create_daily_checkin(req.user_id, {
        "mood": req.mood,
        "notes": result.get("memory_updates", {}).get("notes", []),
        "daily_steps": req.daily_steps or 0,
    })

    energy = result.get("energy_estimation", {})
    extracted_activity = result.get("structured_energy", {})

    log_daily_meal(checkin["id"], {
        "meal_type": "general",
        "description": req.meals_today,
        "estimated_calories": energy.get("estimated_calories_in"),
        "estimated_protein": None,
    })

    log_daily_activity(checkin["id"], {
        "activity_type": req.activity_today or "general",
        "duration_minutes": extracted_activity.get("activity_duration_minutes"),
        "intensity": result.get("activity_level_today"),
        "estimated_calories_burned": energy.get("estimated_activity_calories_burned"),
    })

    recent_checkins = get_recent_checkins(req.user_id, limit=7)

    from ai_module.checkin_agent import analyze_recent_trends, compute_consistency_from_recent_checkins

    trend_analysis = analyze_recent_trends(recent_checkins)
    consistency = compute_consistency_from_recent_checkins(recent_checkins)

    memory_updates = result.get("memory_updates", {})
    memory_updates["trend_analysis"] = trend_analysis
    memory_updates["consistency_score"] = consistency.get("score")

    update_user_memory(req.user_id, memory_updates)

    result["recent_trend_analysis"] = trend_analysis
    result["recent_consistency"] = consistency
    result["recent_checkins_count"] = len(recent_checkins)

    return result


@app.post("/recommend")
def recommend(req: RecommendRequest):
    user_profile = {
        "user_id": req.user_id,
        "age": req.age,
        "weight": req.weight,
        "height": req.height,
        "sex": req.sex,
        "goals": req.goals or [],
        "language": req.language,
        "activity_info": req.activity_info,
        "medical_conditions": req.medical_conditions or [],
    }

    return build_recommendation_agent_output(user_profile)
