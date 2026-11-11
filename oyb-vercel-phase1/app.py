import logging
import os

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

KEYWORDS = {
    "hair": ["hair", "hairfall", "hair fall", "hair loss", "thinning", "thin hair", "hair growth", "dandruff", "biotin"],
    "sleep": ["sleep", "insomnia", "sleepless", "can't sleep", "cannot sleep", "poor sleep", "relax", "stress"],
    "beauty": ["beauty", "skin", "glow", "glowing", "dark spots", "melanin", "complexion", "skin tone"],
    "energy": ["omega", "omega 3", "omega-3", "heart", "brain", "cardiovascular"],
    "health": ["health", "multivitamin", "multivitamins", "vitamin", "immunity", "immune", "energy", "tired", "fatigue"],
}


def detect_categories(message):
    msg = message.lower()
    return [category for category, terms in KEYWORDS.items() if any(term in msg for term in terms)]


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

        msg = user_message.lower()
        categories = detect_categories(user_message)

        if msg in {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}:
            return jsonify({"reply": "👋 Welcome to OYB (Own Your Body)! I can help you explore Hair, Sleep, Beauty, Energy and General Health products. What would you like to know?"})

        matched = [p for p in products_data if p["category"] in categories]
        if matched:
            session["last_product"] = matched[0]["name"]
            cards = []
            for p in matched[:2]:
                cards.append(
                    f'''<div class="product-card"><img src="{p['image']}" alt="{p['name']}" onerror="this.style.display='none'"><br><b>{p['name']}</b><br>⭐ {p['rating']} / 5<br><br>{p['desc']}<br><br><b>{p['price']}</b><br><a href="{p['link']}" target="_blank" rel="noopener">🛒 View Product</a></div>'''
                )
            return jsonify({"reply": "<p>Here are products related to your query:</p>" + "".join(cards)})

        last_product_name = session.get("last_product")
        product = next((p for p in products_data if p["name"] == last_product_name), None)
        if product:
            if any(term in msg for term in ["why", "explain", "details", "about"]):
                return jsonify({"reply": f"<b>{product['name']}</b><br>{product['desc']}<br>Please check the product page for its complete ingredient and label information."})
            if any(term in msg for term in ["safe", "side effect", "side effects", "doctor"]):
                return jsonify({"reply": "Please review the product label and consult a qualified healthcare professional before use, especially if you have a medical condition, take medication, are pregnant or breastfeeding, or have allergies. I can't assess individual safety."})
            if any(term in msg for term in ["how to use", "usage", "dose", "dosage"]):
                return jsonify({"reply": f"Please follow the directions printed on the {product['name']} packaging. I don't want to guess the dosage."})
            if any(term in msg for term in ["buy", "purchase", "price", "order"]):
                return jsonify({"reply": f"You can view {product['name']} here: <a href=\"{product['link']}\" target=\"_blank\" rel=\"noopener\">View product</a>. Listed price in the chatbot: {product['price']}. Please confirm the current price on the product page."})

        if any(term in msg for term in ["suggest", "recommend", "product"]):
            return jsonify({"reply": "Sure! Which area are you interested in: Hair, Sleep, Beauty, Energy/Heart support, or General Health?"})

        if client:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=(
                    "You are the OYB wellness product assistant. Be concise, factual and non-diagnostic. "
                    "Do not invent ingredients, benefits, prices, dosage, safety or medical claims. "
                    "For medical questions, advise consulting a qualified healthcare professional. "
                    f"Customer question: {user_message}"
                ),
            )
            answer = response.text or "I couldn't prepare an answer just now. Please try again."
        else:
            answer = "The AI assistant is not configured yet. Please try a product category, or contact OYB for help."
        return jsonify({"reply": answer})

    except Exception:
        logging.exception("Chatbot request failed")
        return jsonify({"reply": "Sorry, something went wrong. Please try again in a moment."}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
