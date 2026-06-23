import os
from dotenv import load_dotenv
from openai import OpenAI
from ai_module.decision_engine import build_decision_output
from ai_module.user_memory_db import (
    get_user_memory,
    get_user_profile,
    update_user_memory,
    log_chat_interaction
)
from ai_module.product_db import (
    get_product_knowledge_dict,
    get_quantity_offers_dict,
    get_bundle_offers
)
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in .env file.")

client = OpenAI(api_key=api_key)

SYSTEM_PROMPT = """
You are Shifa's AI assistant, a professional nutrition and wellness assistant.

Your role:
- answer clearly about food, healthy habits, wellness, calories, and Shifa products
- use user profile if provided
- give practical and specific answers

LANGUAGE RULES:
- If the user writes in English, reply in English
- If the user writes in French, reply in French
- If the user writes in Arabic, reply in Arabic letters only
- If the user writes in Tunisian dialect, reply in Tunisian dialect using Arabic letters only
- If the user writes Tunisian dialect in Latin letters, convert your answer into Tunisian dialect written in Arabic letters
- Do not use Tunisian in Latin letters
- Do not mix Arabic letters and Latin-script Tunisian in the same answer

STRICT LANGUAGE RULE:
- For Arabic and Tunisian requests, your answer must be written only in Arabic script
- Do NOT answer Tunisian in Latin letters
- Do NOT switch to formal Arabic unless the user is clearly using formal Arabic
- If the user is Tunisian, prefer natural Tunisian darja in Arabic script

CONVERSATION MEMORY RULES:
- Use the previous conversation when the user refers to something implicitly
- If the user says things like "نستعملو", "هذا", "it", "this product", interpret them using recent chat history
- If the last discussed product is clear from the conversation, continue with that product
- Do not switch to another product unless the user explicitly changes the topic
PROFILE PRIORITY RULE:
- For nutrition, meals, calories, exercise, and healthy habit questions, always adapt the answer to the user's profile if available
- Especially use the user's goal, preferences, and activity information
- Do not give a generic answer if profile information is available
- If the user asks whether they can eat a certain food, answer according to their goal first

SCOPE RULE:
- You are only allowed to help with:
  1. Shifa products
  2. nutrition and meals
  3. calories
  4. exercise and activity
  5. healthy habits and wellness
- If the user asks about anything clearly outside these topics, do not answer the unrelated question.
- Instead, politely explain that you are Shifa's assistant and can help only with Shifa products, nutrition, calories, exercise, and wellness.
- Do not try to give partial answers for unrelated topics.

QUALITY RULES:
- Be clear and concise
- Give direct and concrete answers
- Do not give vague advice
- Do not invent facts
- Do not invent product information
- If information is missing, say clearly that you do not have it
- You must NEVER recommend or mention products that are not in the provided Shifa product knowledge base
- If no Shifa product matches the request, clearly say that no specific Shifa product is currently available for that goal

FALLBACK RULE:
- If the question is new or unclear, give a simple and general answer
- Do not invent stories
- Do not generate random names or meaningless sentences
- If unsure, give a short practical answer instead of guessing

SAFETY RULES:
- Do not give medical diagnosis
- Do not claim to cure diseases
- Do not replace a doctor or dietitian

- If the user has medical conditions, adapt advice safely.
- Do not diagnose or prescribe treatment.
- For diabetes, avoid recommending high-sugar meals or sugary drinks.
- For hypertension, avoid recommending high-salt or highly processed foods.
- For pregnancy, breastfeeding, chronic disease, or medication use, advise consulting a doctor or pharmacist before using supplements.

PRODUCT BOUNDARY RULES:
- You must NEVER mention or recommend products that are not موجودة في قاعدة معرفة Shifa
- Do not invent names like Protein Powder, Weight Gainer, or any external supplement



USAGE PRIORITY RULE:
- If the user asks how to use a product, answer first with the exact usage instructions
- Keep the answer direct and short
- Do not replace the usage instructions with general wellness advice

STYLE:
- Sound professional, helpful, and human
- Keep the answer direct and to the point
- Maximum 2 to 5 short sentences unless the user asks for details
- If product recommendation is relevant, mention it naturally
"""

TUNISIAN_EXAMPLES = """
Example:
Q: شنوة ناكل اليوم باش ننقص وزن؟
A:
حسب هدفك، تنجم تختار وجبات خفيفة ومتوازنة:
- فطور فيه بروتين + شوية غلة
- غدا فيه دجاج ولا حوت + سلطة
- عشا حاجة خفيفة كيف شوربة ولا سلطة
"""

BRAND_INFO = """
Brand: Shifa
Description: Shifa is a wellness and supplement brand.
General rule: Shifa products are dietary supplements, not medications.
They support a healthy lifestyle and do not replace medical advice.
"""

