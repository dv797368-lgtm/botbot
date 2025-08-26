#!/usr/bin/env python
# coding: utf-8

import os
import time
import hmac
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

# --- تهيئة البوت وتطبيق Flask ---
if not BOT_TOKEN:
    print("!!! FATAL ERROR: BOT_TOKEN not found in environment variables.")
    # لا نستخدم exit() للسماح للخادم بالعمل، لكنه لن يعمل بدون توكن
    
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ====== دالة توليد التوقيع (signature) ======
def sign_request(params, secret):
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    query = "".join([f"{k}{v}" for k, v in sorted_params])
    query_to_sign = secret + query + secret
    return hmac.new(secret.encode("utf-8"), query_to_sign.encode("utf-8"), hashlib.md5).hexdigest().upper()

# ====== استعلام API من AliExpress ======
def get_aliexpress_product(product_id):
    url = "https://api-sg.aliexpress.com/sync"
    params = {
        "method": "aliexpress.affiliate.productdetail.get",
        "app_key": APP_KEY,
        "timestamp": str(int(time.time() * 1000)),
        "format": "json",
        "v": "2.0",
        "sign_method": "hmac",
        "product_ids": product_id,
        "target_currency": CURRENCY_CODE,
        "target_language": "EN",
        "ship_to_country": SHIP_TO_COUNTRY,
        "tracking_id": "default"
    }
    params["sign"] = sign_request(params, APP_SECRET)
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        return {"error": str(e)}

# ====== بوت تيليجرام ======
@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message, "👋 أهلا بك! ابعث لي ID تاع المنتج من AliExpress باش نرجعلك التفاصيل.")

@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    product_id = message.text.strip()
    if not product_id.isdigit():
        bot.reply_to(message, "⚠️ من فضلك ابعث ID صالح للمنتج.")
        return
    
    data = get_aliexpress_product(product_id)
    
    # تحويل الـ JSON إلى نص منسق لسهولة القراءة
    formatted_data = json.dumps(data, indent=2, ensure_ascii=False)
    
    # إرسال النتيجة
    bot.reply_to(message, f"```json\n{formatted_data}\n```", parse_mode="MarkdownV2")

# ====== Flask Webhook ======
# هذا المسار هو الذي سيستقبل التحديثات من تليجرام
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def process_updates():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return 'Forbidden', 403

# هذا المسار يستخدمه Render للتأكد من أن التطبيق يعمل
@app.route('/')
def index():
    return "🤖 البوت شغال!", 200

# **تم حذف جميع الأكواد التي تعمل عند التشغيل المباشر**
# Gunicorn هو المسؤول عن تشغيل 'app'
