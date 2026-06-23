import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from datetime import date
from ai_module.product_db import get_quantity_offers_dict, get_bundle_offers
from ai_module.user_memory_db import (
    get_user_memory,
    get_user_profile,
    log_recommendation,
    get_recent_checkins,
    get_recent_chat_history
)

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
Also use recent chatbot interactions from the last 90 days, but do not treat the full conversation as equally important.
Use only useful signals such as health concerns, product questions, repeated issues, preferences, and previous recommendations.
Ignore greetings, thanks, small talk, and unrelated messages.

Give importance in this order:
1. Last 7 days check-in/journal behavior
2. User profile and goals
3. Last 90 days useful chatbot interactions
4. Long-term memory

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
def normalize_moods(recent_moods):
    moods_text = " ".join([str(m).lower() for m in recent_moods])

    mood_map = {
        "😔": "low_mood stress low_energy",
        "😐": "neutral",
        "🙂": "good relaxed",
        "😊": "motivated energetic",
        "🤩": "highly_motivated energetic"
    }

    for emoji, meaning in mood_map.items():
        if emoji in moods_text:
            moods_text += " " + meaning

    return moods_text
def build_nutrition_strategy(merged_profile, signals):
    strategy = {
        "calorie_approach": "balanced",
        "protein": "normal",
        "fiber": "normal",
        
        "step_goal": "",
        "avoid": [],
        "focus": []
    }

    goals = merged_profile.get("goals", [])
    bmi = merged_profile.get("bmi")
    food_patterns = signals.get("food_patterns", [])
    health = signals.get("health_interests", [])
    conditions = merged_profile.get("medical_conditions", [])
    conditions_text = " ".join(conditions).lower() if isinstance(conditions, list) else str(conditions).lower()
    sex = merged_profile.get("sex")
    age = merged_profile.get("age")
   
    recent_moods = merged_profile.get("recent_moods", [])
    avg_steps = merged_profile.get("average_steps_last_7_days", 0)
    activity_level = signals.get("activity_level", "unknown")
   
    # Weight loss
    if "weight_loss" in goals or (bmi and bmi >= 25):
        strategy["calorie_approach"] = "moderate calorie deficit"
        strategy["protein"] = "high"
        strategy["fiber"] = "high"
        strategy["focus"] += [
            "vegetables",
            "lean proteins",
            "whole foods"
        ]

    # Muscle gain
    if "muscle_gain" in goals:
        strategy["calorie_approach"] = "small calorie surplus"
        strategy["protein"] = "very high"
        strategy["focus"] += [
            "protein-rich foods",
            "complex carbohydrates"
        ]


    # Bad food habits from check-ins
    if "heavy_meals" in food_patterns:
        strategy["avoid"].append("fried and very fatty foods")


    if "high_sugar" in food_patterns:
        strategy["avoid"].append("sugary drinks and sweets")


    # Digestion
    if "digestion" in health:
        strategy["focus"] += [
            "fiber",
            "water",
            "probiotic foods"
        ]
        strategy["avoid"].append("ultra-processed foods")
    

    # Medical conditions




    strategy["avoid"] = list(dict.fromkeys(strategy["avoid"]))
    strategy["focus"] = list(dict.fromkeys(strategy["focus"]))
    # Age-based nutrition
    if age and age >= 60:
        strategy["protein"] = "high"
        strategy["focus"] += [
            "adequate protein",
            "calcium-rich foods",
            "vitamin D sources",
            "hydration"
        ]

    # Sex-based nutrition
    if sex == "female":
        strategy["focus"] += [
            "iron-rich foods",
            "calcium-rich foods"
        ]

    if sex == "male":
        strategy["focus"] += [
            "adequate portions based on activity level"
        ]

