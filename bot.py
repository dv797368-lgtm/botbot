import os
import time
import hashlib
import requests
from flask import Flask, request
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
    sorted_params = sorted(params.items(), key=lambda x: x[0])  # ترتيب بارامترات
    query = "".join([f"{k}{v}" for k, v in sorted_params])
    query = secret + query + secret
    return hashlib.md5(query.encode("utf-8")).hexdigest().upper()

# ====== استعلام API من AliExpress ======
def get_aliexpress_product(product_id):
    url = "https://api.taobao.com/router/rest"
    params = {
        "method": "aliexpress.affiliate.productdetail.get",
        "app_key": APP_KEY,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "2.0",
        "sign_method": "md5",
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
    bot.reply_to(message, "👋 أهلا بك! ابعث لي ID تاع المنتج من AliExpress باش نرجعلك التفاصيل.")

@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    product_id = message.text.strip()
    if not product_id.isdigit():
        bot.reply_to(message, "⚠️ من فضلك ابعث ID صالح للمنتج (أرقام فقط).")
        return

    data = get_aliexpress_product(product_id)

    try:
        product = data["aliexpress_affiliate_productdetail_get_response"]["result"]["products"][0]
        title = product.get("product_title", "بدون عنوان")
        url = product.get("promotion_link", "❌ ماكانش رابط")
        price = product.get("target_sale_price", "❌ ماكانش سعر")

        reply = f"📦 {title}\n💰 السعر: {price} {CURRENCY_CODE}\n🔗 الرابط: {url}"
    except Exception as e:
        reply = f"❌ ماقدرتش نجيب التفاصيل.\nالرد من API:\n{data}"

    bot.reply_to(message, reply)

# ====== Flask Webhook ======
@app.route("/", methods=["POST", "GET"])
def index():
    if request.method == "POST":
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        bot.process_new_updates([update])
        return "OK", 200   # ✅ مهم: لازم نرجع كود 200
    return "🤖 البوت شغال!", 200

if __name__ == "__main__":
    # ✅ Render يفرض PORT في متغير البيئة
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
