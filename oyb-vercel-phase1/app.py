import logging
import os
import re
import unicodedata

from flask import Flask, jsonify, render_template, request, session
from google import genai

logging.basicConfig(level=logging.INFO)

# Vercel serves files in /public through its CDN. Flask templates remain in /templates.
app = Flask(__name__, static_folder="public", static_url_path="")
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)

api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

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

# Phrase-based matching intentionally uses complete words/phrases, not loose
# substring matching. These are customer-language cues, not medical diagnoses.
KEYWORDS = {
    "hair": [
        "hair", "hair care", "haircare", "hair fall", "hairfall", "falling hair",
        "hair loss", "losing hair", "hair thinning", "thinning hair", "thin hair",
        "weak hair", "brittle hair", "dry hair", "damaged hair", "rough hair",
        "frizzy hair", "frizz", "hair breakage", "hair breaking", "breakage",
        "hair growth", "grow hair", "faster hair growth", "long hair", "thicker hair",
        "hair density", "receding hairline", "baldness", "bald spot", "scalp", "itchy scalp",
        "dandruff", "flaky scalp", "split ends", "biotin", "nac", "zinc for hair",
        "weak roots", "hair roots", "hair nourishment", "hair strength", "premature greying",
        "grey hair", "gray hair", "alopecia", "shedding", "excessive shedding",
    ],
    "sleep": [
        "sleep", "sleeping", "sleep care", "sleep wellness", "better sleep", "poor sleep",
        "deep sleep", "good sleep", "sleep quality", "can't sleep", "cannot sleep",
        "unable to sleep", "difficulty sleeping", "trouble sleeping", "fall asleep",
        "stay asleep", "waking up at night", "wake up at night", "insomnia", "sleepless",
        "sleeplessness", "restless sleep", "night routine", "sleep schedule", "sleep cycle",
        "relax", "relaxation", "calm", "unwind", "stress relief", "feeling stressed",
        "stress", "stressed", "feeling stressed", "tension", "overthinking at night", "mind won't switch off",
    ],
    "beauty": [
        "beauty", "skin", "skin care", "skincare", "glowing skin", "glow", "dull skin",
        "skin glow", "bright skin", "radiant skin", "uneven skin tone", "skin tone",
        "dark spots", "dark spot", "spots on face", "pigmentation", "hyperpigmentation",
        "melanin", "complexion", "blemishes", "skin blemishes", "skin wellness",
        "healthy skin", "skin health", "dry skin", "skin texture", "face marks",
        "sun spots", "age spots", "tanning", "tan", "skin appearance",
    ],
    "energy": [
        "energy", "omega", "omega 3", "omega-3", "omega three", "fish oil", "heart", "heart health",
        "healthy heart", "cardiovascular", "cardiovascular health", "brain", "brain health",
        "brain function", "heart function", "heart support", "dha", "epa", "essential fatty acids",
    ],
    "health": [
        "health", "general health", "overall health", "wellness", "multivitamin", "multivitamins",
        "multi vitamin", "multi vitamins", "daily top up", "daily top-up", "daily vitamin",
        "vitamin", "vitamins", "vitamin deficiency", "nutrients", "nutrition", "nutritional support",
        "immunity", "immune", "immune system", "immune support", "immunity support",
        "low energy", "energy levels", "tired", "tiredness", "fatigue", "feeling tired",
        "feel exhausted", "exhaustion", "weakness", "general wellness", "daily wellness",
        "daily nutrition", "nutrient support", "vitamin support",
    ],
}

FOLLOW_UP_GROUPS = {
    "price": ["price", "cost", "how much", "rate", "pricing", "mrp"],
    "buy": ["buy", "purchase", "order", "where can i get", "where to buy", "buy now", "link"],
    "usage": ["how to use", "how do i take", "when to take", "usage", "dosage", "dose", "directions", "serving"],
    "safety": ["safe", "safety", "side effect", "side effects", "allergy", "allergic", "pregnant", "breastfeeding", "medication", "medicine", "interactions"],
    "details": ["why", "explain", "details", "tell me more", "more information", "what is this", "benefits", "ingredients", "composition", "what does it do"],
}


def normalize_text(value):
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = re.sub(r"[^\w\s'-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def phrase_in_text(phrase, text):
    """Match a phrase on word boundaries to avoid accidental substring hits."""
    phrase = normalize_text(phrase)
    if not phrase:
        return False
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text) is not None


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


def product_card(product):
    return (
        f"<div class=\"product-card\"><img src=\"{product['image']}\" "
        f"alt=\"{product['name']}\" onerror=\"this.style.display='none'\"><br>"
        f"<b>{product['name']}</b><br>⭐ {product['rating']} / 5<br><br>"
        f"{product['desc']}<br><br><b>{product['price']}</b><br>"
        f"<a href=\"{product['link']}\" target=\"_blank\" rel=\"noopener\">🛒 View Product</a></div>"
    )