PRODUCT_KNOWLEDGE = {
    "Slim Day": {
        "name": "Slim Day",
        "category": "Weight management supplement",
        "price": 49.0,
        "currency": "TND",
        "old_price": None,
        "offer_active": False,
        "offer_title": None,
        "offer_description": None,
        "pack_size": "30 capsules",
        "description": (
            "Slim Day is a dietary supplement designed to support weight control "
            "and fat metabolism during the day."
        ),
        "benefits": [
            "supports natural weight management",
            "helps reduce fat accumulation",
            "supports fat burning and metabolism",
            "helps regulate appetite and reduce sugar cravings",
            "supports digestion and liver function",
            "helps maintain balanced blood sugar levels",
        ],
        "ingredients": [
            "Morosil red orange extract: 400 mg",
            "Green tea leaf extract: 120 mg",
            "Artichoke leaf extract: 120 mg",
            "Guarana seed extract (20% natural caffeine): 80 mg",
            "Zinc: 1.5 mg",
            "Chromium: 6 micrograms",
        ],
        "usage": (
            "Take 2 capsules daily with a large glass of water, preferably in the morning or during breakfast."
        ),
        "precautions": [
            "Dietary supplement, not a medicine",
            "For adults only",
            "Use in the morning",
            "Not recommended for pregnant or breastfeeding women",
            "Not recommended for people sensitive to caffeine",
            "If you have a medical condition or take medication, consult a doctor or pharmacist",
            "Do not exceed the recommended daily dose",
            "Keep out of reach of children",
        ],
    },

    "Slim Night": {
        "name": "Slim Night",
        "category": "Night support supplement",
        "price": 49.0,
        "currency": "TND",
        "old_price": None,
        "offer_active": False,
        "offer_title": None,
        "offer_description": None,
        "pack_size": "30 capsules",
        "description": (
            "Slim Night is a dietary supplement designed to support fat metabolism during sleep "
            "and improve sleep quality."
        ),
        "benefits": [
            "supports fat metabolism during sleep",
            "helps improve sleep quality and deep sleep",
            "promotes relaxation and calming of the nervous system",
            "may help reduce night cravings",
            "supports muscle recovery during the night",
            "supports hormonal balance related to sleep",
        ],
        "ingredients": [
            "Ashwagandha KSM-66: 200 mg",
            "GABA: 100 mg",
            "Chamomile extract: 80 mg",
            "Passionflower extract: 80 mg",
            "Valerian extract: 80 mg",
            "L-carnitine (Carnipure): 110 mg",
            "L-tryptophan: 35 mg",
            "Melatonin: 1 mg",
        ],
        "usage": (
            "Take 2 capsules in the evening with a glass of water, 30 minutes before sleep."
        ),
        "precautions": [
            "Dietary supplement, not a medicine",
            "For adults only",
            "Not recommended for pregnant or breastfeeding women",
            "If you have a medical condition or take medication, consult a doctor or pharmacist",
            "Do not exceed the recommended daily dose",
            "Keep out of reach of children",
        ],
    },

    "Slim Pack": {
        "name": "Slim Pack",
        "category": "Weight management pack",
        "price": 75.0,
        "currency": "TND",
        "old_price": 98.0,
        "offer_active": True,
        "offer_title": "Pack Offer",
        "offer_description": "Slim Day + Slim Night at a reduced bundle price.",
        "pack_size": "2 products",
        "description": (
            "Slim Pack combines Slim Day and Slim Night in a complete daytime and nighttime weight-management routine."
        ),
        "benefits": [
            "combines daytime and nighttime support",
            "supports weight management throughout the day",
            "pairs metabolism and appetite support with nighttime recovery and sleep support",
        ],
        "ingredients": [
            "Includes Slim Day",
            "Includes Slim Night",
        ],
        "usage": (
            "Use Slim Day in the morning and Slim Night in the evening according to the instructions of each product."
        ),
        "precautions": [
            "Use each product according to its own instructions and precautions",
            "Dietary supplements, not medicines",
            "Do not exceed recommended doses",
        ],
    },

    "Colon Detox": {
        "name": "Colon Detox",
        "category": "Digestive supplement",
        "price": 49.0,
        "currency": "TND",
        "old_price": 69,
        "offer_active": False,
        "offer_title": None,
        "offer_description": None,
        "pack_size": "30 capsules",
        "description": (
            "Colon Detox is a natural digestive support product designed to improve digestion, "
            "reduce bloating and gas, support bowel regularity, and help intestinal comfort."
        ),
        "benefits": [
            "supports digestion",
            "helps reduce bloating and gas",
            "supports natural relief of constipation",
            "supports intestinal regularity",
            "supports gut health and digestive comfort",
        ],
        "ingredients": [
            "Activated charcoal: 125 mg",
            "Senna: 100 mg",
            "Anise: 30 mg",
            "Fennel: 20 mg",
            "Rhubarb: 20 mg",
            "Prebiotic: 50 mg",
        ],
        "usage": (
            "Take 1 to 2 capsules with water. Follow the recommended dose on the product."
        ),
        "precautions": [
            "Dietary supplement, not a medicine",
            "Do not exceed the recommended daily dose",
            "Consult a doctor or pharmacist if needed",
            "Keep out of reach of children",
        ],
    },

    "Liver Detox": {
        "name": "Liver Detox",
        "category": "Detox supplement",
        "price": 49.0,
        "currency": "TND",
        "old_price": 69.0,
        "offer_active": False,
        "offer_title": None,
        "offer_description": None,
        "pack_size": "30 capsules",
        "description": (
            "Liver Detox is a dietary supplement developed to support liver function, natural detoxification, and digestion."
        ),
        "benefits": [
            "supports liver detoxification",
            "supports digestion",
            "helps support liver and kidney elimination functions",
            "supports bile production and digestive comfort",
            "supports liver protection and regeneration",
        ],
        "ingredients": [
            "Artichoke dry extract: 180 mg",
            "Milk thistle / Silymarin 80%: 125 mg",
            "Dandelion extract: 125 mg",
            "Desmodium: 70 mg",
        ],
        "usage": (
            "Take 2 capsules daily, preferably in the morning on an empty stomach or before meals."
        ),
        "precautions": [
            "Dietary supplement, not a medicine",
            "Do not exceed the recommended daily dose",
            "Consult a doctor or pharmacist if needed",
            "Keep out of reach of children",
        ],
    },

    "Blood Detox": {
        "name": "Blood Detox",
        "category": "Circulation and heart support supplement",
        "price": 92.0,
        "currency": "TND",
        "old_price": None,
        "offer_active": False,
        "offer_title": None,
        "offer_description": None,
        "pack_size": "30 capsules",
        "description": (
            "Blood Detox is a dietary supplement designed to support heart health, blood circulation, "
            "and the elimination of toxins related to oxidative stress and daily strain."
        ),
        "benefits": [
            "supports heart health and natural cardiovascular function",
            "helps improve blood circulation",
            "helps reduce oxidative stress",
            "supports blood pressure balance and mineral balance",
            "supports cellular energy and heart muscle function",
            "helps the body eliminate toxins linked to daily stress",
        ],
        "ingredients": [
            "Vitamin D3: 20 mg (as shown on provided packaging)",
            "Magnesium: 50 mg",
            "Potassium: 50 mg",
            "Chloride: 46 mg",
            "Olive leaf: 150 mg",
            "Garlic extract: 150 mg",
            "Curcuma 95% curcumin: 100 mg",
            "Q10: 20 mg",
            "Piperine: 15 mg",
            "Berry extract: 80 mg",
        ],
        "usage": (
            "Take 1 capsule daily after meals. Continuous use for 30 days is recommended for best results."
        ),
        "precautions": [
            "Dietary supplement, not a medicine",
            "Keep out of reach of children",
            "Not recommended for pregnant or breastfeeding women except with medical advice",
            "If you have a chronic illness or take medication, consult a specialist before use",
        ],
    },
}