# BMI-based nutrition
    if bmi and bmi < 18.5:
        strategy["calorie_approach"] = "healthy calorie surplus"
        strategy["protein"] = "high"
        strategy["focus"] += [
            "energy-dense healthy foods",
            "protein-rich meals",
            "complex carbohydrates"
        ]

    elif bmi and 18.5 <= bmi < 25:
        strategy["calorie_approach"] = "maintenance"
        strategy["focus"] += [
            "balanced meals",
            "vegetables",
            "whole grains"
        ]

    elif bmi and bmi >= 30:
        strategy["calorie_approach"] = "gradual calorie deficit"
        strategy["focus"] += [
            "high-satiety meals",
            "lean proteins",
            "fiber-rich foods"
        ]
    

    # Activity/steps influence nutrition
    if avg_steps < 5000 and ("weight_loss" in goals or (bmi and bmi >= 25)):
        strategy["focus"] += [
            "high-satiety meals",
            "lean proteins",
            "vegetables"
        ]
        strategy["avoid"] += [
            "large portions of bread and fried foods"
        ]

    if avg_steps >= 7500 or activity_level == "high":
        strategy["focus"] += [
            "recovery meals",
            "adequate carbohydrates",
            "hydration"
        ]

    if "muscle_gain" in goals and (avg_steps >= 5000 or activity_level in ["moderate", "high"]):
        strategy["focus"] += [
            "post-workout protein",
            "complex carbohydrates after training"
        ]

    # Mood influence nutrition
    moods_text = normalize_moods(recent_moods)
    if "low_energy" in moods_text:
        strategy["focus"] += [
            "iron-rich foods",
            "regular meal timing",
            "adequate hydration"
        ]

    if "stress" in moods_text or "anxious" in moods_text or "قلق" in moods_text:
        strategy["focus"] += [
            "regular meals",
            "magnesium-rich foods",
            "omega-3 sources"
        ]

    strategy["avoid"] = list(dict.fromkeys(strategy["avoid"]))
    strategy["focus"] = list(dict.fromkeys(strategy["focus"]))
    
    # Final nutrition safety override
    if "cholesterol" in conditions_text:
        strategy["avoid"] += [
            "fried foods",
            "high saturated fat foods"
        ]
        strategy["focus"] += [
            "fiber",
            "lean proteins",
            "healthy fats"
        ]


    if "pregnancy" in conditions_text or "breastfeeding" in conditions_text:
        strategy["calorie_approach"] = "doctor-approved balanced nutrition"
        strategy["avoid"] += ["supplements without medical advice", "extreme dieting"]
        strategy["focus"] += ["balanced meals", "hydration", "doctor-approved nutrition"]

    if "diabetes" in conditions_text:
        strategy["avoid"] += ["sugary drinks", "large sweet portions"]
        strategy["focus"] += ["non-starchy vegetables", "lean protein", "quality carbohydrates"]

    if "hypertension" in conditions_text or "high blood pressure" in conditions_text:
        strategy["avoid"] += ["high sodium foods", "processed foods"]
        strategy["focus"] += ["DASH-style meals", "vegetables", "fruits", "whole grains"]

    strategy["avoid"] = list(dict.fromkeys(strategy["avoid"]))
    strategy["focus"] = list(dict.fromkeys(strategy["focus"]))

    return strategy

def build_exercise_strategy(merged_profile, signals):

    strategy = {
        "main_activity": "general movement",
        "duration": "30 minutes",
        "frequency": "3 times per week",
        "intensity": "moderate",
        "exercise_type": "general",
        "focus": "",
        "step_goal": "",
        "today_program": {},
        "body_focus": [],
        "exercise_examples": [],
        "limitations": [],
        "reasoning": []
    }

    avg_steps = merged_profile.get("average_steps_last_7_days", 0)
    activity = signals.get("activity_level")
    age = merged_profile.get("age")
    goals = merged_profile.get("goals", [])
    conditions = merged_profile.get("medical_conditions", [])
    conditions_text = " ".join(conditions).lower() if isinstance(conditions, list) else str(conditions).lower()
    bmi = merged_profile.get("bmi")
    sex = merged_profile.get("sex")
    food_patterns = signals.get("food_patterns", [])
    health = signals.get("health_interests", [])
   
    recent_moods = merged_profile.get("recent_moods", [])
    consistency = merged_profile.get("consistency_score") or 0
    recurring_activity_patterns = merged_profile.get("recurring_activity_patterns", [])
    low_activity_count = recurring_activity_patterns.count("low")
    moderate_activity_count = recurring_activity_patterns.count("moderate")
    high_activity_count = recurring_activity_patterns.count("high")
    
    if sex == "female":
        strategy["reasoning"].append(
            "Program adapted to female physiological characteristics and personal goals."
        )

    elif sex == "male":
        strategy["reasoning"].append(
            "Program adapted to male physiological characteristics and personal goals."
        )

    
    moods_text = normalize_moods(recent_moods)