def answer_product_follow_up(product, intent):
    if intent == "price":
        return (f"The chatbot's listed price for <b>{product['name']}</b> is {product['price']}. "
                "Please check the product page for the latest price and availability.")
    if intent == "buy":
        return (f"You can view <b>{product['name']}</b> here: "
                f"<a href=\"{product['link']}\" target=\"_blank\" rel=\"noopener\">View product</a>.")
    if intent == "usage":
        return (f"Please follow the directions printed on the <b>{product['name']}</b> packaging. "
                "I don't want to guess the dosage. Ask a qualified healthcare professional if unsure.")
    if intent == "safety":
        return ("Please review the product label and consult a qualified healthcare professional before use, "
                "especially if you have a medical condition, take medication, are pregnant or breastfeeding, "
                "or have allergies. I can't assess individual safety.")
    if intent == "details":
        return (f"<b>{product['name']}</b><br>{product['desc']}<br>For verified ingredients and full product "
                "information, please check the official product page.")
    return None


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "gemini_configured": bool(client)})


@app.post("/get_response")
def get_response():
    try:
        data = request.get_json(silent=True) or {}
        user_message = (data.get("message") or "").strip()
        if not user_message:
            return jsonify({"reply": "Please enter a question."}), 400

        msg = normalize_text(user_message)
        if msg in {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "good evening oyb"}:
            return jsonify({"reply": "👋 Welcome to OYB (Own Your Body)! I can help you explore Hair, Sleep, Beauty, Energy and General Health products. What would you like to know?"})

        # Handle follow-ups against the last product before detecting new concerns.
        last_product_name = session.get("last_product")
        product = next((p for p in products_data if p["name"] == last_product_name), None)
        follow_up = detect_follow_up(user_message)
        if product and follow_up:
            reply = answer_product_follow_up(product, follow_up)
            if reply:
                return jsonify({"reply": reply})

        categories = detect_categories(user_message)
        if categories:
            matched = [p for p in products_data if p["category"] in categories]
            if matched:
                session["last_product"] = matched[0]["name"]
                cards = "".join(product_card(p) for p in matched[:3])
                category_names = ", ".join(c.title() for c in categories)
                return jsonify({"reply": f"<p>I understood you're asking about {category_names}. Here are related OYB products:</p>{cards}"})

        if any(phrase_in_text(term, msg) for term in ["suggest", "recommend", "product", "what do you sell", "catalog", "show products"]):
            return jsonify({"reply": "Sure! Which area are you interested in: Hair, Sleep, Beauty, Energy/Heart support, or General Health?"})

        if client:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=(
                    "You are the OYB (Own Your Body) wellness product assistant. Answer the customer's actual question "
                    "helpfully and clearly, even if it does not match a product keyword. You may answer general questions, "
                    "but do not pretend every question is about an OYB product. Use only these verified product facts: "
                    "Good Hair Day: hair support; label highlights Biotin, Zinc and NAC; listed price ₹466. "
                    "Sleep Wellness: supports sleep and relaxation; listed price ₹499. "
                    "Beauty Wellness: supports skin wellness; listed price ₹499. "
                    "Omega-3: pure Omega-3 support for a healthy heart; listed price ₹499. "
                    "Daily Top-up Multivitamins: multivitamins for daily energy and immunity support; listed price ₹499. "
                    "Do not invent ingredients, clinical evidence, benefits, prices, stock, delivery details, dosage, or medical claims. "
                    "If asked for details not supplied here, say you do not have verified information and direct them to the official "
                    "product page or OYB support. Never diagnose, prescribe, or claim a supplement treats or cures a disease. "
                    "For medical symptoms, medication interactions, pregnancy, breastfeeding, allergies, or safety questions, "
                    "recommend a qualified healthcare professional. If the question is unrelated to wellness, answer briefly "
                    "if appropriate and politely explain that you are OYB's wellness assistant. Keep the answer concise and natural.\n\n"
                    f"Customer question: {user_message}"
                ),
            )
            answer = response.text or "I couldn't prepare an answer just now. Please try again or contact OYB support."
        else:
            answer = ("I can help with OYB's Hair, Sleep, Beauty, Energy and General Health products. "
                      "The AI assistant is temporarily unavailable for questions outside these topics.")
        return jsonify({"reply": answer})

    except Exception:
        logging.exception("Chatbot request failed")
        return jsonify({"reply": "Sorry, something went wrong. Please try again in a moment."}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