BUNDLE_OFFERS = [
    {
        "bundle_name": "Liver Detox + Colon Detox",
        "products": ["Liver Detox", "Colon Detox"],
        "offer_active": True,
        "old_price": 99.0,
        "new_price": 69.0,
        "currency": "TND",
        "delivery_fee": 6.0,
        "title": "عرض ديتوكس",
        "description": "ليفير ديتوكس + كولون ديتوكس بسعر 69 د.ت عوض 99 د.ت"
    },
    {
        "bundle_name": "Slim Day + Slim Night",
        "products": ["Slim Day", "Slim Night"],
        "offer_active": True,
        "old_price": 98.0,
        "new_price": 75.0,
        "currency": "TND",
        "delivery_fee": 6.0,
        "title": "عرض Slim Pack",
        "description": "Slim Day + Slim Night بسعر bundle أقل"
    }
]

QUANTITY_OFFERS = {
    "Liver Detox": [
        {
            "quantity": 1,
            "old_price": 59.0,
            "new_price": 49.0,
            "currency": "TND",
            "discount_percent": 17,
            "delivery_fee": 6.0,
            "delivery_text": "التوصيل 6 د.ت",
            "title": "اشترِ علبة واحدة (30 كبسولة)"
        },
        {
            "quantity": 2,
            "old_price": 120.0,
            "new_price": 69.0,
            "currency": "TND",
            "discount_percent": 43,
            "delivery_fee": 6.0,
            "delivery_text": "التوصيل 6 د.ت",
            "title": "اشترِ علبتين إثنين (60 كبسولة)"
        },
        {
            "quantity": 3,
            "old_price": 180.0,
            "new_price": 89.0,
            "currency": "TND",
            "discount_percent": 51,
            "delivery_fee": 0.0,
            "delivery_text": "التوصيل مجاني",
            "title": "اشترِ ثلاثة علب (90 كبسولة)"
        }
    ],

    "Colon Detox": [
        {
            "quantity": 1,
            "old_price": 59.0,
            "new_price": 49.0,
            "currency": "TND",
            "discount_percent": 17,
            "delivery_fee": 6.0,
            "delivery_text": "التوصيل 6 د.ت",
            "title": "اشترِ علبة واحدة (30 كبسولة)"
        },
        {
            "quantity": 2,
            "old_price": 120.0,
            "new_price": 69.0,
            "currency": "TND",
            "discount_percent": 43,
            "delivery_fee": 6.0,
            "delivery_text": "التوصيل 6 د.ت",
            "title": "اشترِ علبتين إثنين (60 كبسولة)"
        },
        {
            "quantity": 3,
            "old_price": 180.0,
            "new_price": 89.0,
            "currency": "TND",
            "discount_percent": 51,
            "delivery_fee": 0.0,
            "delivery_text": "التوصيل مجاني",
            "title": "اشترِ ثلاثة علب (90 كبسولة)"
        }
    ]
}


def build_user_context(merged_profile: dict | None) -> str:
    if not merged_profile:
        return "No user profile provided."

    return f"""
User profile:
- age: {merged_profile.get('age')}
- weight: {merged_profile.get('weight')}
- height: {merged_profile.get('height')}
- goals: {merged_profile.get('goals')}
- medical_conditions: {merged_profile.get('medical_conditions')}
- activity_info: {merged_profile.get('activity_info')}
- sex: {merged_profile.get('sex')}
Daily check-in memory:
- health_interests: {merged_profile.get('health_interests')}
- recurring_food_patterns: {merged_profile.get('recurring_food_patterns')}
- recurring_activity_patterns: {merged_profile.get('recurring_activity_patterns')}
- last_meal_summary: {merged_profile.get('last_meal_summary')}
- last_activity_summary: {merged_profile.get('last_activity_summary')}
- last_detected_issue: {merged_profile.get('last_detected_issue')}
- consistency_score: {merged_profile.get('consistency_score')}
"""


def detect_product(question: str) -> str | None:
    q = question.lower()

    if "slim day" in q:
        return "Slim Day"
    if any(x in q for x in [
        "colon detox", "colon", "constipation", "digest", "digestion", "li ynadhef lcolon", "الي ينظف القولون", "gaz", "nfekh"
        "kerch", "bloating", "نفخة", "إمساك", "هضم", "كرش"
    ]):
        return "Colon Detox"
    if "slim night" in q:
        return "Slim Night"
    if any(x in q for x in [
        "semna", "kerch", "nodh3ef", "سمنة", "graisse","li ynaqes lwazn"
        "تخسيس", "نقص وزن", "naqs", "wazn", "نضعف", "كرش"
    ]):
        return "Slim Pack"


    if any(x in q for x in [
        "liver detox", "liver", "kebda", "كبد", "detox", "سموم"
    ]):
        return "Liver Detox"

    if any(x in q for x in [
        "blood detox", "blood", "circulation", "heart", "cardio", "دم", "قلب", "الي ينظف الدم", "li ysafi dam", "anxiete"
    ]):
        return "Blood Detox"

    return None

