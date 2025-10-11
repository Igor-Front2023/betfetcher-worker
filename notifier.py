# notifier.py - simple wrapper around telegram Bot to send admin messages
from telegram import Bot
import asyncio

class Notifier:
    def __init__(self, bot_or_token, admin_id):
        # bot_or_token: Application.bot or token string
        if hasattr(bot_or_token, 'send_message'):
            self.bot = bot_or_token
        else:
            self.bot = Bot(token=bot_or_token)
        self.admin_id = admin_id

    async def notify(self, text: str):
        try:
            # send_message is sync in Bot, but Application.bot has async send_message
            send = getattr(self.bot, 'send_message', None)
            if asyncio.iscoroutinefunction(send):
                await send(chat_id=self.admin_id, text=text[:4000])
            else:
                # run sync send_message in executor
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: self.bot.send_message(chat_id=self.admin_id, text=text[:4000]))
        except Exception as e:
            print("Notifier error:", e)
