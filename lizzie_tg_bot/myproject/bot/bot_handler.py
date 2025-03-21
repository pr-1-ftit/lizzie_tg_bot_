import os
import json
import logging
import time
import psycopg2
import ollama
import asyncio
import random
from dotenv import load_dotenv
from urllib.parse import urlparse
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Завантаження змінних середовища
load_dotenv()

# Завантаження конфігурації
CONFIG_FILE = "config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    raise ValueError("❌ Файл config.json не знайдено!")

# Токен і база даних
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
if not TOKEN or not DATABASE_URL:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN і DATABASE_URL не знайдено у .env!")

# Логування
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Функція підключення до PostgreSQL
def connect_db():
    try:
        result = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            dbname=result.path[1:], user=result.username, password=result.password,
            host=result.hostname, port=result.port, sslmode='disable', client_encoding='UTF8'
        )
        return conn
    except Exception as e:
        logger.error(f"❌ Помилка підключення до бази даних: {e}")
        return None

# Створення таблиць
def create_tables():
    conn = connect_db()
    if conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    language TEXT DEFAULT 'українська',
                    age INTEGER
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL
                );
            """)
            conn.commit()
        conn.close()

create_tables()

# Функція збереження повідомлення у базу
def save_message(user_id, role, content):
    conn = connect_db()
    if conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_history (user_id, role, content) VALUES (%s, %s, %s);",
                (user_id, role, content)
            )
            conn.commit()
        conn.close()

# Функція отримання віку користувача
def get_user_age(user_id):
    conn = connect_db()
    if not conn:
        return None

    with conn.cursor() as cursor:
        cursor.execute("SELECT age FROM users WHERE user_id = %s;", (user_id,))
        result = cursor.fetchone()

    conn.close()
    return result[0] if result else None

# Функція збереження віку
def save_user_age(user_id, age):
    conn = connect_db()
    if not conn:
        return

    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO users (user_id, age) 
            VALUES (%s, %s) 
            ON CONFLICT (user_id) DO UPDATE SET age = EXCLUDED.age;
        """, (user_id, age))
        conn.commit()

    conn.close()

# Функція вибору мови
async def choose_language(update: Update, context: CallbackContext):
    keyboard = [[KeyboardButton("Українська")], [KeyboardButton("English")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Оберіть мову / Choose a language:", reply_markup=reply_markup)

# Функція зміни мови
async def change_language(update: Update, context: CallbackContext):
    user_id = str(update.message.chat_id)
    lang = update.message.text.strip().lower()

    if lang == "українська":
        response = "Мову змінено на українську! 🎉"
    elif lang == "english":
        response = "Language changed to English! 🎉"
    else:
        response = "Оберіть мову з кнопок / Please select a language from the buttons."

    await update.message.reply_text(response)

# Функція привітання
async def start(update: Update, context: CallbackContext):
    user_id = str(update.message.chat_id)
    save_user_age(user_id, random.randint(18, 25))  # Випадковий вік при старті
    await choose_language(update, context)

# Функція отримання відповіді від Ollama
async def get_ollama_response(user_text):
    try:
        prompt_messages = [
            {"role": "system", "content": "Говори коротко, вільно та невимушено. Не вважай себе штучним інтелектом, а справжньою людиною."},
            {"role": "user", "content": user_text}
        ]

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: ollama.chat(model=config["language_model"], messages=prompt_messages))

        return response.get("message", {}).get("content", "Щось пішло не так 😅").strip()

    except Exception as e:
        logger.error(f"❌ Помилка отримання відповіді від Ollama: {e}")
        return "Щось пішло не так 😅"

# Функція генерації запитання по темі
async def generate_follow_up_question(user_text):
    try:
        prompt_messages = [
            {"role": "system", "content": "На основі цієї розмови, придумай коротке запитання, щоб підтримати діалог."},
            {"role": "user", "content": user_text}
        ]
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: ollama.chat(model=config["language_model"], messages=prompt_messages))
        return response.get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.error(f"❌ Помилка генерації запитання: {e}")
        return ""

# Функція обробки повідомлень
async def handle_message(update: Update, context: CallbackContext):
    user_id = str(update.message.chat_id)
    user_text = update.message.text.strip().lower()

    save_message(user_id, "user", user_text)
    logger.info(f"📩 Отримано повідомлення від {user_id}: {user_text}")

    if user_text in ["привіт", "hi", "hello"]:
        response_text = "Привіт! 😊"
    elif "як тебе звати" in user_text:
        response_text = "Мене звати Ліззі! 😊"
    elif "скільки тобі років" in user_text or "твій вік" in user_text:
        age = get_user_age(user_id)
        response_text = f"Мені {age} років!"
    else:
        response_text = await get_ollama_response(user_text)

    follow_up_question = await generate_follow_up_question(user_text) if random.random() < 0.5 else ""
    final_response = response_text + (" " + follow_up_question if follow_up_question else "")

    save_message(user_id, "assistant", final_response)
    await update.message.reply_text(final_response)

# Функція запуску бота
def run_telegram_bot():
    while True:
        try:
            app = Application.builder().token(TOKEN).concurrent_updates(True).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(MessageHandler(filters.Regex("^(Українська|English)$"), change_language))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            logger.info("🚀 Бот запущений!")
            app.run_polling()
        except Exception as e:
            logger.error(f"❌ Помилка: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_telegram_bot()