# Step-based base level
    if avg_steps < 5000:
        strategy["focus"] = "increase daily movement"
        strategy["step_goal"] = "start with 5000–7000 steps/day"
        strategy["duration"] = "20-30 minutes"
        strategy["intensity"] = "light"
    elif avg_steps < 7500:
        strategy["focus"] = "progressive improvement"
        strategy["step_goal"] = "reach 7000–10000 steps/day"
        strategy["intensity"] = "light to moderate"
    elif avg_steps < 10000:
        strategy["focus"] = "maintain good activity level"
        strategy["step_goal"] = "maintain 8000–10000 steps/day"
    else:
        strategy["focus"] = "maintain excellent activity level"
        strategy["step_goal"] = "maintain current activity"

# Activity-level signal from check-ins / LLM signals
    if activity == "low":
        strategy["intensity"] = "light"
        strategy["duration"] = "20-30 minutes"
        strategy["reasoning"].append("Low activity level: start progressively")

    elif activity == "moderate":
        strategy["intensity"] = "light to moderate"
        strategy["reasoning"].append("Moderate activity level: maintain and progress gradually")

    elif activity == "high":
        strategy["intensity"] = "moderate to high"
        strategy["reasoning"].append("High activity level: allow more advanced session if safe")
    
    # Long-term activity behavior from memory
    if low_activity_count >= 2:
        strategy["duration"] = "10-20 minutes"
        strategy["intensity"] = "light"
        strategy["exercise_examples"].append("short walking breaks")
        strategy["reasoning"].append("Recurring low activity pattern: build habit gradually")

    elif high_activity_count >= 2:
        strategy["reasoning"].append("Recurring high activity pattern: allow progression and recovery balance")

    elif moderate_activity_count >= 2:
        strategy["reasoning"].append("Recurring moderate activity pattern: maintain consistency and progress slowly")
# Goal-based exercise type
    if "muscle_gain" in goals:
        strategy["exercise_type"] = "strength training"
        strategy["main_activity"] = "resistance training"
        strategy["duration"] = "40-60 minutes"
    elif "weight_loss" in goals or (bmi and bmi >= 25):
        strategy["exercise_type"] = "cardio + light strength"
        strategy["main_activity"] = "cardio and full-body movement"
    else: 
        strategy["exercise_type"] = "wellness movement"
        strategy["main_activity"] = "walking and mobility"
    # BMI adaptation
    if bmi and bmi >= 30:
        strategy["intensity"] = "light to moderate"
        strategy["duration"] = "20-30 minutes"
        strategy["exercise_examples"].append("low-impact cardio")
        strategy["reasoning"].append("High BMI: prefer low-impact progressive movement")

    elif bmi and bmi < 18.5:
        strategy["exercise_type"] = "strength + mobility"
        strategy["exercise_examples"].append("light resistance training")
        strategy["reasoning"].append("Low BMI: avoid excessive cardio and support strength")
# Health / behavior adaptation
    if "heavy_meals" in food_patterns:
        strategy["exercise_examples"].append("walking after meals")
        strategy["reasoning"].append("Heavy meal pattern detected")

    if "high_sugar" in food_patterns:
        strategy["exercise_examples"].append("light cardio")
        strategy["reasoning"].append("High sugar pattern detected")

    if "digestion" in health:
        strategy["exercise_examples"].append("gentle walking after meals")
        strategy["reasoning"].append("Digestive concern detected")

    if "stress_anxiety" in health or "sleep" in health or "low_mood" in moods_text:
        strategy["exercise_examples"] += ["pilates", "stretching", "breathing exercises", "relaxing walk"]
        strategy["intensity"] = "light to moderate"
        strategy["reasoning"].append("Mood/stress/sleep adaptation")

    if "energetic" in moods_text and not ("pregnancy" in conditions_text or "breastfeeding" in conditions_text):
        strategy["reasoning"].append("Good energy detected: allow slightly more progressive session")

