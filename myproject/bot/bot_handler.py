import os
import logging
import ollama
import json
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Завантажуємо змінні середовища
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Файл для збереження історії
HISTORY_FILE = "chat_history.json"

# Завантаження історії чату
if os.path.exists(HISTORY_FILE) and os.path.getsize(HISTORY_FILE) > 0:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            chat_history = json.load(file)
    except json.JSONDecodeError:
        logger.error("❌ Помилка декодування JSON! Очищуємо файл...")
        chat_history = {}
else:
    chat_history = {}


# Функція збереження історії
def save_history():
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(chat_history, file, ensure_ascii=False, indent=4)


# Словники для збереження контексту користувача
user_languages = {}

# Тексти привітання на різних мовах
LANGUAGES = {
    "en": "Hello! I am Lizzi, your supportive assistant. Let's chat and improve together!",
    "uk": "Привіт! Я Ліззі, твій підтримуючий асистент. Давай спілкуватися і розвиватися разом!"
}


# Обробник команди /start
async def start(update: Update, context: CallbackContext):
    keyboard = [[KeyboardButton("English")], [KeyboardButton("Українська")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text("Choose your language / Оберіть мову:", reply_markup=reply_markup)


# Обробник вибору мови
async def set_language(update: Update, context: CallbackContext):
    user_id = str(update.message.chat_id)
    language = update.message.text.lower()

    if language in ["english", "англійська"]:
        user_languages[user_id] = "en"
    elif language in ["українська", "ukrainian"]:
        user_languages[user_id] = "uk"
    else:
        await update.message.reply_text("Please choose either 'English' or 'Українська'.")
        return

    chat_history[user_id] = {"language": user_languages[user_id], "context": []}
    save_history()
    await update.message.reply_text(LANGUAGES[user_languages[user_id]])


# Функція для отримання відповіді від Ollama
async def get_gemma_response(user_id, user_message):
    try:
        if user_id not in chat_history:
            chat_history[user_id] = {"language": "uk", "context": []}

        chat_history[user_id]["context"].append({"role": "user", "content": user_message})

        response = ollama.chat(
            model="gemma:7b",
            messages=chat_history[user_id]["context"]
        )
        bot_response = response["message"]["content"]

        chat_history[user_id]["context"].append({"role": "assistant", "content": bot_response})
        save_history()
        return bot_response
    except Exception as e:
        logger.error(f"Помилка при зверненні до Ollama: {e}")
        return "Щось пішло не так 😕"


# Обробник текстових повідомлень
async def handle_message(update: Update, context: CallbackContext):
    user_id = str(update.message.chat_id)
    user_text = update.message.text

    ai_response = await get_gemma_response(user_id, user_text)
    await update.message.reply_text(ai_response)


# Команда для перезапуску чату
async def restart(update: Update, context: CallbackContext):
    user_id = str(update.message.chat_id)
    if user_id in chat_history:
        chat_history[user_id]["context"] = []
        save_history()
    await update.message.reply_text("🔄 Розмова перезапущена! Ви можете почати з чистого листа.")


# Функція запуску бота
def run_telegram_bot():
    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не знайдено!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setlanguage", set_language))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ Бот запущений...")
    app.run_polling()


# Запускаємо бота
if __name__ == "__main__":
    run_telegram_bot()
