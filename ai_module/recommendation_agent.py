import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from ai_module.user_memory_db import get_user_memory, log_recommendation
from ai_module.product_db import get_quantity_offers_dict, get_bundle_offers

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None


def calculate_bmi(weight, height_cm):
    if not weight or not height_cm:
        return None
    height_m = height_cm / 100
    if height_m <= 0:
        return None
    return round(weight / (height_m ** 2), 1)


def get_best_offer(product_name, quantity_offers_db, bundle_offers_db):
    if product_name in quantity_offers_db:
        offers = quantity_offers_db[product_name]
        return max(offers, key=lambda x: x.get("discount_percent", 0))

    for bundle in bundle_offers_db:
        if product_name in bundle.get("products", []):
            return bundle

    return None


def extract_recommendation_signals_with_llm(merged_profile: dict) -> dict:
    fallback = {
        "health_interests": merged_profile.get("health_interests", []),
        "activity_level": "unknown",
        "food_patterns": merged_profile.get("recurring_food_patterns", []),
        "detected_priority_need": None,
        "recommended_product_signals": [],
        "meal_strategy": "",
        "exercise_strategy": "",
        "reasoning_summary": "Fallback extraction used."
    }

    if client is None:
        return fallback
    prompt = f"""
You are a wellness recommendation signal extractor for Shifa.

Analyze this user profile + memory + daily check-in data and return ONLY valid JSON.

Allowed health_interests:
- digestion
- detox
- weight_loss
- muscle_gain
- blood_regulation
- stress_anxiety
- sleep

Allowed activity_level:
- low
- moderate
- high
- unknown

Allowed food_patterns:
- heavy_meals
- high_sugar
- light_meals
- balanced_meals
- protein_intake
- vegetable_intake

Return this exact JSON schema:
{{
  "health_interests": [],
  "activity_level": "unknown",
  "food_patterns": [],
  "detected_priority_need": null,
  "recommended_product_signals": [],
  "meal_strategy": "",
  "exercise_strategy": "",
  "reasoning_summary": ""
}}

Product mapping signals:
- digestion/gas/bloating/constipation/stomach discomfort -> Colon Detox
- detox/liver -> Liver Detox
- weight loss/slimming/high BMI -> Slim Pack
- blood circulation/blood regulation/heart support/anxiety/stress-related wellness -> Blood Detox
- muscle gain -> no Shifa product unless current product database supports it

Important:
- Do not invent products.
- Use only signals, not final long explanations.
- If anxiety is mentioned, use stress_anxiety and blood_regulation as signals.

User data:
{json.dumps(merged_profile, ensure_ascii=False)}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Return only valid JSON. No markdown. No explanation."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        content = response.choices[0].message.content.strip()
        return json.loads(content)

    except Exception:
        return fallback


def add_product(recommended_products, product, reason, quantity_offers_db, bundle_offers_db):
    if product not in [p["product"] for p in recommended_products]:
        recommended_products.append({
            "product": product,
            "reason": reason,
            "offer": get_best_offer(product, quantity_offers_db, bundle_offers_db)
        })
def generate_dynamic_plan_with_llm(
    merged_profile: dict,
    signals: dict,
    decision: dict
    
):
    fallback = {
        "meal_recommendations": [],
        "exercise_recommendations": [],
        "daily_actions": [],
        "warnings": []
    }
    
    language = merged_profile.get("language", "ar")

    if client is None:
        return fallback

    prompt = f"""
You are a wellness recommendation assistant for Shifa.

Generate personalized:
1. meal recommendations
2. exercise recommendations
3. daily wellness actions

The recommendations must adapt to:
- user goal
- BMI
- activity level
- daily check-in
- memory
- food patterns
- detected health interests

User profile:
{json.dumps(merged_profile, ensure_ascii=False)}

Extracted signals:
{json.dumps(signals, ensure_ascii=False)}

Decision layer:
{json.dumps(decision, ensure_ascii=False)}

Rules:
Output language: {language}

Language rules:
- If language = "fr", write everything in French.
- If language = "ar", write everything in Arabic or Tunisian Arabic.
- Do not mix French and Arabic in the same recommendation.
- Be practical and personalized.
- Avoid generic robotic recommendations.
- Adapt meals to detected food patterns.
- Adapt exercise intensity to activity level.
- Keep recommendations realistic.
Advanced reasoning rules:

- Use age to adapt exercise intensity and recovery advice.
- Younger users can tolerate more progressive activity suggestions.
- Older users should receive more gradual and recovery-focused advice.

- Use BMI to adapt calorie-balance recommendations.
- High BMI -> focus on sustainable habits and progressive movement.
- Low BMI -> avoid aggressive calorie restriction.

- Use consistency_score:
  - low consistency -> suggest small achievable actions.
  - medium consistency -> encourage stabilization.
  - high consistency -> suggest progression and stronger discipline.
  - If consistency is low:
      be supportive and avoid harsh recommendations.

  - If consistency is high:
      use more motivating/progressive tone.
- Detect repeated unhealthy habits from recurring_food_patterns.
- Detect sedentary lifestyle from recurring_activity_patterns.
- Use recent meal/activity summaries to personalize recommendations.

