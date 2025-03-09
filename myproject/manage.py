import os
import logging
import ollama
import random
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Завантажуємо змінні середовища
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Словники для збереження контексту користувача
user_context = {}
user_gender = {}  # Збереження статі співрозмовника
user_questions = {}  # Збереження списку вже заданих питань

# База питань для кожної статі
QUESTION_SETS = {
    "чоловік": [
        "А ти як думаєш?",
        "Чим зараз займаєшся?",
        "Які у тебе плани на сьогодні?",
        "Що останнім часом тебе вразило?",
        "Є щось цікаве, що ти б хотів обговорити?",
        "Який останній фільм або серіал ти дивився?",
    ],
    "жінка": [
        "А ти як думаєш? 😏",
        "Чим займаєшся, красуне?",
        "Які у тебе плани, сонечко?",
        "Що останнім часом тебе вразило?",
        "Є щось цікаве, що ти б хотіла обговорити?",
        "Який останній фільм або серіал ти дивилася?",
    ],
}


# Функція для отримання унікального питання
def get_unique_question(user_id):
    gender = user_gender.get(user_id, "чоловік")

    # Якщо користувач ще не отримував питань, ініціалізуємо йому список
    if user_id not in user_questions or not user_questions[user_id]:
        user_questions[user_id] = QUESTION_SETS[gender].copy()
        random.shuffle(user_questions[user_id])  # Перемішуємо список питань

    return user_questions[user_id].pop()  # Вибираємо питання та видаляємо його зі списку


# Функція для отримання відповіді від Gemma через Ollama
def get_gemma_response(user_id, user_message):
    try:
        if user_id not in user_context:
            user_context[user_id] = [{"role": "system", "content": "Будь природною, живою, зберігай контекст розмови."}]

        user_context[user_id].append({"role": "user", "content": user_message})

        # Фіксовані відповіді
        user_message_lower = user_message.lower()

        if "твоє ім'я" in user_message_lower or "як тебе звати" in user_message_lower:
            return "Мене звати Lizzi 😊"

        if "як справи" in user_message_lower:
            return random.choice(["Чудово! А ти?", "Непогано, тільки що каву пила. А у тебе як?", "Та норм, трохи сумую."])

        if "скільки тобі років" in user_message_lower or "який твій вік" in user_message_lower:
            age = random.randint(18, 25)
            return f"Мені {age} 😊"

        response = ollama.chat(model="gemma:7b", messages=user_context[user_id])
        bot_response = response["message"]["content"]

        # Обмеження довжини відповіді
        if len(bot_response) > 100:
            bot_response = bot_response[:100] + "..."

        user_context[user_id].append({"role": "assistant", "content": bot_response})

        return bot_response
    except Exception as e:
        logger.error(f"Помилка при зверненні до Ollama: {e}")
        return "Щось пішло не так 😕"


# Обробник команди /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привіт! Я Lizzi. Напиши /setgender чоловік або /setgender жінка, щоб я підлаштувала стиль спілкування 😊")


# Обробник команди /setgender
async def set_gender(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    if not context.args:
        await update.message.reply_text("Будь ласка, вкажи стать: /setgender чоловік або /setgender жінка.")
        return

    gender = context.args[0].lower()
    if gender in ["чоловік", "жінка"]:
        user_gender[user_id] = gender
        user_questions[user_id] = []  # Очищаємо питання, щоб оновити список під стать
        await update.message.reply_text(f"Окей! Тепер я буду спілкуватися з тобою як з {gender} ❤️")
    else:
        await update.message.reply_text("Некоректне значення. Вибери: /setgender чоловік або /setgender жінка.")


# Обробник текстових повідомлень
async def handle_message(update: Update, context: CallbackContext):
    user_text = update.message.text
    user_id = update.message.chat_id

    ai_response = get_gemma_response(user_id, user_text)
    await update.message.reply_text(ai_response)

    # Додаємо унікальне питання Ліззі після відповіді
    if random.random() > 0.4:  # 60% шанс задати питання
        question = get_unique_question(user_id)
        await update.message.reply_text(question)


# Функція запуску бота
def run_telegram_bot():
    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не знайдено!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setgender", set_gender))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ Бот запущений...")
    app.run_polling()


# Запускаємо бота
if __name__ == "__main__":
    run_telegram_bot()
