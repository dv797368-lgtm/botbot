import os
import telebot
from flask import Flask, request

# 👇 حط التوكن تاعك هنا
TOKEN = "7473686932:AAEmpKvL4rJyC2aEzyJ3be65eCF2FFdwc6A"
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

# ========= أوامر البوت =========
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 مرحبا! أنا البوت تاعك، اكتب /help باش تعرف الأوامر المتاحة.")

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
ℹ️ الأوامر المتاحة:

/start - بدء المحادثة مع البوت
/help - عرض المساعدة
اكتب أي رسالة أخرى باش نرجعلك نفس النص
"""
    bot.reply_to(message, help_text)

# ========= رد على أي نص آخر =========
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"📩 انت كتبت: {message.text}")

# ========= Webhook =========
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "OK", 200
    else:
        return "Unsupported Media Type", 415

@app.route('/', methods=['GET'])
def index():
    return "بوت شغال ✅", 200


if __name__ == "__main__":
    # Render يعطيك PORT تلقائياً
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
