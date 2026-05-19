from ai_module.supabase_client import supabase


def get_or_create_user(user_code: str):
    user_code = user_code or "demo_user"

    existing = (
        supabase.table("users")
        .select("*")
        .eq("user_code", user_code)
        .execute()
    )

    if existing.data:
        return existing.data[0]

    created = (
        supabase.table("users")
        .insert({
            "user_code": user_code
        })
        .execute()
    )

    return created.data[0]


def get_user_memory(user_code: str):
    user = get_or_create_user(user_code)

    existing = (
        supabase.table("user_memory")
        .select("*")
        .eq("user_id", user["id"])
        .execute()
    )

    if existing.data:
        return existing.data[0]

    created = (
        supabase.table("user_memory")
        .insert({
            "user_id": user["id"],
            "health_interests": [],
            "past_recommended_products": [],
            "recurring_food_patterns": [],
            "recurring_activity_patterns": [],
            "notes": [],
        })
        .execute()
    )

    return created.data[0]


def merge_unique(existing, new_items):
    existing = existing or []

    if not isinstance(new_items, list):
        new_items = [new_items]

    result = list(existing)

    for item in new_items:
        if item and item not in result:
            result.append(item)

    return result

def log_chat_interaction(user_code: str, data: dict):
    user = get_or_create_user(user_code)

    row = {
        "user_id": user["id"],
        "question": data.get("question"),
        "answer": data.get("answer"),
        "intent": data.get("intent"),
        "detected_product": data.get("detected_product"),
        "recommended_product": data.get("recommended_product"),
        "used_memory": data.get("used_memory", False),
    }

    supabase.table("chat_interactions").insert(row).execute()

def log_recommendation(user_code: str, data: dict):
    user = get_or_create_user(user_code)

    row = {
        "user_id": user["id"],
        "recommended_products": data.get("recommended_products", []),
        "meal_recommendations": data.get("meal_recommendations", []),
        "exercise_recommendations": data.get("exercise_recommendations", []),
        "reasoning_summary": data.get("reasoning_summary"),

        "used_memory": data.get("used_memory", False),
        "used_goal": data.get("used_goal", False),
        "used_activity": data.get("used_activity", False),
        "used_bmi": data.get("used_bmi", False),
        "used_daily_checkin": data.get("used_daily_checkin", False),

        "response_time_sec": data.get("response_time_sec"),
    }

    supabase.table("recommendation_logs").insert(row).execute()


def create_daily_checkin(user_code: str, data: dict):
    user = get_or_create_user(user_code)

    row = {
        "user_id": user["id"],
        "mood": data.get("mood"),
        "notes": data.get("notes"),
    }

    result = (
        supabase.table("daily_checkins")
        .upsert(row, on_conflict="user_id,checkin_date")
        .execute()
    )

    return result.data[0]
def log_daily_meal(checkin_id: int, data: dict):
    row = {
        "checkin_id": checkin_id,
        "meal_type": data.get("meal_type", "general"),
        "description": data.get("description"),
        "estimated_calories": data.get("estimated_calories"),
        "estimated_protein": data.get("estimated_protein"),
    }

    supabase.table("daily_meal_logs").insert(row).execute()


def log_daily_activity(checkin_id: int, data: dict):
    row = {
        "checkin_id": checkin_id,
        "activity_type": data.get("activity_type", "general"),
        "duration_minutes": data.get("duration_minutes"),
        "intensity": data.get("intensity"),
        "estimated_calories_burned": data.get("estimated_calories_burned"),
    }

    supabase.table("daily_activity_logs").insert(row).execute()

def get_recent_checkins(user_code: str, limit: int = 7):
    user = get_or_create_user(user_code)

    checkins_res = (
        supabase.table("daily_checkins")
        .select("*")
        .eq("user_id", user["id"])
        .order("checkin_date", desc=True)
        .limit(limit)
        .execute()
    )

    checkins = checkins_res.data or []

    for checkin in checkins:
        meals_res = (
            supabase.table("daily_meal_logs")
            .select("*")
            .eq("checkin_id", checkin["id"])
            .execute()
        )

        activities_res = (
            supabase.table("daily_activity_logs")
            .select("*")
            .eq("checkin_id", checkin["id"])
            .execute()
        )

        checkin["daily_meal_logs"] = meals_res.data or []
        checkin["daily_activity_logs"] = activities_res.data or []

    return checkins

def get_user_profile(user_code: str) -> dict:
    user = get_or_create_user(user_code)

    profile_id = user.get("profile_id")

    if not profile_id:
        return {}

    res = (
        supabase.table("user_profiles")
        .select("*")
        .eq("id", profile_id)
        .execute()
    )

    if res.data:
        return res.data[0]

    return {}

def upsert_user_profile(user_code: str, profile_data: dict):
    user = get_or_create_user(user_code)

    row = {
        "name": profile_data.get("name") or user_code,
        "age": profile_data.get("age"),
        "height": profile_data.get("height"),
        "height_unit": "cm",
        "weight": profile_data.get("weight"),
        "weight_unit": "kg",
        "sex": profile_data.get("sex"),
        "goals": profile_data.get("goals", []),
        "language": profile_data.get("language", "ar"),
    }

    if user.get("profile_id"):
        res = (
            supabase.table("user_profiles")
            .update(row)
            .eq("id", user["profile_id"])
            .execute()
        )
        return res.data[0] if res.data else row

    res = supabase.table("user_profiles").insert(row).execute()
    profile = res.data[0]

    supabase.table("users").update({
        "profile_id": profile["id"]
    }).eq("id", user["id"]).execute()

    return profile
def update_user_memory(user_code: str, new_data: dict):
    user = get_or_create_user(user_code)
    current = get_user_memory(user_code)

    allowed_fields = {
        "health_interests",
        "last_detected_issue",
        "last_recommended_product",
        "past_recommended_products",
        "recurring_food_patterns",
        "recurring_activity_patterns",
        "last_meal_summary",
        "last_activity_summary",
        "consistency_score",
        "notes",
        "trend_analysis",
    }

    list_fields = {
        "health_interests",
        "past_recommended_products",
        "recurring_food_patterns",
        "recurring_activity_patterns",
        "notes",
    }

    update_data = {}

    for key, value in new_data.items():
        if key not in allowed_fields:
            continue

        if value is None or value == "":
            continue

        if key in list_fields:
            update_data[key] = merge_unique(
                current.get(key),
                value
            )
        else:
            update_data[key] = value

    if not update_data:
        return

    (
        supabase.table("user_memory")
        .update(update_data)
        .eq("user_id", user["id"])
        .execute()
    )