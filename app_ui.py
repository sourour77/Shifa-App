import streamlit as st
import requests
import re
from ai_module.homepage import get_homepage_recommendation
from ai_module.recommendation_agent import build_recommendation_agent_output
from ai_module.checkin_agent import build_daily_checkin_output
from ai_module.user_memory_db import (
    update_user_memory,
    create_daily_checkin,
    log_daily_meal,
    log_daily_activity
)
from ai_module.checkin_agent import analyze_recent_trends
from ai_module.user_memory_db import get_recent_checkins
from ai_module.checkin_agent import compute_consistency_from_recent_checkins
from ai_module.user_memory_db import get_user_profile, upsert_user_profile
st.set_page_config(page_title="Marhbe Bik FI Shifa ✨🌱", page_icon="💬", layout="centered")

# ---------- Helpers ----------
def contains_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text))

def render_bubble(content: str, role: str):
    if role == "user":
        bg = "#f1f3f6"
        align = "left"
        icon = "🧑"
    else:
        bg = "#ffffff"
        align = "left"
        icon = "🤖"

    direction = "rtl" if contains_arabic(content) else "ltr"

    st.markdown(
        f"""
        <div style="
            background:{bg};
            padding:14px 16px;
            border-radius:14px;
            margin-bottom:10px;
            border:1px solid #e6e8eb;
            direction:{direction};
            text-align:{align};
            line-height:1.8;
            font-size:18px;
            unicode-bidi: plaintext;
            word-break: break-word;
        ">
            <div style="font-size:15px; opacity:0.75; margin-bottom:6px;">{icon}</div>
            <div>{content}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ---------- Page ----------
st.title("Marhbe Bik FI Shifa ✨🌱")
st.write("Ask about products, nutrition, calories, or healthy habits.")

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("User Profile")

    user_id = st.text_input("User ID", value="demo_user")
    saved_profile = get_user_profile(user_id)

    name = st.text_input(
        "Name",
        value=saved_profile.get("name") or user_id
    )
    
    language = st.selectbox(
        "Language",
        ["ar", "fr"],
        index=0
    )

    age = st.number_input(
        "Age",
        min_value=0,
        max_value=120,
        value=int(saved_profile.get("age") or 24)
    )

    sex_options = ["", "Male", "Female"]
    saved_sex = saved_profile.get("sex") or ""
    sex = st.selectbox(
        "Sex",
        sex_options,
        index=sex_options.index(saved_sex) if saved_sex in sex_options else 0
    )

    weight = st.number_input(
        "Weight (kg)",
        min_value=0.0,
        max_value=300.0,
        value=float(saved_profile.get("weight") or 70.0)
    )

    height = st.number_input(
        "Height (cm)",
        min_value=50.0,
        max_value=250.0,
        value=float(saved_profile.get("height") or 165.0)
    )

    goals_text = st.text_input(
        "Goals",
        value=", ".join(saved_profile.get("goals") or ["weightloss"])
    )

    goals = [g.strip() for g in goals_text.split(",") if g.strip()]

    if st.button("Save profile"):
        upsert_user_profile(user_id, {
            "name": name,
            "age": age,
            "height": height,
            "weight": weight,
            "sex": sex,
            "goals": goals,
            "language": language,
        })
        st.success("Profile saved.")

goals = [g.strip() for g in goals_text.split(",") if g.strip()]
user_profile = {
    "user_id": user_id,
    "name": name,
    "age": age,
    "weight": weight,
    "height": height,
    "sex": sex,
    "goals": goals,
    "language": language,
}

st.subheader("Daily Check-in Agent")

meals_today = st.text_area("What did you eat today?")
activity_today = st.text_area("What activity did you do today?")
mood = st.selectbox("Mood", ["", "good", "tired", "stressed", "happy", "low"])

if st.button("Analyze my day"):
    checkin_result = build_daily_checkin_output(
        user_profile=user_profile,
        meals_today=meals_today,
        activity_today=activity_today,
        mood=mood
        
    )
    
    checkin = create_daily_checkin(
        user_profile.get("user_id", "demo_user"),
        {
            "mood": mood,
            "notes": f"Consistency score: {checkin_result['consistency_score']}"
        }
    )

    energy = checkin_result.get("energy_estimation", {})

    log_daily_meal(
        checkin["id"],
        {
            "meal_type": "general",
            "description": meals_today,
            "estimated_calories": energy.get("estimated_calories_in"),
            "estimated_protein": None,
        }
    )

    log_daily_activity(
        checkin["id"],
        {
            "activity_type": "general",
            "description": activity_today,
            "intensity": checkin_result["activity_level_today"],
            "estimated_calories_burned": energy.get("estimated_calories_burned"),
        }
    )
    
    recent_checkins = get_recent_checkins(user_id, limit=7)
    consistency_result = compute_consistency_from_recent_checkins(recent_checkins)

    checkin_result["memory_updates"]["consistency_score"] = consistency_result["score"]
    checkin_result["memory_updates"]["notes"] = checkin_result["memory_updates"].get("notes", []) + [
        f"Consistency level: {consistency_result['level']}",
        consistency_result["summary"]
    ]
    
    trend_analysis = analyze_recent_trends(recent_checkins)
    checkin_result["memory_updates"]["trend_analysis"] = trend_analysis
    checkin_result["memory_updates"]["notes"] = checkin_result["memory_updates"].get("notes", []) + [
        f"Trend direction: {trend_analysis['trend_direction']}",
        trend_analysis["insight"]
    ]

    if checkin_result["product_hint"]:
        st.success(f"Suggested product: {checkin_result['product_hint']}")

    st.write(f"Consistency score: {checkin_result['consistency_score']}/100")

    if energy:
        st.markdown("### Daily Energy Insight")

        st.write(f"Calories consumed: {energy.get('estimated_calories_in')}")
        st.write(f"Calories burned: {energy.get('estimated_calories_burned')}")
        st.write(f"Net calories: {energy.get('estimated_net_calories')}")
        st.write(f"Weight trend: {energy.get('weight_trend')}")
        st.write(
            f"Estimated weekly change: {energy.get('estimated_weekly_weight_change_kg')} kg"
        )

        for a in energy.get("assumptions", []):
            st.write(f"- {a}")

        if energy.get("insight_message"):
            st.info(energy.get("insight_message"))
    st.markdown("### Trend Analysis")
    st.write(f"Trend: {trend_analysis['trend_direction']}")
    st.write(trend_analysis["insight"])
    update_user_memory(
        user_profile.get("user_id", "demo_user"),
        checkin_result["memory_updates"]
    )

    st.success("Daily check-in saved to memory.")

agent_rec = get_homepage_recommendation(user_profile)

st.subheader("Personalized Recommendation Agent")

st.markdown("### Recommended Products")
for item in agent_rec["recommended_products"]:
    st.success(item["product"])
    st.write(item["reason"])

    offer = item.get("offer")
    if offer:
        if "new_price" in offer:
            st.write(f"Best offer: {offer.get('title')} → {offer.get('new_price')} {offer.get('currency')}")
        else:
            st.write(f"Bundle offer: {offer.get('description')}")



st.markdown("### Meal Recommendations")

for meal in agent_rec["meal_recommendations"]:
    st.write(f"🍽️ {meal.get('title')}")
    st.write(meal.get("recommendation"))
    st.caption(meal.get("reason"))

st.markdown("### Exercise Recommendations")

for ex in agent_rec["exercise_recommendations"]:
    st.write(f"🏃 {ex.get('title')}")
    st.write(ex.get("recommendation"))
    st.caption(ex.get("reason"))
if agent_rec.get("behavioral_insight"):
    st.info(agent_rec["behavioral_insight"])

if agent_rec.get("motivation_message"):
    st.success(agent_rec["motivation_message"])

st.subheader("Chat")

for msg in st.session_state.messages:
    render_bubble(msg["content"], msg["role"])

user_input = st.chat_input("Write your message here...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    render_bubble(user_input, "user")

    payload = {
    "question": user_input,
    "user_id": user_id,
    "age": age,
    "weight": weight,
    "height": height,
    "goals": goals or [],

    "chat_history": st.session_state.messages[-6:]
    }

    try:
        response = requests.post("http://127.0.0.1:8000/chat", json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        bot_reply = data.get("response", "No response returned.")
    except Exception as e:
        bot_reply = f"Error: {e}"

    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    render_bubble(bot_reply, "assistant")

