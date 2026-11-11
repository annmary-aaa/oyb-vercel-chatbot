
import logging
import os
import re
import unicodedata

from flask import Flask, jsonify, render_template, request, session
from google import genai
from supabase import create_client

logging.basicConfig(level=logging.INFO)

# Flask configuration
app = Flask(__name__, static_folder="public", static_url_path="")
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)

# Gemini configuration
api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

# Supabase configuration
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

supabase = None

if supabase_url and supabase_key:
    try:
        supabase = create_client(supabase_url, supabase_key)
        logging.info("Supabase client initialized.")
    except Exception:
        logging.exception("Supabase initialization failed.")

# OYB Products
products_data = [
    {
        "name": "Good Hair Day",
        "price": "₹466",
        "desc": "Hair support with Biotin, Zinc & NAC",
        "category": "hair",
        "link": "https://oyb.co.in/products/good-hair-day",
        "image": "/static/hair.png",
        "rating": "4.5",
    },
    {
        "name": "Sleep Wellness",
        "price": "₹499",
        "desc": "Supports sleep and relaxation",
        "category": "sleep",
        "link": "https://oyb.co.in/products/azzzleep",
        "image": "/static/sleep.png",
        "rating": "4.4",
    },
    {
        "name": "Beauty Wellness",
        "price": "₹499",
        "desc": "Supports skin wellness",
        "category": "beauty",
        "link": "https://oyb.co.in/products/glow",
        "image": "/static/beauty.png",
        "rating": "4.6",
    },
    {
        "name": "Omega-3",
        "price": "₹499",
        "desc": "Pure Omega-3 support for a healthy heart",
        "category": "energy",
        "link": "https://oyb.co.in/products/omega",
        "image": "/static/omega.png",
        "rating": "4.5",
    },
    {
        "name": "Daily Top-up Multivitamins",
        "price": "₹499",
        "desc": "Multivitamins for daily energy and immunity support",
        "category": "health",
        "link": "https://oyb.co.in/products/daily-top-up",
        "image": "/static/multi.png",
        "rating": "4.4",
    },
]

# Category keywords
KEYWORDS = {
    "hair": [
        "hair", "hair care", "haircare", "hair fall", "hairfall",
        "falling hair", "hair loss", "losing hair", "hair thinning",
        "thinning hair", "thin hair", "weak hair", "brittle hair",
        "dry hair", "damaged hair", "rough hair", "frizzy hair",
        "frizz", "hair breakage", "hair breaking", "breakage",
        "hair growth", "grow hair", "faster hair growth", "long hair",
        "thicker hair", "hair density", "receding hairline", "baldness",
        "bald spot", "scalp", "itchy scalp", "dandruff", "flaky scalp",
        "split ends", "biotin", "nac", "zinc for hair", "weak roots",
        "hair roots", "hair nourishment", "hair strength",
        "premature greying", "grey hair", "gray hair", "alopecia",
        "shedding", "excessive shedding",
    ],
    "sleep": [
        "sleep", "sleeping", "sleep care", "sleep wellness",
        "better sleep", "poor sleep", "deep sleep", "good sleep",
        "sleep quality", "can't sleep", "cannot sleep",
        "unable to sleep", "difficulty sleeping", "trouble sleeping",
        "fall asleep", "stay asleep", "waking up at night",
        "wake up at night", "insomnia", "sleepless", "sleeplessness",
        "restless sleep", "night routine", "sleep schedule",
        "sleep cycle", "relax", "relaxation", "calm", "unwind",
        "stress relief", "feeling stressed", "stress", "stressed",
        "tension", "overthinking at night", "mind won't switch off",
    ],
    "beauty": [
        "beauty", "skin", "skin care", "skincare", "glowing skin",
        "glow", "dull skin", "skin glow", "bright skin", "radiant skin",
        "uneven skin tone", "skin tone", "dark spots", "dark spot",
        "spots on face", "pigmentation", "hyperpigmentation",
        "melanin", "complexion", "blemishes", "skin blemishes",
        "skin wellness", "healthy skin", "skin health", "dry skin",
        "skin texture", "face marks", "sun spots", "age spots",
        "tanning", "tan", "skin appearance",
    ],
    "energy": [
        "energy", "omega", "omega 3", "omega-3", "omega three",
        "fish oil", "heart", "heart health", "healthy heart",
        "cardiovascular", "cardiovascular health", "brain",
        "brain health", "brain function", "heart function",
        "heart support", "dha", "epa", "essential fatty acids",
    ],
    "health": [
        "health", "general health", "overall health", "wellness",
        "multivitamin", "multivitamins", "multi vitamin",
        "multi vitamins", "daily top up", "daily top-up",
        "daily vitamin", "vitamin", "vitamins", "vitamin deficiency",
        "nutrients", "nutrition", "nutritional support", "immunity",
        "immune", "immune system", "immune support",
        "immunity support", "low energy", "energy levels", "tired",
        "tiredness", "fatigue", "feeling tired", "feel exhausted",
        "exhaustion", "weakness", "general wellness",
        "daily wellness", "daily nutrition", "nutrient support",
        "vitamin support",
    ],
}