def detect_products(question: str) -> list:
    q = question.lower()
    products = []

    if "colon detox" in q or "colon" in q:
        products.append("Colon Detox")

    if "liver detox" in q or "liver" in q or "kebda" in q or "كبد" in q:
        products.append("Liver Detox")

    if "blood detox" in q or "blood" in q:
        products.append("Blood Detox")

    if "slim pack" in q:
        products.append("Slim Pack")

    if "slim day" in q:
        products.append("Slim Day")

    if "slim night" in q:
        products.append("Slim Night")

    return products

def format_delivery_info_for_products(products: list, quantity_offers_db: dict, bundle_offers_db: list) -> str:
    if not products:
        return ""

    lines = []

    # 1) Check if there is a bundle offer for these products together
    selected = set(products)

    matching_bundles = []
    for bundle in bundle_offers_db:
        bundle_products = set(bundle.get("products", []))

        if selected.issubset(bundle_products) or bundle_products.issubset(selected):
            matching_bundles.append(bundle)

    if matching_bundles:
        lines.append("عندك زادة عرض pack يجمع المنتجات هاذم:")

        for bundle in matching_bundles:
            fee = bundle.get("delivery_fee")
            delivery = "التوصيل مجاني" if fee == 0 else f"التوصيل {fee} د.ت"

            lines.append(
                f"- {bundle.get('title')}: "
                f"{bundle.get('new_price')} {bundle.get('currency')} "
                f"بدل {bundle.get('old_price')} {bundle.get('currency')}، "
                f"{delivery}."
            )

        lines.append("العرض هذا أنفع من شراء كل منتج وحدو.")

    # 2) Then show delivery per product/quantity
    for product in products:
        lines.append(f"\n{product}:")

        offers = quantity_offers_db.get(product, [])

        if offers:
            for offer in offers:
                title = offer.get("title") or f"{offer.get('quantity')} علبة"
                delivery = offer.get("delivery_text")

                if not delivery and offer.get("delivery_fee") is not None:
                    fee = offer.get("delivery_fee")
                    delivery = "التوصيل مجاني" if fee == 0 else f"التوصيل {fee} د.ت"

                lines.append(f"- {title}: {delivery}")
        else:
            lines.append("- ما عنديش تفاصيل توصيل حسب الكمية لهذا المنتج وحدو.")

    return "\n".join(lines)

def get_last_product_from_history(chat_history: list | None) -> str | None:
    if not chat_history:
        return None

    for msg in reversed(chat_history):
        content = msg.get("content", "")
        detected = detect_product(content)
        if detected:
            return detected

    return None


def is_implicit_reference(question: str) -> bool:
    q = question.lower()
    keywords = [
        "نستعملو",
        "نستعمل",
        "كيفاش نستعمل",
        "kifeh nestaamlou",
        "nestaamlou",
        "how to use it",
        "how long use it",
        "use it",
        "hedha",
        "this product",
        "ce produit",
        "قداش من شهر",
        "قداش مدة",
        "how long",
        "for how long",
    ]
    return any(k in q for k in keywords)


def detect_intent(question: str) -> str:
    q = question.lower()
    product = detect_product(question)
    if any(w in q for w in [
        "نفخة", "غازات", "كرشي", "معدة", "هضم", "امساك", "إمساك",
        "bloating", "gas", "constipation", "digestion", "nfekh", "gaz"
    ]):
        return "digestion_issue"

    if any(w in q for w in [
        "متقلق", "قلق", "stress", "stressed", "anxiety",
        "مانجمش نرقد", "ما نرقدش", "نوم", "sleep", "insomnia"
    ]):
        return "stress_sleep_issue"

    if any(word in q for word in ["hi", "hello", "aslema", "slm", "salem", "bonjour"]):
        return "greeting"
    if any(word in q for word in [
       "produit", "products", "product", "yelzmni", "يلزمني",
       "nheb produit", "شنو يلزمني", "شنوة يلزمني",
       "behi", "best", "ahsen", "haja", "solution"
    ]):
       return "product_recommendation"
    
    if any(word in q for word in [
        "livraison", "delivery", "shipping", "frais livraison",
        "توصيل", "التوصيل", "قداش التوصيل", "توصل", "livrer"
    ]):
        return "delivery_info"

    if any(word in q for word in [
        "قداش", "سعر", "ثمن", "bqadeh", "prix", "price", "soum", "how much", "combien", "bgideh"
    ]):
        return "price_offer_query"

    if any(word in q for word in [
        "عرض", "promo", "promotion", "offer"
    ]):

        return "price_offer_query"
    if any(word in q for word in ["naqs", "wazn", "ynaqsou", "lose weight", "perdre du poids", "وزن"]):
        return "weight_loss_advice"

    if any(word in q for word in ["muscle", "prise de masse", "nzid", "wazn", "mass", "عضلات"]):
        return "muscle_gain_advice"

    if any(word in q for word in ["nekil", "eat", "manger", "meal", "repas", "ftor", "ghda", "3cha", "آكل"]):
        return "meal_suggestion"

    if any(word in q for word in ["calorie", "calories", "سعرات", "حريرات", "9addech", "qaddech"]):
        return "calorie_question"

    if any(word in q for word in [
        "produit", "products", "product", "les produit", "aandkom", "3andkom",
        "behi", "best", "ahsen", "haja", "solution"
    ]) and any(word in q for word in [
        "naqs", "wazn", "ynaqsou", "lose weight", "perdre du poids", "وزن",
        "constipation", "colon", "kebda", "kerch", "digest", "digestion",
        "bloating", "نفخة", "إمساك", "هضم", "كبد", "كرش", "belly"
    ]):
        return "product_recommendation"

    if product:
        if any(word in q for word in ["faida", "faidet", "fayda", "benefit", "benefits", "bienfait", "bienfaits", "فوائد", "ya3mel"]):
            return "product_benefits"
        if any(word in q for word in ["kifeh", "comment utiliser", "how should i use", "how to use", "كيف أستعمل", "nesta3ml", "usage", "قداش من شهر", "how long"]):
            return "product_usage"
        return "product_info"
    
    

    if any(word in q for word in ["shifa", "brand", "marque", "شنية شفاء", "ما هي شفاء"]):
        return "brand_info"

    return "unknown"


