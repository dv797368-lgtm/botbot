#!/usr/bin/env python
# coding: utf-8

import telebot
from telebot import types
from aliexpress_api import AliexpressApi, models
import re
import requests
import json
from urllib.parse import quote
import traceback
from datetime import datetime
import os
from flask import Flask, request
import time

# --- Configuration Settings from Environment Variables ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALIEXPRESS_APP_KEY = os.getenv("ALIEXPRESS_APP_KEY")
ALIEXPRESS_APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET")
CURRENCY_CODE = os.getenv("CURRENCY_CODE", "USD")
SHIP_TO_COUNTRY = os.getenv("SHIP_TO_COUNTRY", "DZ") # تم التحديث إلى الجزائر بناءً على الكود الجديد

# --- Bot Initialization ---
if not BOT_TOKEN:
    print("!!! FATAL ERROR: BOT_TOKEN not found in environment variables.")
    exit()

bot = telebot.TeleBot(BOT_TOKEN)
aliexpress = AliexpressApi(
    ALIEXPRESS_APP_KEY, 
    ALIEXPRESS_APP_SECRET,
    models.Language.AR, 
    CURRENCY_CODE, 
    'default',
    ship_to_country=SHIP_TO_COUNTRY
)

# --- Flask App for Webhook ---
app = Flask(__name__)

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def process_updates():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Forbidden', 403

@app.route('/')
def index():
    return "Bot is running!", 200

# --- Keyboard Definitions ---
def create_keyboards():
    keyboard_start = types.InlineKeyboardMarkup(row_width=1)
    btn_discount = types.InlineKeyboardButton("⭐️ تخفيض العملات على منتجات السلة 🛒 ⭐️", callback_data='click')
    keyboard_start.add(btn_discount)

    keyboard_offers = types.InlineKeyboardMarkup(row_width=1)
    btn_channel = types.InlineKeyboardButton("✨ اشترك في قناتنا لأقوى العروض ✨", url="https://t.me/bestpromo0")
    keyboard_offers.add(btn_channel)
    return keyboard_start, keyboard_offers

KEYBOARD_START, KEYBOARD_OFFERS = create_keyboards()

# --- Utility Functions ---
def escape_markdown_v2(text: str) -> str:
    if not text: return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join('\\' + char if char in escape_chars else char for char in str(text))
    
def extract_product_id_from_url(url: str) -> str:
    try:
        final_url = url
        if ("a.aliexpress.com" in url or "s.click.aliexpress.com" in url) and "aff_fcid=" not in url:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=15)
            final_url = response.url
        patterns = [r'/item/(\d{8,})\.html', r'/i/(\d{8,})\.html', r'productId=(\d{8,})', r'id=(\d{8,})']
        for pattern in patterns:
            match = re.search(pattern, final_url)
            if match: return match.group(1)
        return None
    except Exception: return None

def get_product_details(product_id: str) -> dict:
    try:
        details = aliexpress.get_products_details([product_id])
        if details:
            product = details[0]
            return {'title': product.product_title,'price': getattr(product, 'promotion_price', None) or getattr(product, 'target_sale_price', None),'image_url': product.product_main_image_url,'store_name': getattr(product, 'store_name', 'غير متوفر'),'rating': getattr(product, 'positive_feedback_rate', 'غير متوفر'),'coin_discount_rate': getattr(product, 'coin_discount_rate', 0) / 100.0}
    except Exception as e: print(f"[API_ERROR] {e}.")
    return None

def safe_get_affiliate_link(link: str) -> str:
    try:
        response = aliexpress.get_affiliate_links([link])
        if response and hasattr(response[0], 'promotion_link'): return response[0].promotion_link
        return "تعذر إنشاء الرابط"
    except Exception: return "تعذر إنشاء الرابط"

def extract_link(text: str) -> str:
    link_pattern = r'https?://[a-zA-Z0-9.-]*aliexpress\.[a-zA-Z0-9./_?=&-]+'
    links = re.findall(link_pattern, text)
    return links[0] if links else None

# --- Message Handlers ---
@bot.message_handler(commands=['start', 'help'])
def welcome_user(message):
    welcome_text = "مرحباً بك! أرسل لي أي رابط منتج من AliExpress وسأبحث لك عن أفضل العروض\\."
    bot.send_message(message.chat.id, welcome_text, reply_markup=KEYBOARD_START, parse_mode='MarkdownV2')

