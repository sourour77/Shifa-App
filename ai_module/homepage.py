from ai_module.user_memory_db import get_user_memory, update_user_memory
from ai_module.recommendation_agent import build_recommendation_agent_output


def get_homepage_recommendation(user_profile: dict):
    user_profile = user_profile or {}

    user_id = user_profile.get("user_id", "demo_user")
    memory = get_user_memory(user_id)

    agent_output = build_recommendation_agent_output(user_profile)

    recommended_products = agent_output.get("recommended_products", [])

    if recommended_products:
        first_product = recommended_products[0].get("product")

        update_user_memory(user_id, {
            "last_recommended_product": first_product,
            "past_recommended_products": [p.get("product") for p in recommended_products if p.get("product")]
        })

    return agent_output