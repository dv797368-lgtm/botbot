import os
import time
import hmac
import hashlib
import requests
from flask import Flask, request, jsonify
import telebot

# ====== متغيرات البيئة ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_KEY = os.getenv("ALIEXPRESS_APP_KEY")
APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET")
CURRENCY_CODE = os.getenv("CURRENCY_CODE", "USD")
SHIP_TO_COUNTRY = os.getenv("SHIP_TO_COUNTRY", "DZ")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ====== دالة توليد التوقيع (signature) ======
def sign_request(params, secret):
    sorted_params = sorted(params.items(), key=lambda x: x[0])  # ترتيب البارامترات
    query = "".join([f"{k}{v}" for k, v in sorted_params])
    query = secret + query + secret
    return hmac.new(secret.encode("utf-8"), query.encode("utf-8"), hashlib.md5).hexdigest().upper()

# ====== استعلام API من AliExpress ======
def get_aliexpress_product(product_id):
    url = "https://api.taobao.com/router/rest"
    params = {
        "method": "aliexpress.affiliate.productdetail.get",
        "app_key": APP_KEY,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "2.0",
        "sign_method": "hmac",
        "product_ids": product_id,
        "target_currency": CURRENCY_CODE,
        "target_language": "EN",
        "ship_to_country": SHIP_TO_COUNTRY
    }
    params["sign"] = sign_request(params, APP_SECRET)
    response = requests.get(url, params=params)
    return response.json()

# ====== بوت تيليجرام ======
@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message, "👋 أهلا! ابعث لي ID تاع المنتج من AliExpress باش نرجعلك التفاصيل.")

@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    product_id = message.text.strip()
    if not product_id.isdigit():
        bot.reply_to(message, "⚠️ من فضلك ابعث ID صالح للمنتج.")
        return
    try:
        data = get_aliexpress_product(product_id)
        bot.reply_to(message, str(data))
    except Exception as e:
        bot.reply_to(message, f"❌ صار خطأ: {e}")

# ====== Flask Routes ======
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "🤖 البوت شغال على Render/محلي!"})

@app.route("/webhook", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200   # ✅ Telegram لازم ياخذ 200

# ====== التشغيل محليًا ======
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