# Consistency adaptation
    if consistency is not None and consistency < 50:
        strategy["duration"] = "10-20 minutes"
        strategy["intensity"] = "light"
        strategy["reasoning"].append("Low consistency: start with simple achievable activity")
    elif consistency is not None and consistency >= 75:
        strategy["reasoning"].append("High consistency: user can progress gradually")

# Daily body/type rotation
    body_rotation = ["cardio", "lower body", "upper body + core", "mobility", "full body"]
    rotation_index = date.today().weekday() % len(body_rotation)
    rotated_focus = body_rotation[rotation_index]

# Today's program selector
    if "stress_anxiety" in health or "sleep" in health or "low_mood" in moods_text:
        today_focus = "stress relief / mobility"
        today_activity = "pilates, stretching, breathing exercises, or relaxing walk"
    elif "muscle_gain" in goals:
        today_focus = rotated_focus if rotated_focus != "cardio" else "full body"
        today_activity = f"{today_focus} strength exercises adapted to your level"
    elif "weight_loss" in goals or (bmi and bmi >= 25):
        today_focus = rotated_focus
        today_activity = f"{today_focus} session with cardio and light strength"
    else:
        today_focus = rotated_focus
        today_activity = f"{today_focus} wellness movement"

    strategy["today_program"] = {
        "focus": today_focus,
        "activity": today_activity,
        "duration": strategy.get("duration"),
        "intensity": strategy.get("intensity"),
        "step_goal": strategy.get("step_goal"),
        "extra": list(dict.fromkeys(strategy.get("exercise_examples", [])))[:3],
    }



    # Final safety override: medical conditions have highest priority
    if "pregnancy" in conditions_text or "breastfeeding" in conditions_text:
        strategy["main_activity"] = "doctor-approved gentle movement"
        strategy["duration"] = "15-30 minutes"
        strategy["frequency"] = "as approved by doctor"
        strategy["intensity"] = "light"
        strategy["step_goal"] = "gentle daily movement only if approved"
        strategy["exercise_examples"] = ["doctor-approved walking", "gentle mobility"]
        strategy["reasoning"].append("Pregnancy/breastfeeding safety override")
        strategy["today_program"] = {
            "focus": "safety and gentle movement",
            "activity": "doctor-approved walking or gentle mobility",
            "duration": "15-30 minutes",
            "intensity": "light",
            "step_goal": "gentle movement only if approved",
            "extra": ["avoid intense exercise", "rest if tired"]
        }



    elif "hypertension" in conditions_text or "high blood pressure" in conditions_text:
        strategy["main_activity"] = "walking and low-impact cardio"
        strategy["intensity"] = "light to moderate"
        strategy["reasoning"].append("Hypertension safety adaptation")
        strategy["today_program"] = {
            "focus": "low-impact cardio",
            "activity": "walking or low-impact cardio",
            "duration": strategy.get("duration"),
            "intensity": "light to moderate",
            "step_goal": strategy.get("step_goal"),
            "extra": ["avoid sudden intense effort"]
        }

    elif age and age >= 60:
        strategy["main_activity"] = "walking, mobility, balance, and light resistance training"
        strategy["intensity"] = "light to moderate"
        strategy["frequency"] = "most days of the week"
        strategy["reasoning"].append("Older adult safety adaptation")
    return strategy

