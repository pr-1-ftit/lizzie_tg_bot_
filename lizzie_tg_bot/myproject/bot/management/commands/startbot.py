from django.core.management.base import BaseCommand
from bot.bot_handler import run_telegram_bot

class Command(BaseCommand):
    help = "Запускає Telegram-бота"

    def handle(self, *args, **kwargs):
        run_telegram_bot()
