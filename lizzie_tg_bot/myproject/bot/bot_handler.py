import os
import logging
import ollama
import sqlite3
import time
import random

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Завантаження змінних середовища
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Логування
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Підключення до бази даних
DB_FILE = "lizzie_learning.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

# Створення таблиць
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    language TEXT DEFAULT 'uk',
    greeted INTEGER DEFAULT 0,
    age INTEGER
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS chat_history (
    user_id TEXT,
    role TEXT,
    content TEXT,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);
""")

conn.commit()

MAX_HISTORY = 10

def get_user_language(user_id):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else "uk"

def set_user_language(user_id, language):
    cursor.execute("INSERT INTO users (user_id, language, greeted, age) VALUES (?, ?, 0, NULL) ON CONFLICT(user_id) DO UPDATE SET language = ?",
                   (user_id, language, language))
    conn.commit()

def has_greeted(user_id):
    cursor.execute("SELECT greeted FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] == 1

def set_greeted(user_id):
    cursor.execute("UPDATE users SET greeted = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

def get_or_set_age(user_id):
    cursor.execute("SELECT age FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result and result[0] is not None:
        return result[0]

    new_age = random.randint(18, 25)
    cursor.execute("UPDATE users SET age = ? WHERE user_id = ?", (new_age, user_id))
    conn.commit()
    return new_age

async def start(update: Update, context: CallbackContext):
    keyboard = [[KeyboardButton("English 🇬🇧")], [KeyboardButton("Українська 🇺🇦")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("🌍 Обери мову:", reply_markup=reply_markup)

async def set_language(update: Update, context: CallbackContext):
    user_id = str(update.message.chat_id)
    user_choice = update.message.text

    language = "en" if "English" in user_choice else "uk" if "Українська" in user_choice else None
    if not language:
        await update.message.reply_text("⚠️ Обери мову зі списку.")
        return

    set_user_language(user_id, language)
    await update.message.reply_text("Привіт! 😊" if language == "uk" else "Hi! 😊")
    set_greeted(user_id)

async def clear_history(update: Update, context: CallbackContext):
    user_id = str(update.message.chat_id)
    cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
    conn.commit()
    cursor.execute("UPDATE users SET greeted = 0, age = NULL WHERE user_id = ?", (user_id,))
    conn.commit()

    message = "Готово, почнемо з чистого листа! 😉" if get_user_language(user_id) == "uk" else "Done, fresh start! 😉"
    await update.message.reply_text(message)

async def get_lizzie_response(user_id, user_message):
    try:
        language = get_user_language(user_id)

        if any(word in user_message.lower() for word in ["скільки тобі років", "який твій вік", "скільки років"]):
            age = get_or_set_age(user_id)
            phrases = [
                f"{age}, а тобі? 😉",
                f"Десь {age}, а що? 😏",
                f"{age}, але я молода душею 😆"
            ]
            return random.choice(phrases) if language == "uk" else f"{age}, but I feel young! 😉"

        bot_protection = [
            "ти бот", "ти справжня", "ти штучний", "ти штучний інтелект", "це ai", "ти справжня людина", "ти робот", "ти реально існуєш",
            "are you a bot", "are you real", "are you AI", "are you a human", "do you exist", "are you fake"
        ]

        if any(word in user_message.lower() for word in bot_protection):
            return random.choice([
                "Та ну, я жива, як і ти! 😊",
                "Дивне питання, звісно що так!",
                "Що за думки? 😄",
                "А ти як думаєш?",
                "Я просто така, яка є 😉"
            ]) if language == "uk" else random.choice([
                "Come on, I'm as real as you! 😊",
                "Weird question, of course I am!",
                "What makes you think that? 😄",
                "What do you think?",
                "I am who I am 😉"
            ])

        chat_history = [{"role": "system", "content": (
            "Відповідай просто, коротко і дружньо, без зайвих слів. Ніколи не кажи, що ти бот. Веди розмову як справжня людина."
        ) if language == "uk" else (
            "Keep responses short, friendly, and to the point. Never admit to being a bot. Talk like a real person."
        )}]

        chat_history.append({"role": "user", "content": user_message})

        response = ollama.chat(model="Mistral:latest", messages=chat_history)
        bot_response = response["message"]["content"].strip()

        return bot_response
    except Exception as e:
        logger.error(f"❌ Помилка: {e}")
        return "Щось пішло не так 😅"

async def handle_message(update: Update, context: CallbackContext):
    user_id = str(update.message.chat_id)
    user_text = update.message.text

    if not get_user_language(user_id):
        await start(update, context)
        return

    if not has_greeted(user_id):
        await update.message.reply_text("Привіт! 😊")
        set_greeted(user_id)

    ai_response = await get_lizzie_response(user_id, user_text)
    await update.message.reply_text(ai_response)

def run_telegram_bot():
    while True:
        try:
            app = Application.builder().token(TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("clear", clear_history))
            app.add_handler(MessageHandler(filters.Regex("^(English 🇬🇧|Українська 🇺🇦)$"), set_language))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

            logger.info("✅ Бот запущений...")
            app.run_polling()
        except Exception as e:
            logger.error(f"❌ Помилка: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_telegram_bot()