def generate_dynamic_plan_with_llm(
    merged_profile: dict,
    signals: dict,
    decision: dict,
    nutrition_strategy: dict,
    exercise_strategy: dict
    
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

The recommendations MUST consider ALL available information:

1. User profile:
- age
- sex
- weight
- height
- BMI
- goals
- medical conditions

2. Recent 7-day behavior:
- detected food patterns from recent check-ins
- detected activity level
- consistency and behavioral trends
- mood patterns
- average daily steps

3. Long-term personalization:
- last 90 days useful chatbot interactions
- user memory and recurring patterns

4. Rule-based strategies:
- nutrition_strategy generated from scientific rules
- exercise_strategy generated from scientific rules

Do not ignore any important factor.

User profile:
{json.dumps(merged_profile, ensure_ascii=False)}

Extracted signals:
{json.dumps(signals, ensure_ascii=False)}

Decision layer:
{json.dumps(decision, ensure_ascii=False)}
Nutrition strategy:
{json.dumps(nutrition_strategy, ensure_ascii=False)}

Exercise strategy:
{json.dumps(exercise_strategy, ensure_ascii=False)}

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
- Use recent_chat_topics from the last 90 days only as long-term personalization signals.
- Do not repeat or summarize the whole chatbot conversation.
- Use chat history only to detect recurring concerns, preferences, products discussed, and repeated difficulties.
- If recent check-ins show improvement after previous poor habits, encourage progress and suggest maintaining the new habit.
- If behavior is consistently good, suggest maintenance and small optimizations.
- If behavior is worsening, give more corrective but supportive recommendations.
- Do not recommend extreme diets, unrealistic exercises, or medical claims. Prefer realistic habits adapted to the user profile and recent behavior.
- Use age to adapt exercise intensity and recovery advice.
- Younger users can tolerate more progressive activity suggestions.
- Older users should receive more gradual and recovery-focused advice.
- Use food_patterns, activity_level, average steps, mood, consistency, health interests, and today_program to personalize recommendations.
- Use BMI to adapt calorie-balance recommendations.
- High BMI -> focus on sustainable habits and progressive movement.
- Low BMI -> avoid aggressive calorie restriction.
- If medical_conditions exist, adapt meals and exercise safely.
- Do not give diagnosis or treatment.
- For diabetes: avoid high-sugar recommendations.
- For hypertension: avoid high-salt recommendations.
- For pregnancy, breastfeeding, chronic disease, or medication use: recommend medical advice before supplements.
- Do not always choose the same body focus. Use exercise_strategy.today_program.focus as today’s target and vary body focus across days when medically safe.
- Generate ONLY today’s exercise program, not a weekly plan.
- Use exercise_strategy.today_program as the main exercise recommendation.
- Today’s program must vary the exercise type/body focus depending on all available data: goal, BMI, age, sex, medical conditions, moods, average steps, activity_level, food patterns, health interests, recurring behaviors, chat history, and consistency.
- Mention body focus when available: upper body, lower body, core, cardio, mobility, recovery.
- Respect intensity, duration, frequency, step_goal, limitations and medical safety rules.
Generate a complete personalized exercise session for today.

Use exercise_strategy.today_program as the main guidance.

The session must include:
- A warm-up adapted to the user's condition (3–10 minutes)
- 3–5 exercises with precise sets/repetitions or duration
- A cool-down with stretching, breathing, or mobility exercises

Adapt the exercises according to:
- Age
- Sex (only for physiological context, never limit body parts based on sex)
- BMI and current fitness level
- Goal (weight loss, muscle gain, general wellness)
- Medical conditions and safety limitations (highest priority)
- Average steps and activity level from the last 7 days
- Mood and consistency level
- Health interests and long-term behavior

If the user has low energy, low consistency, or low activity, propose simpler exercises.

If the user is energetic and has no medical restrictions, propose more challenging exercises.

Do not recommend unsafe exercises. Medical conditions always override fitness goals.
Cultural adaptation rules:
- Adapt meal recommendations to Tunisian food culture when appropriate.
- Prefer realistic Tunisian healthy meals instead of only international meals.
- Keep the recommendations compatible with the nutrition_strategy.
- You may suggest traditional Tunisian dishes with healthier adaptations.

Examples:
- Couscous with vegetables and lean chicken instead of high-fat couscous.
- Lablabi with moderate bread portions and good protein sources.
- Ojja with vegetables and controlled oil.
- Slata mechouia with tuna or eggs.
- Grilled fish with vegetables.
- Chorba with balanced portions.
- Frik soup.
- Healthy Tunisian salads.
- Fruits, nuts, yogurt, and dates can be suggested only when compatible with medical conditions. For diabetes, prefer unsweetened yogurt, nuts, and low-glycemic fruits, and avoid adding honey or excessive dates.

For weight loss:
- Reduce portions of bread, sweets, fried foods, and sugary drinks.
- Prefer grilled, steamed, and home-cooked meals.

For muscle gain:
- Increase protein sources such as eggs, chicken, fish, dairy, legumes, and Tunisian dishes rich in protein.

For diabetes or blood sugar concerns:
- Prefer low glycemic and high-fiber choices.
- Control bread, pastries, and sugary dessert portions.

Do not criticize traditional Tunisian food. Adapt it to make it healthier.

IMPORTANT:
Do not decide nutrition or exercise strategy by yourself.

The nutrition_strategy and exercise_strategy are generated by a deterministic rule engine based on BMI, goals, age, activity level, health concerns and recent behavior.

Your role is only to transform these strategies into:
- realistic meals
- suitable exercises
- practical daily actions

Always follow the provided strategies.
Do not recommend extreme diets or unrealistic workouts.

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

Do NOT generate supplement safety warnings.
Do NOT generate medical-condition warnings.
These warnings are already handled by the rule engine.
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
    consistency = merged_profile.get("consistency_score") or 0
    conditions = merged_profile.get("medical_conditions", [])
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
    if goals:
        decision["used_signals"]["profile"] = True

    if bmi:
        decision["used_signals"]["bmi"] = True

    if activity_level != "unknown":
        decision["used_signals"]["activity"] = True
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

   
    elif "muscle_gain" in goals_text:
        decision["priority_focus"] = "muscle_gain"
        decision["used_signals"]["profile"] = True
    elif bmi and bmi >= 25:
        decision["priority_focus"] = "weight_management"
        decision["used_signals"]["bmi"] = True

    else:
        decision["priority_focus"] = "general_wellness"
    # -------------------------
# Advanced behavioral logic
# -------------------------

    if (
        age
        and age >= 50
        and activity_level == "low"
    ):
        decision["daily_actions"].append({
            "action": "Increase movement progressively",
            "reason": "Low activity level and low step count require gradual adaptation."
        })
    if (
        bmi and bmi >= 28
        and "high_sugar" in food_patterns
        and consistency < 50
    ):
        decision["priority_focus"] = "weight_management"

    if "stress_anxiety" in health_interests:
        decision["daily_actions"].append({
            "action": "Improve sleep quality and reduce stress",
            "reason": "Stress management supports recovery and overall wellbeing."
        })
    if consistency < 40:
        decision["daily_actions"].append({
            "action": "Start with small achievable habits",
            "reason": "Gradual changes improve long-term consistency."
        })
    conditions_text = " ".join(conditions).lower() if isinstance(conditions, list) else str(conditions).lower()

    if "pregnancy" in conditions_text or "breastfeeding" in conditions_text:
        decision["priority_focus"] = "pregnancy_safe_wellness"
        decision["warnings"].append(
            "في فترة الحمل أو الرضاعة، استشيري الطبيب قبل استعمال أي مكمل غذائي."
        )
        decision["confidence_score"] = 70
        return decision
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
        or decision["priority_focus"] == "weight_loss"
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
    if conditions:
        decision["warnings"].append(
            "إذا عندك مرض مزمن أو تستعمل أدوية، استشر طبيب أو صيدلي قبل استعمال أي مكمل غذائي."
        )
    decision["confidence_score"] = min(confidence, 100)

    return decision

def build_recommendation_agent_output(user_profile: dict):
    import time
    start_time = time.time()
    user_profile = user_profile or {}
    user_id = user_profile.get("user_id", "demo_user")
    memory = get_user_memory(user_id)
    profile = get_user_profile(user_id)
    recent_checkins = get_recent_checkins(user_id, limit=50)
    recent_steps = [
        c.get("daily_steps", 0)
        for c in recent_checkins
        if c.get("daily_steps") is not None
    ]

    average_steps_last_7_days = (
        sum(recent_steps) / len(recent_steps)
        if recent_steps else 0
    )
    recent_chat_history = get_recent_chat_history(user_id, days=90, limit=100)
    quantity_offers_db = get_quantity_offers_dict()
    bundle_offers_db = get_bundle_offers()
    merged_profile = {
        "user_id": user_id,
        "age": user_profile.get("age") or profile.get("age"),
        "weight": user_profile.get("weight") or profile.get("weight"),
        "height": user_profile.get("height") or profile.get("height"),
        "goals": user_profile.get("goals") or profile.get("goals", []),
        "average_steps_last_7_days": average_steps_last_7_days,
        "medical_conditions": user_profile.get("medical_conditions") or profile.get("medical_conditions", []),
        "language": user_profile.get("language", "ar"),
        "sex": user_profile.get("sex") or profile.get("sex"),
   
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
        "recent_checkins": recent_checkins,
        "recent_chat_history": recent_chat_history,
        "recent_chat_topics": [
            {
                "question": c.get("question"),
                "intent": c.get("intent"),
                "detected_product": c.get("detected_product"),
                "recommended_product": c.get("recommended_product"),
            }
            for c in recent_chat_history
            if c.get("intent") not in ["greeting", "thanks", "small_talk", None]
        ],
        "recent_meals": [
            meal.get("description")
            for c in recent_checkins
            for meal in c.get("daily_meal_logs", [])
            if meal.get("description")
        ],
        "recent_activities": [
            activity.get("activity_type")
            for c in recent_checkins
            for activity in c.get("daily_activity_logs", [])
            if activity.get("activity_type")
        ],
        "recent_moods": [c.get("mood") for c in recent_checkins if c.get("mood")],
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
    nutrition_strategy = build_nutrition_strategy(
        merged_profile,
        signals
    )

    exercise_strategy = build_exercise_strategy(
        merged_profile,
        signals
    )
    dynamic_plan = generate_dynamic_plan_with_llm(
        merged_profile,
        signals,
        decision,
        nutrition_strategy,
        exercise_strategy
    )
    

    output = {
        "profile_summary": {
            "goals": merged_profile.get("goals"),
            "weight": merged_profile.get("weight"),
            "height": merged_profile.get("height"),
            "bmi": bmi,
            "age": merged_profile.get("age"),
            "medical_conditions": merged_profile.get("medical_conditions"),
            "sex": merged_profile.get("sex"),
            "average_steps_last_7_days": average_steps_last_7_days,
            "activity_level": signals.get("activity_level", "unknown"),
            "health_interests": signals.get("health_interests", []),
            "food_patterns": signals.get("food_patterns", []),
            "past_recommended_products": merged_profile.get("past_recommended_products", []),
            "last_recommended_product": merged_profile.get("last_recommended_product"),
            "last_meal_summary": merged_profile.get("last_meal_summary"),
            "last_activity_summary": merged_profile.get("last_activity_summary"),
            "last_detected_issue": merged_profile.get("last_detected_issue"),
            "consistency_score": merged_profile.get("consistency_score"),
            "recent_checkins_count": len(recent_checkins),
            "recent_meals": merged_profile.get("recent_meals"),
            "recent_activities": merged_profile.get("recent_activities"),
            "recent_chat_count": len(recent_chat_history),
            "recent_chat_topics": merged_profile.get("recent_chat_topics"),
        },

        "priority_focus": decision["priority_focus"],
        "recommended_products": decision["recommended_products"],

        "meal_recommendations": dynamic_plan.get("meal_recommendations", []),
        "exercise_recommendations": dynamic_plan.get("exercise_recommendations", []),
        "daily_actions": dynamic_plan.get("daily_actions", []),
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
        "used_activity": (
            len(recent_checkins) > 0
        ),
        "used_bmi": bool(bmi),
        "used_daily_checkin": len(recent_checkins) > 0,
        "response_time_sec": response_time,
    })
    output["warnings"] = list(dict.fromkeys(output.get("warnings", [])))
    return output