from typing import Optional


def build_decision_output(
    question: str,
    user_profile: Optional[dict],
    intent: str,
    detected_product: Optional[str],
    product_db: dict,
    quantity_offers: dict,
    bundle_offers: list,
) -> dict:
    q = question.lower().strip()
    user_profile = user_profile or {}
    weight = user_profile.get("weight")
    height_cm = user_profile.get("height")
    activity_info = str(user_profile.get("activity_info", "")).lower()
    history = str(user_profile.get("history", "")).lower()

    bmi = None
    if weight and height_cm and height_cm > 0:
        height_m = height_cm / 100
        bmi = weight / (height_m ** 2)
    goals = user_profile.get("goals", [])
    goals_text = " ".join(goals).lower() if isinstance(goals, list) else str(goals).lower()
    activity_level = "unknown"
    if any(x in activity_info for x in ["low", "sedentary", "rarely", "peu", "inactive", "lazy"]):
        activity_level = "low"
    elif any(x in activity_info for x in ["walk", "daily", "moderate", "moyen", "regular", "marche"]):
        activity_level = "moderate"
    elif any(x in activity_info for x in ["gym", "intense", "sport", "training", "high", "active"]):
        activity_level = "high"

    output = {
        "intent": intent,
        "detected_product": detected_product,
        "recommended_product": None,
        "recommendation_reason": None,
        "meal_suggestion": None,
        "calorie_info": None,
        "usage_info": None,
        "benefits_info": None,
        "precautions": None,
        "lifestyle_suggestion": None,
        "follow_up_question": None,
        "price_info": None,
        "offer_info": None,
        "bundle_offer_info": None,
        "out_of_scope": False,
    }
    if detected_product and detected_product in product_db:
        product = product_db[detected_product]
        output["recommended_product"] = detected_product
        output["recommendation_reason"] = "Based on the product or need detected from the user question."
        output["usage_info"] = product.get("usage")
        output["benefits_info"] = product.get("benefits")
        output["precautions"] = product.get("precautions")
    # 1) If product explicitly detected
    if intent == "product_recommendation":
        # digestion / constipation / bloating / kerch
        if any(w in q for w in [
            "constipation", "digest", "digestion", "colon", "bloating",
            "kerch", "belly", "stomach", "نفخة", "إمساك", "هضم", "كرش", "بطن"
        ]) or any(w in history for w in [
            "constipation", "digest", "digestion", "colon", "bloating",
            "kerch", "belly", "stomach", "نفخة", "إمساك", "هضم", "كرش", "بطن"
        ]):
            output["recommended_product"] = "Colon Detox"
            output["recommendation_reason"] = "Colon Detox is the closest Shifa product for digestion, bloating, and constipation support."

        # liver / detox
        elif any(w in q for w in [
            "liver", "kebda", "كبد", "detox", "سموم", "تنقية"
        ]) or any(w in history for w in [
            "liver", "kebda", "كبد", "detox", "سموم", "تنقية"
        ]):
            output["recommended_product"] = "Liver Detox"
            output["recommendation_reason"] = "Liver Detox is the closest Shifa product for liver-support and detox routines."

        # weight-loss recommendation based on goal + profile
        elif "weight loss" in goals_text or any(w in q for w in [
            "naqs", "lose weight", "perdre du poids", "وزن", "تنحيف", "slim"
        ]):
            if bmi and bmi >= 25:
                output["recommended_product"] = "Slim Pack"
                output["recommendation_reason"] = "Slim Pack is recommended because your goal is weight loss and your profile suggests weight-management support may fit."
            elif activity_level == "low":
                output["recommended_product"] = "Slim Pack"
                output["recommendation_reason"] = "Slim Pack is recommended because your goal is weight loss and your current activity level seems low to moderate."
            else:
                output["recommended_product"] = "Slim Pack"
                output["recommendation_reason"] = "Slim Pack is the closest Shifa product for weight-loss support."

        # if no exact product, no forced recommendation
        else:
            output["recommended_product"] = None
            output["recommendation_reason"] = "No exact Shifa product match was found from the current profile alone."

    # 3) Nutrition / meal logic
    if intent in ["meal_suggestion", "weight_loss_advice", "muscle_gain_advice", "calorie_question"]:
        if "weight loss" in goals_text or any(w in q for w in ["naqs", "lose weight", "وزن", "تنحيف"]):
            output["meal_suggestion"] = (
                "Prefer balanced meals with protein, vegetables, and moderate portions of carbs. Reduce sugar and heavy fatty meals."
            )

            if activity_level == "low":
                output["lifestyle_suggestion"] = (
                    "Try increasing daily movement gradually, like walking more often, while keeping lighter balanced meals."
                )
            else:
                output["lifestyle_suggestion"] = (
                    "Keep regular activity, hydrate well, and stay consistent with lighter balanced meals."
                )

        elif "muscle" in goals_text or any(w in q for w in ["muscle", "mass", "prise de masse", "عضلات"]):
            output["meal_suggestion"] = (
                "Focus on protein-rich meals with enough carbs and regular meal timing to support training."
            )

            if activity_level == "high":
                output["lifestyle_suggestion"] = (
                    "Since your activity seems high, combine strength training with enough protein, carbs, and recovery."
                )
            else:
                output["lifestyle_suggestion"] = (
                    "To support muscle gain, combine protein-rich meals with regular resistance training."
                )

    # 4) Calorie logic
    if intent == "calorie_question":
        if "banana" in q or "banane" in q:
            output["calorie_info"] = "A medium banana is approximately 90 to 110 kcal."
        elif "egg" in q or "oeuf" in q or "بيض" in q:
            output["calorie_info"] = "One egg is approximately 70 to 80 kcal."
        elif "bread" in q or "pain" in q or "khobz" in q:
            output["calorie_info"] = "Bread depends on type and quantity, but 100 g is often around 250 to 280 kcal."
        elif "couscous" in q or "كسكسي" in q:
            output["calorie_info"] = "Couscous calories depend on portion size and ingredients like meat, oil, and vegetables."
        else:
            output["calorie_info"] = "Calories depend on the exact food and quantity."
            output["follow_up_question"] = "Tell me the exact food and quantity and I’ll estimate it better."

    # 5) Price / offers logic
    target_product = output["recommended_product"] or detected_product
    if intent == "price_offer_query" and target_product and target_product in product_db:
        product = product_db[target_product]
        price = product.get("price")
        currency = product.get("currency", "TND")
        old_price = product.get("old_price")

        if price is not None:
            if old_price:
                output["price_info"] = f"{price} {currency} بدل {old_price} {currency}"
            else:
                output["price_info"] = f"{price} {currency}"

        if target_product in quantity_offers:
            output["offer_info"] = quantity_offers[target_product]

        for offer in bundle_offers:
            if target_product in offer.get("products", []):
                output["bundle_offer_info"] = offer

    # 6) Product details fallback
    final_product = output["recommended_product"] or detected_product
    if final_product and final_product in product_db:
        product = product_db[final_product]
        output["usage_info"] = output["usage_info"] or product.get("usage")
        output["benefits_info"] = output["benefits_info"] or product.get("benefits")
        output["precautions"] = output["precautions"] or product.get("precautions")

    # 7) No Shifa product for muscle gain
    if intent == "muscle_gain_advice" and not output["recommended_product"]:
        output["recommendation_reason"] = (
            "There is no specific mapped Shifa product for muscle gain in the current knowledge base."
        )

    return output