FOLLOW_UP_GROUPS = {
    "price": ["price", "cost", "how much", "rate", "pricing", "mrp"],
    "buy": ["buy", "purchase", "order", "where can i get",
            "where to buy", "buy now", "link"],
    "usage": ["how to use", "how do i take", "when to take",
              "usage", "dosage", "dose", "directions", "serving"],
    "safety": ["safe", "safety", "side effect", "side effects",
               "allergy", "allergic", "pregnant", "breastfeeding",
               "medication", "medicine", "interactions"],
    "details": ["why", "explain", "details", "tell me more",
                "more information", "what is this", "benefits",
                "ingredients", "composition", "what does it do"],
}


def normalize_text(value):
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = re.sub(r"[^\w\s'-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def phrase_in_text(phrase, text):
    phrase = normalize_text(phrase)

    if not phrase:
        return False

    return re.search(
        r"(?<!\w)" + re.escape(phrase) + r"(?!\w)",
        text
    ) is not None


def detect_categories(message):
    msg = normalize_text(message)
    detected = []

    for category, phrases in KEYWORDS.items():
        if any(phrase_in_text(phrase, msg) for phrase in phrases):
            detected.append(category)

    return detected


def detect_follow_up(message):
    msg = normalize_text(message)

    for intent, phrases in FOLLOW_UP_GROUPS.items():
        if any(phrase_in_text(phrase, msg) for phrase in phrases):
            return intent

    return None


# Save customer enquiries to Supabase
def save_customer_enquiry(data, user_message):
    if supabase is None:
        logging.warning(
            "Supabase is not configured. Enquiry was not saved."
        )
        return False

    try:
        categories = detect_categories(user_message)
        category = categories[0] if categories else "general"

        # Keep the previous product category for follow-up questions.
        if category == "general":
            last_product_name = session.get("last_product")

            last_product = next(
                (
                    item for item in products_data
                    if item["name"] == last_product_name
                ),
                None,
            )

            if last_product:
                category = last_product["category"]

        enquiry = {
            "name": (data.get("name") or "").strip() or None,
            "email": (data.get("email") or "").strip() or None,
            "phone": (data.get("phone") or "").strip() or None,
            "category": category,
            "user_query": user_message,
        }

        supabase.table("customer_enquiries").insert(
            enquiry
        ).execute()

        logging.info(
            "Customer enquiry saved. Category: %s",
            category
        )

        return True

    except Exception:
        logging.exception(
            "Could not save customer enquiry to Supabase."
        )
        return False


def product_card(product):
    return (
        f"<div class=\"product-card\"><img src=\"{product['image']}\" "
        f"alt=\"{product['name']}\" "
        f"onerror=\"this.style.display='none'\"><br>"
        f"<b>{product['name']}</b><br>"
        f"⭐ {product['rating']} / 5<br><br>"
        f"{product['desc']}<br><br>"
        f"<b>{product['price']}</b><br>"
        f"<a href=\"{product['link']}\" target=\"_blank\" "
        f"rel=\"noopener\">🛒 View Product</a></div>"
    )


def answer_product_follow_up(product, intent):

    if intent == "price":
        return (
            f"The chatbot's listed price for "
            f"<b>{product['name']}</b> is {product['price']}. "
            "Please check the product page for the latest "
            "price and availability."
        )

    if intent == "buy":
        return (
            f"You can view <b>{product['name']}</b> here: "
            f"<a href=\"{product['link']}\" target=\"_blank\" "
            f"rel=\"noopener\">View product</a>."
        )

    if intent == "usage":
        return (
            f"Please follow the directions printed on the "
            f"<b>{product['name']}</b> packaging. "
            "I don't want to guess the dosage. "
            "Ask a qualified healthcare professional if unsure."
        )

    if intent == "safety":
        return (
            "Please review the product label and consult a "
            "qualified healthcare professional before use, "
            "especially if you have a medical condition, take "
            "medication, are pregnant or breastfeeding, or have "
            "allergies. I can't assess individual safety."
        )

    if intent == "details":
        return (
            f"<b>{product['name']}</b><br>{product['desc']}<br>"
            "For verified ingredients and full product "
            "information, please check the official product page."
        )

    return None


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "gemini_configured": bool(client),
        "supabase_configured": bool(supabase),
    })