- If user repeatedly reports heavy meals or high sugar:
  recommendations should directly adapt to these habits.

- Avoid repeating identical recommendations every day.
- Recommendations should feel contextual, progressive, human, and realistic.
- Return ONLY valid JSON.

JSON schema:
{{
  "behavioral_insight": "",
  "meal_recommendations": [
    {{
      "title": "",
      "recommendation": "",
      "reason": ""
    }}
  ],
  "exercise_recommendations": [
    {{
      "title": "",
      "recommendation": "",
      "reason": ""
    }}
  ],
  "daily_actions": [
    {{
      "action": "",
      "reason": ""
    }}
  ],
  "motivation_message": "",
  "warnings": []
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Return only valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7
        )

        content = response.choices[0].message.content.strip()

        return json.loads(content)

    except Exception:
        return fallback
    
def build_recommendation_decision(
    signals: dict,
    merged_profile: dict,
    bmi: float | None,
    quantity_offers_db: dict,
    bundle_offers_db: list
) -> dict:
    health_interests = signals.get("health_interests", [])
    activity_level = signals.get("activity_level", "unknown")
    food_patterns = signals.get("food_patterns", [])
    priority_need = signals.get("detected_priority_need")
    goals = merged_profile.get("goals", [])
    goals_text = " ".join(goals).lower() if isinstance(goals, list) else str(goals).lower() 
    age = merged_profile.get("age")
    consistency = merged_profile.get("consistency_score", 0)

    decision = {
        "priority_focus": None,
        "recommended_products": [],
        "meal_plan": {
            "breakfast": None,
            "lunch": None,
            "dinner": None,
            "snack": None,
        },
        "exercise_plan": {
            "main_activity": None,
            "duration": None,
            "intensity": None,
            "frequency": None,
        },
        "daily_actions": [],
        "warnings": [],
        "upsell_strategy": None,
        "confidence_score": 0,
        "used_signals": {
            "memory": False,
            "profile": False,
            "daily_checkin": False,
            "bmi": False,
            "activity": False,
        }
    }

    # -------------------------
    # 1. Decide priority focus
    # -------------------------
    if priority_need:
        decision["priority_focus"] = priority_need
        decision["used_signals"]["daily_checkin"] = True

    elif health_interests:
        decision["priority_focus"] = health_interests[0]
        decision["used_signals"]["memory"] = True

    elif "weight loss" in goals_text or "weightloss" in goals_text:
        decision["priority_focus"] = "weight_loss"
        decision["used_signals"]["profile"] = True

    elif bmi and bmi >= 25:
        decision["priority_focus"] = "weight_management"
        decision["used_signals"]["bmi"] = True

    else:
        decision["priority_focus"] = "general_wellness"
    # -------------------------
# Advanced behavioral logic
# -------------------------

    if age and age >= 50:
        decision["daily_actions"].append(
            "Prioritize gradual movement, recovery, hydration, and sleep quality."
        )

    if (
        bmi and bmi >= 28
        and "high_sugar" in food_patterns
        and consistency < 50
    ):
        decision["priority_focus"] = "weight_management"

    if (
        "stress_anxiety" in health_interests
        and consistency < 40
    ):
        decision["daily_actions"].append(
            "Focus on sleep quality, stress reduction, and regular meal timing."
        )

    # -------------------------
    # 2. Product decision
    # -------------------------
    if "digestion" in health_interests or decision["priority_focus"] == "digestion":
        add_product(
            decision["recommended_products"],
            "Colon Detox",
            "Best match for digestion, bloating, gas, and constipation support.",
            quantity_offers_db,
            bundle_offers_db
        )

    if "detox" in health_interests or decision["priority_focus"] == "detox":
        add_product(
            decision["recommended_products"],
            "Liver Detox",
            "Best match for liver support and detox routine.",
            quantity_offers_db,
            bundle_offers_db
        )

    if (
        "weight_loss" in health_interests
        or decision["priority_focus"] in ["weight_loss", "weight_management"]
        or "weight loss" in goals_text 
        or "weightloss" in goals_text
    ):
        add_product(
            decision["recommended_products"],
            "Slim Pack",
            "Best match for weight-management support.",
            quantity_offers_db,
            bundle_offers_db
        )

    if (
        "blood_regulation" in health_interests
        or "stress_anxiety" in health_interests
        or decision["priority_focus"] in ["blood_regulation", "stress_anxiety"]
    ):
        add_product(
            decision["recommended_products"],
            "Blood Detox",
            "Best match for circulation, blood regulation, and stress/anxiety-related wellness support.",
            quantity_offers_db,
            bundle_offers_db
        )

 
    # -------------------------
    if decision["recommended_products"]:
        decision["warnings"].append("منتجات شفاء مكملات غذائية وليست أدوية، ولا تعوض الطبيب.")

    if priority_need in ["digestion", "detox", "blood_regulation", "stress_anxiety"]:
        decision["warnings"].append("إذا الأعراض متكررة أو قوية، الأفضل استشارة مختص.")

    # -------------------------
    # 6. Upsell strategy
    # -------------------------
    if decision["recommended_products"]:
        first_product = decision["recommended_products"][0]["product"]
        offer = get_best_offer(
            first_product,
            quantity_offers_db,
            bundle_offers_db
        )

        if offer:
            decision["upsell_strategy"] = {
                "product": first_product,
                "offer": offer,
                "message": "أفضل عرض متاح لهذا المنتج."
            }

    # -------------------------
    # 7. Confidence score
    # -------------------------
    confidence = 40

    if health_interests:
        confidence += 20
    if priority_need:
        confidence += 15
    if goals:
        confidence += 10
    if bmi:
        confidence += 5
    if activity_level != "unknown":
        confidence += 10

    decision["confidence_score"] = min(confidence, 100)

    return decision

def build_recommendation_agent_output(user_profile: dict):
    import time
    start_time = time.time()
    user_profile = user_profile or {}
    user_id = user_profile.get("user_id", "demo_user")
    memory = get_user_memory(user_id)
    quantity_offers_db = get_quantity_offers_dict()
    bundle_offers_db = get_bundle_offers()
    merged_profile = {
        "user_id": user_id,
        "age": user_profile.get("age") or memory.get("age"),
        "weight": user_profile.get("weight") or memory.get("weight"),
        "height": user_profile.get("height") or memory.get("height"),
        "goals": user_profile.get("goals") or memory.get("goals", []),
        "language": user_profile.get("language", "ar"),
        "activity_info": user_profile.get("activity_info") or memory.get("activity_info"),
        "trend_analysis": memory.get("trend_analysis"),
        "health_interests": memory.get("health_interests", []),
        "past_recommended_products": memory.get("past_recommended_products", []),
        "last_recommended_product": memory.get("last_recommended_product"),
        "recurring_food_patterns": memory.get("recurring_food_patterns", []),
        "recurring_activity_patterns": memory.get("recurring_activity_patterns", []),
        "last_meal_summary": memory.get("last_meal_summary"),
        "last_activity_summary": memory.get("last_activity_summary"),
        "last_detected_issue": memory.get("last_detected_issue"),
        "consistency_score": memory.get("consistency_score"),
        "notes": memory.get("notes", []),
    }

    bmi = calculate_bmi(merged_profile.get("weight"), merged_profile.get("height"))
    merged_profile["bmi"] = bmi

    signals = extract_recommendation_signals_with_llm(merged_profile)
    decision = build_recommendation_decision(
        signals,
        merged_profile,
        bmi,
        quantity_offers_db,
        bundle_offers_db
    )
    dynamic_plan = generate_dynamic_plan_with_llm(
        merged_profile,
        signals,
        decision
    )
    

    output = {
        "profile_summary": {
            "goals": merged_profile.get("goals"),
            "weight": merged_profile.get("weight"),
            "height": merged_profile.get("height"),
            "bmi": bmi,
            "activity_level": signals.get("activity_level", "unknown"),
            "health_interests": signals.get("health_interests", []),
            "food_patterns": signals.get("food_patterns", []),
            "past_recommended_products": merged_profile.get("past_recommended_products", []),
            "last_recommended_product": merged_profile.get("last_recommended_product"),
            "last_meal_summary": merged_profile.get("last_meal_summary"),
            "last_activity_summary": merged_profile.get("last_activity_summary"),
            "last_detected_issue": merged_profile.get("last_detected_issue"),
            "consistency_score": merged_profile.get("consistency_score"),
        },

        "priority_focus": decision["priority_focus"],
        "recommended_products": decision["recommended_products"],

        "meal_recommendations": dynamic_plan.get("meal_recommendations", []),
        "exercise_recommendations": dynamic_plan.get("exercise_recommendations", []),
        "daily_actions": dynamic_plan.get("daily_actions", []) + decision.get("daily_actions", []),
        "behavioral_insight": dynamic_plan.get("behavioral_insight", ""),
        "motivation_message": dynamic_plan.get("motivation_message", ""),
        "warnings": dynamic_plan.get("warnings", []) + decision.get("warnings", []),

        "upsell_strategy": decision["upsell_strategy"],
        "confidence_score": decision["confidence_score"],

        "reasoning_summary": signals.get("reasoning_summary", "")
            or "Recommendation generated from profile, memory, and daily check-in.",

        "llm_signals": signals,
        "decision_layer": decision
    }


    response_time = round(time.time() - start_time, 3)

    log_recommendation(user_id, {
        "recommended_products": [p.get("product") for p in output.get("recommended_products", [])],
        "meal_recommendations": output.get("meal_recommendations", []),
        "exercise_recommendations": output.get("exercise_recommendations", []),
        "reasoning_summary": output.get("reasoning_summary"),

        "used_memory": bool(memory.get("health_interests") or memory.get("past_recommended_products")),
        "used_goal": bool(merged_profile.get("goals")),
        "used_activity": bool(merged_profile.get("activity_info")),
        "used_bmi": bool(bmi),
        "used_daily_checkin": bool(memory.get("last_meal_summary") or memory.get("last_activity_summary")),

        "response_time_sec": response_time,
    })

    return output