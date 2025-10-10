# notifier.py
import logging
from telegram import Bot

class Notifier:
    def __init__(self, bot: Bot, admin_id: int):
        self.bot = bot
        self.admin_id = admin_id

    async def notify(self, text: str):
        try:
            if not text:
                return
            # Telegram has message length limits, обрежем при необходимости
            if len(text) > 4000:
                text = text[:3997] + "..."
            await self.bot.send_message(chat_id=self.admin_id, text=text)
        except Exception as e:
            logging.exception("Notifier error while sending message")