def build_intent_instruction(intent: str) -> str:
    instructions = {
        "greeting": "Reply briefly and warmly.",
        "weight_loss_advice": "Give practical weight-loss advice with 2 to 4 concrete suggestions.",
        "muscle_gain_advice": "Give practical muscle-gain advice with food and habit suggestions.",
        "meal_suggestion": "Suggest meal ideas adapted to the user's goal.",
        "calorie_question": "Answer simply about calories. If exact value is unknown, say it is an estimate.",
        "product_info": "Explain clearly what the product is, based only on the provided product information.",
        "product_benefits": "Explain product benefits based only on the provided product information.",
        "product_usage": "Explain briefly how to use the product in 1 to 2 sentences.",
        "product_recommendation": "Recommend the most relevant Shifa product naturally and explain briefly why it fits the user's goal.",
        "digestion_issue": "Give digestion advice and recommend Colon Detox only if relevant.",
        "stress_sleep_issue": "Give stress/sleep wellness advice and recommend Blood Detox only if relevant.",
        "brand_info": "Answer briefly about the brand using the brand information provided.",
        "delivery_info": "Answer only about delivery fees and delivery conditions using the provided offers. Do not invent delivery information.",
        "unknown": "Give a short, clear, safe, general answer without inventing facts.",
    }
    return instructions.get(intent, instructions["unknown"])


def detect_intent_domain(question: str) -> str:
    q = question.lower()

    if any(w in q for w in [
        "hi", "hello", "aslema", "slm", "salem", "bonjour", "مرحبا", "سلام"
    ]):
        return "greeting"

    if any(w in q for w in [
        # only explicit shifa/product family signals
        "shifa", "slim day", "slim night", "slim pack",
        "colon detox", "liver detox", "blood detox",
        "colon", "liver", "blood detox",
        "constipation", "digest", "digestion", "kerch", "bloating",
        "نفخة", "إمساك", "هضم", "كرش", "كبد",
        "فوائد منتج", "كيفاش نستعمل", "سعر منتج", "عرض شفاء"
    ]):
        return "shifa_products"

    if any(w in q for w in [
        "eat", "manger", "meal", "food", "calorie", "diet", "protein", "carb",
        "fat", "fiber", "vitamin", "fruit", "vegetable", "healthy food",
        "couscous", "pizza", "riz", "bread", "banana", "egg",
        "ناكل", "اكل", "وجبة", "وجبات", "سعرات", "تغذية", "شنوة ناكل",
        "regime", "régime", "nutrition", "light meals"
    ]):
        return "nutrition"

    if any(w in q for w in [
        "exercise", "sport", "training", "workout", "cardio", "walk", "walking",
        "run", "running", "fitness", "gym", "movement",
        "رياضة", "تمرين", "تمارين", "مشي", "لياقة"
    ]):
        return "exercise"

    if any(w in q for w in [
        "health", "wellness", "sleep", "healthy", "habit", "habits",
        "lifestyle", "energy", "stress", "digestion",
        "صحة", "نوم", "عادات", "رفاهة", "توتر", "طاقة"
    ]):
        return "health_wellness"

    return "unknown"

def is_short_followup(question: str) -> bool:
    q = question.lower().strip()
    short_followups = {
        "ey", "eya", "oui", "yes", "ok", "okay",
        "and then", "ensuite", "ba3d", "mba3d",
        "more", "akther", "زيد", "عادي", "donc", "alors"
    }
    return q in short_followups

def recommend_shifa_product(question: str, merged_profile: dict | None = None) -> tuple[str | None, str | None]:
    q = question.lower()
    goals = merged_profile.get("goals", []) if merged_profile else []
    goals_text = " ".join(goals).lower() if isinstance(goals, list) else str(goals).lower()

    # digestion / constipation / belly / bloating
    if any(w in q for w in [
        "constipation", "digest", "digestion", "colon", "bloating",
        "kerch", "belly", "stomach", "نفخة", "إمساك", "هضم", "كرش", "بطن"
    ]):
        return "Colon Detox", "هذا المنتج هو الأقرب لدعم الهضم، الانتفاخ، والإمساك."

    # liver / detox
    if any(w in q for w in [
        "liver", "detox", "kebda", "كبد", "تنقية", "سموم"
    ]):
        return "Liver Detox", "هذا المنتج هو الأقرب لدعم الكبد والتنقية."
    if any(w in q for w in [
        "متقلق", "قلق", "stress", "stressed", "anxiety",
        "مانجمش نرقد", "ما نرقدش", "نوم", "sleep", "insomnia"
    ]):
        return "Blood Detox", "هذا المنتج هو الأقرب لدعم التوازن، الدورة الدموية، والتعب المرتبط بالضغط اليومي."
    # weight loss / slimming
    if any(w in q for w in [
        "naqs", "wazn", "lose weight", "perdre du poids", "slim", "وزن", "تنحيف", "semna", "kerch", "nodh3ef", "سمنة", "graisse",
        "تخسيس", "نقص وزن", "نضعف", "كرش"
    ]) or "weight loss" in goals_text:
        return "Slim Pack", "هذا المنتج هو الأقرب لدعم نقص الوزن."

    return None, None