@app.post("/get_response")
def get_response():

    try:
        data = request.get_json(silent=True) or {}

        user_message = (data.get("message") or "").strip()

        if not user_message:
            return jsonify({
                "reply": "Please enter a question."
            }), 400

        # Store the customer's message in Supabase.
        # Database errors will not stop chatbot replies.
        save_customer_enquiry(data, user_message)

        msg = normalize_text(user_message)

        # Greeting handling
        if msg in {
            "hi", "hello", "hey", "good morning",
            "good afternoon", "good evening",
            "good evening oyb"
        }:
            return jsonify({
                "reply": (
                    "👋 Welcome to OYB (Own Your Body)! "
                    "I can help you explore Hair, Sleep, Beauty, "
                    "Energy and General Health products. "
                    "What would you like to know?"
                )
            })

        # Ingredient-specific questions
        ingredient_terms = [
            "melatonin", "biotin", "zinc", "nac",
            "omega-3", "omega 3", "omega three",
            "vitamin d", "vitamin b12", "magnesium",
            "collagen", "ashwagandha", "iron",
            "folic acid", "dha", "epa"
        ]

        ingredient_query = (
            any(phrase_in_text(term, msg)
                for term in ingredient_terms)
            or any(
                phrase_in_text(term, msg)
                for term in [
                    "ingredient", "ingredients", "contains",
                    "contain", "has in it", "have in it",
                    "composition"
                ]
            )
        )

        if ingredient_query:

            if any(
                phrase_in_text(term, msg)
                for term in ["biotin", "zinc", "nac"]
            ):
                return jsonify({
                    "reply": (
                        "The information provided for "
                        "<b>Good Hair Day</b> lists Biotin, Zinc "
                        "and NAC. Its listed price is ₹466. "
                        "For the complete ingredient amounts and "
                        "label details, please check the product "
                        "packaging or official product page: "
                        "<a href='https://oyb.co.in/products/"
                        "good-hair-day' target='_blank' "
                        "rel='noopener'>Good Hair Day</a>."
                    )
                })

            if phrase_in_text("melatonin", msg):
                return jsonify({
                    "reply": (
                        "You're looking for an OYB product that "
                        "contains <b>melatonin</b>. I can confirm "
                        "that OYB's <b>Sleep Wellness</b> product "
                        "is described as supporting sleep and "
                        "relaxation, but the product information "
                        "currently available to me does not list "
                        "its ingredients. So I cannot confirm "
                        "that it contains melatonin or recommend "
                        "it as a melatonin product. Please check "
                        "the product label or ask OYB support to "
                        "verify the ingredients: "
                        "<a href='https://oyb.co.in/products/"
                        "azzzleep' target='_blank' "
                        "rel='noopener'>Sleep Wellness "
                        "product page</a>."
                    )
                })

        # Follow-up questions about the previous product
        last_product_name = session.get("last_product")

        product = next(
            (
                p for p in products_data
                if p["name"] == last_product_name
            ),
            None,
        )

        follow_up = detect_follow_up(user_message)

        if product and follow_up:
            reply = answer_product_follow_up(
                product,
                follow_up
            )

            if reply:
                return jsonify({"reply": reply})

        # Category detection
        categories = detect_categories(user_message)

        if categories:
            matched = [
                p for p in products_data
                if p["category"] in categories
            ]

            if matched:
                session["last_product"] = matched[0]["name"]

                cards = "".join(
                    product_card(p) for p in matched[:3]
                )

                category_names = ", ".join(
                    c.title() for c in categories
                )

                return jsonify({
                    "reply": (
                        f"<p>I understood you're asking about "
                        f"{category_names}. Here are related "
                        f"OYB products:</p>{cards}"
                    )
                })

        # Product recommendation prompt
        if (not ingredient_query) and any(
            phrase_in_text(term, msg)
            for term in [
                "suggest", "recommend", "product",
                "what do you sell", "catalog",
                "show products"
            ]
        ):
            return jsonify({
                "reply": (
                    "I can help you find a relevant OYB product. "
                    "Tell me the concern or goal you have in mind—"
                    "for example, hair support, sleep and relaxation, "
                    "skin wellness, heart support, or daily nutrition. "
                    "If you're looking for a specific ingredient, "
                    "tell me its name and I'll check only the "
                    "ingredient information that is verified "
                    "in the product details."
                )
            })

        # Gemini response
        if client:

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=(
                    "You are the OYB (Own Your Body) customer "
                    "wellness assistant. Your job is to answer "
                    "the customer's actual question, not merely "
                    "detect keywords. First identify what they "
                    "are asking, then explain the answer in plain, "
                    "friendly language. For ordinary informational "
                    "questions, give a useful explanation in about "
                    "4-7 sentences, or use short bullet points "
                    "when that is clearer. Define unfamiliar terms "
                    "and include a simple example where useful. "
                    "Do not give one-line generic replies when an "
                    "explanation is requested. If the question is "
                    "ambiguous, provide the most likely helpful "
                    "general answer and ask one focused follow-up "
                    "question instead of refusing to answer. If you "
                    "genuinely do not know, say what you can explain "
                    "and what detail is missing; never pretend to "
                    "know. You may answer general wellness and "
                    "everyday informational questions even when "
                    "no product keyword matches, but politely "
                    "remind users that you are OYB's wellness "
                    "assistant when the topic is far outside wellness.\n\n"

                    "VERIFIED OYB PRODUCT FACTS (do not add "
                    "unsupported details): "
                    "Good Hair Day: hair support; the supplied "
                    "label highlights Biotin, Zinc and NAC; "
                    "listed price ₹466. "
                    "Sleep Wellness: supports sleep and relaxation; "
                    "listed price ₹499. "
                    "Beauty Wellness: supports skin wellness; "
                    "listed price ₹499. "
                    "Omega-3: pure Omega-3 support for a healthy "
                    "heart; listed price ₹499. "
                    "Daily Top-up Multivitamins: multivitamins for "
                    "daily energy and immunity support; listed "
                    "price ₹499. "
                    "Do not invent ingredients, clinical evidence, "
                    "product benefits, prices, stock, delivery "
                    "details, dosage, or medical claims. If asked "
                    "for unavailable product details, explain that "
                    "the information is not in the verified product "
                    "data and direct the customer to the official "
                    "product page or OYB support. Never diagnose, "
                    "prescribe, or claim a supplement treats or "
                    "cures a disease. For symptoms, medication "
                    "interactions, pregnancy, breastfeeding, "
                    "allergies, or individual safety, provide "
                    "general information only and recommend a "
                    "qualified healthcare professional. Do not "
                    "state a supplement is universally safe. "
                    "Be respectful, conversational, specific, "
                    "and transparent.\n\n"

                    f"Customer question: {user_message}"
                ),
            )

            answer = response.text or (
                "I can help with that, but I couldn't generate "
                "a complete explanation just now. In general, "
                "it's best to check reliable information and "
                "consider your own circumstances. Could you "
                "rephrase your question or tell me which part "
                "you want explained?"
            )

        else:
            answer = (
                "I can still help with general wellness guidance. "
                "A useful starting point is to describe the concern, "
                "when it happens, and what you have already tried. "
                "I can explain general information and help you "
                "explore the OYB categories—Hair, Sleep, Beauty, "
                "Energy and General Health. The AI answer service "
                "is not connected right now, so I won't guess at "
                "details I cannot verify. What would you like "
                "to understand?"
            )

        return jsonify({"reply": answer})

    except Exception:
        logging.exception("Chatbot request failed")

        fallback = (
            "I understood your question, but the AI answer service "
            "is temporarily having trouble. I can still help you "
            "narrow it down: are you asking about an OYB product, "
            "general wellness information, or something else? "
            "Please try once more in a little while."
        )

        return jsonify({"reply": fallback}), 200


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