@bot.callback_query_handler(func=lambda call: call.data == 'click')
def handle_callbacks(callback_query):
    bot.answer_callback_query(callback_query.id)
    help_text = "لحل مشكلة التخفيض بالعملات، تأكد من تسجيل الدخول لحسابك ووجود عملات كافية\\."
    bot.send_message(callback_query.message.chat.id, help_text, reply_markup=KEYBOARD_START, parse_mode='MarkdownV2')

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    link = extract_link(message.text)
    if not link:
        bot.send_message(message.chat.id, "لم أجد رابطًا في رسالتك\\. يرجى إرسال رابط صحيح\\.", reply_markup=KEYBOARD_START, parse_mode='MarkdownV2')
        return

    processing_msg = bot.send_message(message.chat.id, f'جاري البحث عن أفضل العروض لـ{SHIP_TO_COUNTRY}... ⏳')
    try:
        product_id = extract_product_id_from_url(link)
        if not product_id:
            bot.edit_message_text("❌ لم أتمكن من استخراج معرّف المنتج\\.", chat_id=message.chat.id, message_id=processing_msg.message_id, parse_mode='MarkdownV2')
            return

        product_info = get_product_details(product_id)
        if not product_info:
            bot.edit_message_text("❌ لم أتمكن من جلب تفاصيل المنتج\\.", chat_id=message.chat.id, message_id=processing_msg.message_id, parse_mode='MarkdownV2')
            return

        encoded_link = quote(link, safe='')
        coins_link = safe_get_affiliate_link(f'https://star.aliexpress.com/share/share.htm?platform=AE&businessType=ProductDetail&redirectUrl={encoded_link}?sourceType=620')
        super_link = safe_get_affiliate_link(f'https://star.aliexpress.com/share/share.htm?platform=AE&businessType=ProductDetail&redirectUrl={encoded_link}?sourceType=562')
        coins_hub_link = "https://s.click.aliexpress.com/e/_oBs9DwX"

        estimated_text = ""
        if product_info['coin_discount_rate'] > 0 and product_info['price']:
            try:
                price_float = float(product_info['price'])
                estimated_price = price_float * (1 - product_info['coin_discount_rate'])
                estimated_text = f"\n💎 *السعر بالعملات قد يصل إلى*: *{estimated_price:.2f} {CURRENCY_CODE}*"
            except: pass
        
        rating_display = f"{product_info['rating']}%" if str(product_info['rating']).replace('.', '', 1).isdigit() else product_info['rating']

        caption = (f"📌 *{escape_markdown_v2(product_info['title'])}*\n\n"
                   f"💰 *أفضل سعر*: *{escape_markdown_v2(str(product_info['price']))} {escape_markdown_v2(CURRENCY_CODE)}*"
                   f"{escape_markdown_v2(estimated_text)}\n\n"
                   f"⭐️ *شراء المنتج بخصم العملات*:\n{escape_markdown_v2(coins_link)}\n\n"
                   f"🔗 *رابط عرض BIG SAVE*:\n{escape_markdown_v2(super_link)}\n\n"
                   f"💰 *مركز العملات* \\(اجمع عملاتك من هنا\\):\n{escape_markdown_v2(coins_hub_link)}\n\n"
                   f"\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
                   f"🛍️ *المتجر*: {escape_markdown_v2(product_info['store_name'])}\n"
                   f"📊 *التقييم*: {escape_markdown_v2(rating_display)}\n\n"
                   f"⚠️ *ملاحظة*: الاسعار تقديرية السعر النهائي بعد التخفيض يظهر عند الدفع\\.")

        bot.delete_message(message.chat.id, processing_msg.message_id)
        bot.send_photo(message.chat.id, product_info['image_url'], caption=caption, reply_markup=KEYBOARD_OFFERS, parse_mode='MarkdownV2')

    except Exception as e:
        print(f"Error processing link: {e}")
        traceback.print_exc()
        bot.edit_message_text("❌ حدث خطأ أثناء معالجة الرابط\\. حاول مرة أخرى\\.", chat_id=message.chat.id, message_id=processing_msg.message_id, parse_mode='MarkdownV2')

# --- Set Webhook (Run this once when you deploy or change the URL) ---
def set_webhook():
    # يجب أن تحصل على هذا الرابط من لوحة تحكم Render
    # مثال: https://your-bot-name.onrender.com
    RENDER_URL = os.getenv("RENDER_EXTERNAL_URL") 
    if RENDER_URL:
        WEBHOOK_URL = f"{RENDER_URL}/{BOT_TOKEN}"
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"Webhook set to {WEBHOOK_URL}")
    else:
        print("Could not set webhook: RENDER_EXTERNAL_URL environment variable not found.")

# The Flask app is run by the Gunicorn server configured in Render
# We only set the webhook when the app starts
if __name__ == 'main_for_webhook':
    set_webhook()