def is_out_of_scope(question: str, chat_history: list | None = None) -> bool:
    q = question.lower().strip()
    chat_history = chat_history or []

    short_followups = {
        "ey", "eyy", "oui", "yes", "ok", "okay", "d'accord", "dakord", "dacc",
        "aslema", "salem", "hello", "hi",
        "and then", "ensuite", "ba3d", "mba3d", "more", "akther", "زيد"
    }
    if q in short_followups:
        return False

    intent = detect_intent(question)
    domain = detect_intent_domain(question)

    if intent in [
        "greeting",
        "price_offer_query",
        "weight_loss_advice",
        "muscle_gain_advice",
        "meal_suggestion",
        "calorie_question",
        "product_recommendation",
        "product_benefits",
        "product_usage",
        "product_info",
        "brand_info",
    ]:
        return False

    if domain in ["greeting", "shifa_products", "nutrition", "exercise", "health_wellness"]:
        return False

    last_product = get_last_product_from_history(chat_history)
    if last_product and len(q.split()) <= 4:
        return False

    return is_clearly_unrelated(question)
 
def is_clearly_unrelated(question: str) -> bool:
    q = question.lower().strip()

    unrelated_keywords = [
        "instagram caption", "caption", "bio instagram", "post caption",
        "who is", "qui est", "capital", "history",
        "actor", "actress", "singer", "movie", "football", "politics",
        "president", "programming", "math", "python code", "java code",
        "مغني", "ممثل", "سياسة", "رئيس", "عاصمة", "تاريخ", "كود", "معادلة",
        "شيرين", "سعد لمجرد"
    ]

    person_question_starters = [
        "chkoun", "chkun", "qui", "who is", "taarfou", "ta3ref", "تعرف", "شكون"
    ]

    in_scope_keywords = [
        "shifa", "slim", "colon", "liver", "blood detox",
        "nutrition", "diet", "meal", "food", "eat", "manger",
        "calorie", "exercise", "sport", "health", "wellness",
        "protein", "muscle", "sleep", "digestion", "healthy",
        "ناكل", "تغذية", "رياضة", "صحة", "سعرات", "هضم", "وزن", "كرش", "إمساك",
        "عضلات", "نوم", "طاقة", "وجبة", "وجبات"
    ]

    if any(q.startswith(x) for x in person_question_starters) and not any(k in q for k in in_scope_keywords):
        return True

    if any(k in q for k in unrelated_keywords):
        return True

    return False

def build_out_of_scope_answer(question: str) -> str:
    return (
        "نعتذر، أنا مساعد شفاء ومجالي يقتصر على منتجات شفاء، التغذية، السعرات، "
        "العادات الصحية والرفاهة. إذا تحب، اسألني مثلاً على فوائد منتج، طريقة استعماله، "
        "السعر، أو نصائح غذائية حسب هدفك."
    )

def is_price_or_offer_question(question: str) -> bool:
    q = question.lower()
    keywords = [
        "price", "prix", "thmen", "soum", "قداش", "سعر",
        "offer", "promo", "promotion", "عرض",
        "1", "2", "3", "piece", "pieces", "علبة", "علبتين", "ثلاثة"
    ]
    return any(k in q for k in keywords)


def format_quantity_offers(product_name: str | None, quantity_offers_db: dict) -> str:
    if not product_name or product_name not in quantity_offers_db:
        return ""

    offers = quantity_offers_db[product_name]

    formatted = ["Available quantity offers:"]

    for offer in offers:
        formatted.append(
            f"- {offer.get('title')}: "
            f"{offer.get('new_price')} {offer.get('currency')} "
            f"بدل {offer.get('old_price')} {offer.get('currency')} "
            f"({offer.get('discount_percent')}% تخفيض)، "
            f"{offer.get('delivery_text')}"
        )

    return "\n".join(formatted)

def get_last_intent_from_history(chat_history: list | None) -> str | None:
    if not chat_history:
        return None

    for msg in reversed(chat_history):
        content = msg.get("content", "")
        if "التوصيل" in content or "livraison" in content or "delivery" in content:
            return "delivery_info"

    return None

def get_best_quantity_offer(product_name: str | None, quantity_offers_db: dict) -> str:
    if not product_name or product_name not in quantity_offers_db:
        return ""

    offers = quantity_offers_db[product_name]
    best = max(offers, key=lambda x: x.get("discount_percent", 0))

    return (
        f"Best value offer: {best.get('title')} "
        f"بسعر {best.get('new_price')} {best.get('currency')} "
        f"بدل {best.get('old_price')} {best.get('currency')} "
        f"({best.get('discount_percent')}% discount), {best.get('delivery_text')}."
    )

def format_product_context(product_name: str | None, product_db: dict) -> str:
    if not product_name or product_name not in product_db:
        return ""

    p = product_db[product_name]

    benefits = "\n".join([f"- {b}" for b in p.get("benefits", [])])
    ingredients = "\n".join([f"- {i}" for i in p.get("ingredients", [])])
    precautions = "\n".join([f"- {pr}" for pr in p.get("precautions", [])])

    return f"""
Product name: {p.get('name', '')}
Category: {p.get('category', '')}
Price: {p.get('price', '')} {p.get('currency', '')}
Old price: {p.get('old_price', '')}
Offer active: {p.get('offer_active', False)}
Offer title: {p.get('offer_title', '')}
Offer description: {p.get('offer_description', '')}
Pack size: {p.get('pack_size', '')}

Description:
{p.get('description', '')}

Benefits:
{benefits}

Ingredients:
{ingredients}

Usage:
{p.get('usage', '')}

Precautions:
{precautions}
"""

def format_chat_history(chat_history: list | None) -> str:
    if not chat_history:
        return "No previous conversation."

    formatted = []
    for msg in chat_history[-6:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        formatted.append(f"{role}: {content}")

    return "\n".join(formatted)



def chatbot_response(question, user_profile=None, chat_history=None):
    chat_history = chat_history or []
    user_profile = user_profile or {}
    user_id = user_profile.get("user_id", "demo_user")
    stored_memory = get_user_memory(user_id)
    stored_profile = get_user_profile(user_id)
    product_db = get_product_knowledge_dict()
    quantity_offers_db = get_quantity_offers_dict()
    bundle_offers_db = get_bundle_offers()
    merged_profile = {
        "user_id": user_id,
        "age": user_profile.get("age") or stored_profile.get("age"),
        "sex": user_profile.get("sex") or stored_profile.get("sex"),
        "weight": user_profile.get("weight") or stored_profile.get("weight"),
        "height": user_profile.get("height") or stored_profile.get("height"),
        "goals": user_profile.get("goals") or stored_profile.get("goals", []),
        "medical_conditions": user_profile.get("medical_conditions") or stored_profile.get("medical_conditions", []),
        "activity_info": user_profile.get("activity_info") or stored_memory.get("activity_info"),
    # Daily check-in memory
        "health_interests": stored_memory.get("health_interests", []),
        "recurring_food_patterns": stored_memory.get("recurring_food_patterns", []),
        "recurring_activity_patterns": stored_memory.get("recurring_activity_patterns", []),
        "last_meal_summary": stored_memory.get("last_meal_summary"),
        "last_activity_summary": stored_memory.get("last_activity_summary"),
        "last_detected_issue": stored_memory.get("last_detected_issue"),
        "consistency_score": stored_memory.get("consistency_score"),
    }

    if is_out_of_scope(question, chat_history):
        answer = build_out_of_scope_answer(question)
        log_chat_interaction(user_id, {
            "question": question,
            "answer": answer,
            "intent": "out_of_scope",
            "detected_product": None,
            "recommended_product": None,
            "used_memory": bool(stored_memory),
        })
        return {
            "answer": answer,
            "intent": "out_of_scope",
            "detected_product": None,
            "recommended_product": None,
            "recommendation_reason": None,
            "meal_suggestion": None,
            "calorie_info": None,
            "usage_info": None,
            "benefits_info": None,
            "precautions": None,
            "lifestyle_suggestion": None,
            "follow_up_question": "تنجم تسألني على منتجات شفاء، التغذية، السعرات، أو العادات الصحية.",
            "price_info": None,
            "offer_info": None
        }
    intent = detect_intent(question)
    last_intent = get_last_intent_from_history(chat_history)

    if intent == "product_info" and last_intent == "delivery_info":
         intent = "delivery_info"
    profile_nutrition_rule = ""
    if intent in ["meal_suggestion", "weight_loss_advice", "calorie_question", "muscle_gain_advice"] or detect_intent_domain(question) in ["nutrition", "exercise", "health_wellness"]:
        profile_nutrition_rule = """
    For this question, you must adapt the answer to the user's profile.
    If the user asks about a food, evaluate it according to the user's goal.
    Example:
    - if the goal is weight loss, suggest moderation, lighter portions, and healthier combinations
    - if the goal is muscle gain, suggest enough protein and balanced carbs
    Do not answer in a generic way if profile information exists.
    """  
    detected_product = detect_product(question)
    last_product = get_last_product_from_history(chat_history)
    detected_products = detect_products(question)

    if intent == "delivery_info" and detected_products:
        delivery_info = format_delivery_info_for_products(
            detected_products,
            quantity_offers_db,
            bundle_offers_db
        )

        answer = f"أكيد، هاني نعطيك معلومات التوصيل حسب المنتج والكمية:\n{delivery_info}"

        return {
            "answer": answer,
            "intent": "delivery_info",
            "detected_product": ", ".join(detected_products),
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
            "offer_info": delivery_info,
        }
    if intent == "delivery_info" and not detected_product:
        answer = "على أنهي منتج تحب تعرف التوصيل؟ 🚚\nالتوصيل يختلف حسب الكمية، وفي بعض العروض يكون مجاني 😉"

        return {
            "answer": answer,
            "intent": "delivery_info",
            "detected_product": None,
            "recommended_product": None,
            "recommendation_reason": None,
            "meal_suggestion": None,
            "calorie_info": None,
            "usage_info": None,
            "benefits_info": None,
            "precautions": None,
            "lifestyle_suggestion": None,
            "follow_up_question": answer,
            "price_info": None,
            "offer_info": None,
        }

    if not detected_product and is_implicit_reference(question):
        detected_product = last_product

    decision = build_decision_output(
        question=question,
        user_profile=merged_profile,
        intent=intent,
        detected_product=detected_product,
        product_db=product_db,
        quantity_offers=quantity_offers_db,
        bundle_offers=bundle_offers_db,
    )

    recommended_product = decision["recommended_product"]
    recommendation_reason = decision["recommendation_reason"]
    usage = decision["usage_info"]
    benefits = decision["benefits_info"]

    quantity_offers = format_quantity_offers(detected_product or recommended_product, quantity_offers_db)
    best_quantity_offer = get_best_quantity_offer(detected_product or recommended_product, quantity_offers_db)
    # RULES
    usage_rule = ""
    if intent == "product_usage":
        usage_rule = "Answer ONLY with usage instructions."

    price_rule = ""
    if intent in ["price_offer_query", "delivery_info"]:
        price_rule = """
    The user is asking about price, offer, or delivery.
    You must answer with available price/offers/delivery info from the provided product offers.
    If the question is only about delivery, focus only on delivery.
    Do not invent delivery fees.

    Keep the answer short, clear, and sales-oriented without sounding aggressive.
    """
    recommended_product_context = format_product_context(recommended_product, product_db)

    recommended_quantity_offers = format_quantity_offers(
        recommended_product,
        quantity_offers_db
    )

    recommended_best_offer = get_best_quantity_offer(
        recommended_product,
        quantity_offers_db
    )


    decision_context = f"""
    Decision layer output:
    - intent: {decision['intent']}
    - detected_product: {decision['detected_product']}
    - recommended_product: {decision['recommended_product']}
    - recommendation_reason: {decision['recommendation_reason']}
    - usage_info: {decision['usage_info']}
    - benefits_info: {decision['benefits_info']}
    - price_info: {decision['price_info']}
    - meal_suggestion: {decision['meal_suggestion']}
    - calorie_info: {decision['calorie_info']}
    - lifestyle_suggestion: {decision['lifestyle_suggestion']}
    - follow_up_question: {decision['follow_up_question']}
    """
    # PROMPT
    messages = [
        {"role": "system", "content": "Answer in Arabic only."},
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": TUNISIAN_EXAMPLES},
        {"role": "system", "content": f"Detected intent: {intent}"},
        
        {"role": "system", "content": f"Brand information:\n{BRAND_INFO}"},
        {"role": "system", "content": usage_rule},
        {"role": "system", "content": price_rule},
        {
            "role": "system",
            "content": """
        If the user asks about livraison/delivery/توصيل:
        - Use delivery_text or delivery_fee from quantity offers and bundle offers.
        - If 1 or 2 boxes have delivery fee, mention it.
        - If 3 boxes have free delivery, mention it.
        - Do not invent delivery information.
         """
        },
        {"role": "system", "content": f"Recommended best offer:\n{recommended_best_offer}"},
        
        {"role": "system", "content": f"Intent instruction: {build_intent_instruction(intent)}"},

        {"role": "system", "content": f"Best quantity offer:\n{best_quantity_offer}"},

        {"role": "system", "content": f"Product context:\n{format_product_context(detected_product, product_db)}"},
        {"role": "system", "content": f"Recommended product context:\n{format_product_context(recommended_product, product_db)}"},

        {"role": "system", "content": f"Offers:\n{quantity_offers}"},
        {"role": "system", "content": f"Recommended product offers:\n{format_quantity_offers(recommended_product, quantity_offers_db)}"},

        {"role": "system", "content": f"Recommendation reason: {recommendation_reason}"},

        {"role": "system", "content": f"User context:\n{build_user_context(merged_profile)}"},
        {"role": "system", "content": profile_nutrition_rule},

        {
            "role": "system",
            "content": """
    If the user asks for a product recommendation, you must recommend only products from Shifa.
    Do not mention generic supplement categories.
    If a relevant Shifa product exists, name it directly.
    For digestion, constipation, bloating, belly discomfort, or 'kerch', prefer Colon Detox.
    For liver or detox support, prefer Liver Detox.
    For weight loss, prefer Slim Pack.
    Never mention products, categories, or supplements that are not in the Shifa knowledge base.
    """
        },

        {
            "role": "system",
            "content": f"""
    Decision summary:
    - detected_product: {detected_product}
    - recommended_product: {recommended_product}
    - recommendation_reason: {recommendation_reason}
    """
        },

        {"role": "system", "content": decision_context},

        {"role": "system", "content": f"History:\n{format_chat_history(chat_history)}"},
        {"role": "user", "content": question}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.2
    )

    answer = response.choices[0].message.content
    log_chat_interaction(user_id, {
        "question": question,
        "answer": answer,
        "intent": decision["intent"],
        "detected_product": decision["detected_product"],
        "recommended_product": decision["recommended_product"],
        "used_memory": bool(stored_memory),
    })
    memory_update = {
        "last_recommended_product": decision.get("recommended_product"),
    }

    health_interests = []
    notes = []
    q = question.lower()

    if any(w in q for w in ["constipation", "digest", "digestion", "colon", "bloating", "kerch", "نفخة", "إمساك", "هضم", "كرش"]):
        health_interests.append("digestion")
        notes.append("asked about digestion")
    if any(w in q for w in ["متقلق", "قلق", "stress", "anxiety", "مانجمش نرقد", "ما نرقدش", "نوم", "sleep"]):
        health_interests.append("stress_anxiety")
        notes.append("asked about stress or sleep")

    if any(w in q for w in ["liver", "detox", "kebda", "كبد", "سموم"]):
        health_interests.append("detox")
        notes.append("asked about liver or detox")

    if any(w in q for w in ["naqs", "lose weight", "perdre du poids", "وزن", "تنحيف", "slim"]):
        health_interests.append("weight_loss")
        notes.append("interested in weight loss")

    if any(w in q for w in ["muscle", "mass", "prise de masse", "عضلات"]):
        health_interests.append("muscle_gain")
        notes.append("interested in muscle gain")

    if health_interests:
        memory_update["health_interests"] = health_interests

    if decision.get("recommended_product"):
        memory_update["past_recommended_products"] = [decision["recommended_product"]]

    if notes:
        memory_update["notes"] = notes

    update_user_memory(user_id, memory_update)

    return {
        "answer": answer,
        "intent": decision["intent"],
        "detected_product": decision["detected_product"],
        "recommended_product": decision["recommended_product"],
        "recommendation_reason": decision["recommendation_reason"],
        "meal_suggestion": decision["meal_suggestion"],
        "calorie_info": decision["calorie_info"],
        "usage_info": decision["usage_info"],
        "benefits_info": decision["benefits_info"],
        "precautions": decision["precautions"],
        "lifestyle_suggestion": decision["lifestyle_suggestion"],
        "follow_up_question": decision["follow_up_question"],
        "price_info": decision["price_info"],
        "offer_info": decision["offer_info"],
    }
 